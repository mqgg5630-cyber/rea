"""Offline self-check for sys1.

    python selfcheck.py            # human summary, exit 0/1
    python selfcheck.py --json     # machine receipt
    python selfcheck.py --local    # add host facts and SYS1_LOCAL_OK marker

Everything is local: no socket leaves loopback, no model download, no API key.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import platform
import socket
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from sys1 import DecisionEngine, VERSION  # noqa: E402
from sys1.decode import (  # noqa: E402
    TemperatureTable,
    add_jev_confidence,
    answer_confidence,
    apply_confidence_gate,
    confidence_from_probs,
    jev_confidence,
    project_jev_strict,
    softmax,
)
from sys1.lang import analyse, route_model  # noqa: E402
from sys1.mcp import Server as McpServer  # noqa: E402
from sys1.protocol import build_prompt, normalize_questions, render_options  # noqa: E402
from sys1.serve import create_server  # noqa: E402

GOLDENS = os.path.join(HERE, "sys1", "data", "goldens.json")
RESULTS: List[Dict[str, Any]] = []


def check(name: str, ok: bool, detail: Any = None) -> bool:
    RESULTS.append({"check": name, "ok": bool(ok), "detail": detail})
    return bool(ok)


def case(**kwargs):
    return {"type": kwargs.pop("type"), "instructions": kwargs.pop("instructions"), **kwargs}


def _golden_parity() -> Dict[str, int]:
    with open(GOLDENS, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    total = ok = 0
    for checkpoint, block in doc["checkpoints"].items():
        temps = block["temperatures"]
        table = TemperatureTable(temps.get("temperature_by_options"), temps.get("temperature"))
        for golden in block["cases"]:
            answers = golden["result"]["answers"]
            for index, (qid, qdef) in enumerate(golden["questions"].items()):
                kind = qdef["type"]
                k = 2 if kind == "noul" else len(qdef.get("criteria") or [])
                answer = answers[qid]
                if "probabilities" in answer and len(answer["probabilities"]) != k:
                    continue
                probs = softmax(list(golden["logits"][index])[:k], table.get(kind, k))
                if kind == "choice":
                    keys = (list(qdef["criteria"].keys()) if isinstance(qdef["criteria"], dict)
                            else list(qdef["criteria"]))
                    expected = {key: round(v, 4) for key, v in zip(keys, probs)}
                    got = answer["probabilities"]
                    conf = round(confidence_from_probs(probs, k), 4)
                elif kind == "score":
                    expected = {str(i): round(v, 4) for i, v in enumerate(probs)}
                    got = answer["probabilities"]
                    conf = round(confidence_from_probs(probs, k), 4)
                else:
                    expected = {"noul": round(probs[1], 4)}
                    got = {"noul": answer["noul"]}
                    conf = round(max(probs[1], 1 - probs[1]), 4)
                total += 1
                same = all(abs(expected[key] - got[key]) <= 0.00011 for key in expected)
                same = same and abs(conf - answer.get("confidence", conf)) <= 0.00011
                same = same and abs(round(max(probs), 4) - answer.get("answer_confidence", 0)) <= 0.00011
                ok += int(same)
    return {"total": total, "exact": ok}


def _http_suite(engine: DecisionEngine) -> Dict[str, Any]:
    server = create_server("127.0.0.1", 0, engine)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = "http://127.0.0.1:%d" % port
    out: Dict[str, Any] = {}
    try:
        with urllib.request.urlopen(base + "/health", timeout=5) as r:
            health = json.loads(r.read())
            out["health"] = {"status": health.get("status"), "http": r.status,
                             "server_timing": r.headers.get("Server-Timing")}
        body = {
            "state": "我的订阅被重复扣费了，今天必须退款，否则我就取消。",
            "questions": {
                "team": case(type="choice", instructions="Which team?",
                             criteria={"billing": "payments and refunds",
                                       "technical": "bugs and outages"}),
                "urgency": case(type="score", instructions="How urgent?",
                                criteria=["low", "normal", "high"]),
                "churn": case(type="noul", instructions="Threatens to cancel?"),
            },
        }
        req = urllib.request.Request(base + "/v1/systemone", data=json.dumps(body).encode(),
                                     headers={"content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            payload = json.loads(r.read())
            out["single"] = {"http": r.status, "has_routing": "routing" in payload,
                             "answers": payload.get("answers"),
                             "timing_header": r.headers.get("X-Inference-Time-Ms")}
        batch = {"states": ["I was charged twice.", "The app crashes on login."],
                 "questions": {"team": body["questions"]["team"]}}
        req = urllib.request.Request(base + "/v1/systemone/batch", data=json.dumps(batch).encode(),
                                     headers={"content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            payload = json.loads(r.read())
            out["batch"] = {"http": r.status, "n": len(payload.get("results", [])),
                            "total_usage": payload.get("total_usage")}
        for label, payload, expected in (
            ("missing_state", {"questions": {"q": case(type="noul", instructions="x?")}}, 400),
            ("bad_question", {"state": "x", "questions": {"q": {"type": "wat"}}}, 422),
            ("too_many_options", {"state": "x", "questions": {"q": case(
                type="choice", instructions="pick", criteria={str(i): "x" for i in range(120)})}}, 413),
        ):
            req = urllib.request.Request(base + "/v1/systemone", data=json.dumps(payload).encode(),
                                         headers={"content-type": "application/json"})
            try:
                urllib.request.urlopen(req, timeout=5)
                code = 200
            except urllib.error.HTTPError as exc:
                code = exc.code
            out[label] = {"http": code, "expected": expected}
        # strict projection contract
        strict = project_jev_strict({
            "model": "m", "answers": out["single"]["answers"],
            "usage": {"input_tokens": 1, "output_tokens": 0, "truncated": False},
            "routing": {"model": "x"},
        })
        out["strict"] = {"keys": sorted(strict), "usage_keys": sorted(strict["usage"]),
                         "answer_keys": {k: sorted(v) for k, v in strict["answers"].items()}}
    finally:
        server.shutdown()
        server.server_close()
    return out


def _mcp_suite(engine: DecisionEngine) -> Dict[str, Any]:
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
            "name": "system_one", "arguments": {
                "state": "Repeated charge on my invoice; refund it today.",
                "questions": {"team": case(type="choice", instructions="Which team?",
                                           criteria={"billing": "payments and refunds",
                                                     "technical": "bugs"})},
                "engine": "local"}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {
            "name": "system_one", "arguments": {
                "state": "Repeated charge on my invoice; refund it today.",
                "questions": {"team": case(type="choice", instructions="Which team?",
                                           criteria={"billing": "payments and refunds",
                                                     "technical": "bugs"})},
                "engine": "agent"}}},
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {
            "name": "system_one", "arguments": {
                "state": "Repeated charge on my invoice; refund it today.",
                "questions": {"team": case(type="choice", instructions="Which team?",
                                           criteria={"billing": "payments and refunds",
                                                     "technical": "bugs"})},
                "engine": "agent", "agent_logits": {"team": [0.0, 3.0]}}}},
    ]
    stdin = io.StringIO("\n".join(json.dumps(r) for r in requests) + "\n")
    stdout = io.StringIO()
    McpServer(engine, stdin=stdin, stdout=stdout).serve()
    lines = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
    by_id = {line.get("id"): line for line in lines}
    local = json.loads(by_id[3]["result"]["content"][0]["text"])
    needs = json.loads(by_id[4]["result"]["content"][0]["text"])
    scored = json.loads(by_id[5]["result"]["content"][0]["text"])
    return {
        "initialize": by_id[1]["result"]["serverInfo"],
        "tools": [tool["name"] for tool in by_id[2]["result"]["tools"]],
        "local_choice": local["answers"]["team"]["choice"],
        "needs_status": needs.get("status"),
        "has_prompt": "prompt" in list(needs["questions"].values())[0],
        "agent_choice": scored["answers"]["team"]["choice"],
    }


def _offline_audit() -> Dict[str, Any]:
    banned = ("import requests", "import httpx", "import aiohttp", "urlopen(", "socket.create_connection")
    hits = []
    for name in sorted(os.listdir(os.path.join(HERE, "sys1"))):
        if not name.endswith(".py"):
            continue
        path = os.path.join(HERE, "sys1", name)
        text = open(path, "r", encoding="utf-8").read()
        for needle in banned:
            if needle in text and name not in ("serve.py",):
                hits.append("%s:%s" % (name, needle))
    return {"banned_client_imports": hits, "stdlib_only": not hits,
            "python": platform.python_version()}


def _blocked_socket_test(engine: DecisionEngine) -> bool:
    original = socket.create_connection

    def blocked(*args, **kwargs):
        raise AssertionError("outbound connection attempted")

    socket.create_connection = blocked  # type: ignore[assignment]
    try:
        result = engine.predict("Refund my duplicate charge.", {
            "q": case(type="choice", instructions="Team?",
                      criteria={"billing": "refunds", "tech": "bugs"})})
        return result["answers"]["q"]["choice"] == "billing"
    except AssertionError:
        return False
    finally:
        socket.create_connection = original  # type: ignore[assignment]


def audit() -> Dict[str, Any]:
    return {"version": VERSION, "offline": _offline_audit()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--out", default=os.path.join(HERE, "..", "..", "results", "sys1"))
    args = parser.parse_args()

    started = time.perf_counter()
    engine = DecisionEngine()

    # 1. protocol rendering -------------------------------------------------
    q = normalize_questions({"intent": {"type": "choice", "instructions": "Classify.",
                                        "criteria": ["upgrade", "cancel"]}})["intent"]
    opts = render_options(q)
    prompt = build_prompt("upgrade please", q)
    check("render_options keeps order", opts == ["upgrade", "cancel"], opts)
    check("prompt layout", prompt.startswith("[CLS] choice question: Classify. [SEP] [MASK] upgrade")
          and prompt.endswith("[SEP] upgrade please [SEP]"), prompt)

    # 2. formulas -----------------------------------------------------------
    p = softmax([1.0, 0.0, 0.0], 1.0)
    check("softmax sums to 1", abs(sum(p) - 1.0) < 1e-12, p)
    check("entropy confidence of uniform", abs(confidence_from_probs([0.25] * 4, 4)) < 1e-12)
    check("answer_confidence is max", abs(answer_confidence([0.2, 0.5, 0.3], 3) - 0.5) < 1e-12)
    check("jev choice confidence", abs(jev_confidence(
        {"type": "choice", "probabilities": {"a": 0.5, "b": 0.25, "c": 0.25}}) - 0.25) < 1e-9)
    check("jev score confidence", abs(jev_confidence(
        {"type": "score", "probabilities": {"0": 0.2, "1": 0.6, "2": 0.2}}) - 0.4) < 1e-9)

    # 3. decoder parity against real laya logits ----------------------------
    parity = _golden_parity()
    check("decoder parity 100%", parity["exact"] == parity["total"] and parity["total"] >= 80, parity)

    # 4. routing ------------------------------------------------------------
    routing_cases = [
        ("Please refund my duplicate charge today.", "english"),
        ("我这个月被重复扣款了两次，请退款。", "multilingual"),
        ("La aplicación se cierra cada vez que abro la configuración.", "multilingual"),
        ("Ich möchte meine Rechnung reklamieren und eine Rückerstattung erhalten.", "multilingual"),
        ("Bonjour, je veux annuler mon abonnement et être remboursé.", "multilingual"),
        ("Quero cancelar minha assinatura e receber o reembolso.", "multilingual"),
        ("返金をお願いします。二重に請求されました。", "multilingual"),
        ("Мне нужно вернуть деньги за подписку.", "multilingual"),
        ("أريد استرداد أموالي من الاشتراك.", "multilingual"),
    ]
    route_ok = all(route_model(text)["model"] == expected for text, expected in routing_cases)
    check("routing natural sentences", route_ok,
          [(text[:18], route_model(text)["model"], expected) for text, expected in routing_cases])
    check("script detection", analyse("Hello")["script"] == "latin"
          and analyse("你好")["script"] == "han" and analyse("123 !!!")["script"] == "unknown")

    # 5. decisions ----------------------------------------------------------
    dec = engine.predict(
        "Hi, I was billed twice for March. Refund the duplicate today or we cancel.",
        {"department": case(type="choice", instructions="Which department?",
                            criteria={"billing": "invoices, payments, refunds",
                                      "technical": "bugs, outages",
                                      "other": "everything else"}),
         "urgency": case(type="score", instructions="How urgent?",
                         criteria=["not urgent", "soon", "blocking"]),
         "churn": case(type="noul", instructions="Does the user threaten to cancel?")})
    check("english triage", dec["answers"]["department"]["choice"] == "billing"
          and dec["answers"]["urgency"]["score"] > 1.0
          and dec["answers"]["churn"]["noul"] > 0.5, dec["answers"])
    cjk = engine.predict("我这个月被重复扣款了两次，退款一直没有到账。今天不解决就取消订阅。",
                         {"department": {"type": "choice", "instructions": "Which department?",
                                         "criteria": {"billing": "invoices, payments, refunds",
                                                      "technical": "bugs, outages",
                                                      "other": "everything else"}},
                          "urgency": case(type="score", instructions="How urgent?",
                                          criteria=["not urgent", "soon", "blocking"])})
    check("cjk cross-lingual", cjk["answers"]["department"]["choice"] == "billing"
          and cjk["answers"]["urgency"]["score"] > 1.0, cjk["answers"])

    # 6. gate ---------------------------------------------------------------
    gated = engine.predict("Maybe something with the app?", {
        "q": case(type="choice", instructions="Team?",
                  criteria={"billing": "refunds", "tech": "bugs", "other": "other"})},
        min_confidence=0.99)
    check("abstention gate", gated["answers"]["q"].get("low_confidence") is True
          and gated["answers"]["q"]["abstention"] == "abstained", gated["answers"]["q"])

    # 7. agent engine -------------------------------------------------------
    agent = engine.predict("Refund my duplicate charge.", {
        "q": case(type="choice", instructions="Team?",
                  criteria={"billing": "refunds", "tech": "bugs"})},
        engine="agent", agent_logits={"q": [0.0, 4.0]})
    check("agent logits decode", agent["answers"]["q"]["choice"] == "tech"
          and agent["sys1"]["engines_used"]["q"] == "agent", agent["answers"]["q"])
    from sys1.engine import NeedsAgentScores
    try:
        engine.predict("x", {"q": case(type="noul", instructions="y?")}, engine="agent")
        check("agent prompt request", False)
    except NeedsAgentScores as exc:
        payload = exc.payload()
        check("agent prompt request", payload["status"] == "needs_agent_scores"
              and "prompt" in payload["questions"]["q"])

    # 8. determinism --------------------------------------------------------
    a = engine.predict("Refund me", {"q": case(type="noul", instructions="Refund?")})
    b = engine.predict("Refund me", {"q": case(type="noul", instructions="Refund?")})
    check("deterministic", a["answers"] == b["answers"], a["answers"])

    # 9. HTTP ---------------------------------------------------------------
    try:
        http = _http_suite(engine)
        ok_http = (http["health"]["status"] == "ok" and http["single"]["http"] == 200
                   and http["single"]["has_routing"] and http["batch"]["n"] == 2
                   and http["missing_state"]["http"] == 400
                   and http["bad_question"]["http"] == 422
                   and http["too_many_options"]["http"] == 413
                   and http["strict"]["keys"] == ["answers", "model", "usage"]
                   and http["strict"]["usage_keys"] == ["input_tokens", "output_tokens"])
        check("HTTP Jev contract", ok_http, http)
    except Exception as exc:  # noqa: BLE001
        check("HTTP Jev contract", False, repr(exc))

    # 10. MCP ---------------------------------------------------------------
    try:
        mcp = _mcp_suite(engine)
        check("MCP stdio", mcp["local_choice"] == "billing" and mcp["needs_status"] == "needs_agent_scores"
              and mcp["has_prompt"] and mcp["agent_choice"] == "technical", mcp)
    except Exception as exc:  # noqa: BLE001
        check("MCP stdio", False, repr(exc))

    # 11. offline -----------------------------------------------------------
    audit_doc = _offline_audit()
    check("no outbound client imports", audit_doc["stdlib_only"], audit_doc)
    check("works with sockets blocked", _blocked_socket_test(engine))

    # 12. latency -----------------------------------------------------------
    state = ("Hello, I was charged twice this month and want a refund. "
             "This is the second time and nobody replied.")
    questions = {"a": case(type="choice", instructions="Team?",
                           criteria={"billing": "refunds", "tech": "bugs", "other": "x"}),
                 "b": case(type="score", instructions="How urgent?", criteria=["low", "high"]),
                 "c": case(type="noul", instructions="Threatens to cancel?")}
    times = []
    for _ in range(200):
        t0 = time.perf_counter()
        engine.predict(state, questions)
        times.append((time.perf_counter() - t0) * 1000.0)
    times.sort()
    latency = {"p50_ms": round(statistics.median(times), 3), "p95_ms": round(times[189], 3),
               "qps": round(1000.0 / statistics.median(times), 1)}
    check("latency under 25 ms p95", latency["p95_ms"] < 25.0, latency)

    passed = sum(1 for item in RESULTS if item["ok"])
    total = len(RESULTS)
    receipt = {
        "tool": "sys1",
        "version": VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": passed,
        "total": total,
        "ok": passed == total,
        "elapsed_s": round(time.perf_counter() - started, 2),
        "checks": RESULTS,
        "latency": latency,
        "audit": audit_doc,
        "host": {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
        },
    }
    if args.local:
        receipt["SYS1_LOCAL_OK"] = receipt["ok"]
    os.makedirs(os.path.abspath(args.out), exist_ok=True)
    with open(os.path.join(args.out, "SELFCHECK.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    md = ["# sys1 self-check", "",
          "- version: `%s`" % VERSION,
          "- result: **%d/%d %s**" % (passed, total, "PASS" if receipt["ok"] else "FAIL"),
          "- host: `%s` (%s, Python %s)" % (receipt["host"]["hostname"], receipt["host"]["platform"],
                                            receipt["host"]["python"]),
          "- latency: p50 %s ms, p95 %s ms, %s decisions/sec"
          % (latency["p50_ms"], latency["p95_ms"], latency["qps"]),
          "", "| check | result |", "|---|---|"]
    for item in RESULTS:
        md.append("| %s | %s |" % (item["check"], "OK" if item["ok"] else "FAIL"))
    md.append("")
    if args.local:
        md.append("SYS1_LOCAL_OK=%s" % receipt["ok"])
    with open(os.path.join(args.out, "SELFCHECK.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md))

    if args.json:
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
    else:
        for item in RESULTS:
            print("%-34s %s" % (item["check"], "OK" if item["ok"] else "FAIL"))
            if not item["ok"]:
                print("    ", json.dumps(item["detail"], ensure_ascii=False)[:600])
        print("\n%d/%d checks passed (%.2fs)" % (passed, total, receipt["elapsed_s"]))
        if args.local:
            print("SYS1_LOCAL_OK=%s" % receipt["ok"])
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
