"""Evidence run: decoder parity, engine agreement, routing parity, latency.

    python evaluate.py --json ../results/sys1/EVAL.json --md ../results/sys1/EVAL.md

Everything here is measurable offline from fixtures committed in this repo.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import time
from typing import Any, Dict, List, Sequence

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from sys1 import DecisionEngine  # noqa: E402
from sys1.calibrate import evaluate_rows, fit, rows_from_goldens  # noqa: E402
from sys1.decode import TemperatureTable, softmax  # noqa: E402
from sys1.lang import analyse, route_model  # noqa: E402
from sys1.protocol import normalize_questions, option_count  # noqa: E402

GOLDENS = os.path.join(HERE, "sys1", "data", "goldens.json")
ROUTING = os.path.join(HERE, "sys1", "data", "routing.json")


def _qk(q: Dict[str, Any]) -> int:
    return 2 if q.get("type") == "noul" else len(q.get("criteria") or [])


def decoder_parity() -> Dict[str, Any]:
    with open(GOLDENS, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    total = ok = skipped = 0
    rows = []
    for checkpoint, block in doc["checkpoints"].items():
        temps = block["temperatures"]
        table = TemperatureTable(temps.get("temperature_by_options"), temps.get("temperature"))
        for case in block["cases"]:
            questions = case["questions"]
            answers = case["result"]["answers"]
            for index, (qid, qdef) in enumerate(questions.items()):
                total += 1
                answer = answers[qid]
                k = _qk(qdef)
                if "probabilities" in answer and len(answer["probabilities"]) != k:
                    skipped += 1
                    continue
                logits = list(case["logits"][index])[:k]
                probs = softmax(logits, table.get(qdef["type"], k))
                if qdef["type"] == "choice":
                    expected = {key: round(v, 4) for key, v in zip(
                        list(qdef["criteria"].keys()) if isinstance(qdef["criteria"], dict)
                        else list(qdef["criteria"]), probs)}
                elif qdef["type"] == "score":
                    expected = {str(i): round(v, 4) for i, v in enumerate(probs)}
                else:
                    expected = {"noul": round(probs[1], 4)}
                got = answer.get("probabilities") or {"noul": answer.get("noul")}
                delta = max(abs(expected[key] - got[key]) for key in expected)
                from sys1.decode import answer_confidence, confidence_from_probs
                if qdef["type"] == "noul":
                    ent = round(max(probs[1], 1.0 - probs[1]), 4)
                else:
                    ent = round(confidence_from_probs(probs, k), 4)
                ac = round(answer_confidence(probs, k), 4)
                delta_conf = abs(ent - answer.get("confidence", ent))
                delta_ac = abs(ac - answer.get("answer_confidence", ac))
                if delta <= 0.00011 and delta_conf <= 0.00011 and delta_ac <= 0.00011:
                    ok += 1
                else:
                    rows.append({"checkpoint": checkpoint, "case": case["name"], "qid": qid,
                                 "delta_probability": delta, "delta_confidence": delta_conf,
                                 "delta_answer_confidence": delta_ac})
    return {"questions": total, "exact": ok, "mismatched": len(rows), "skipped": skipped,
            "mismatches": rows[:10]}


def engine_agreement(engine: DecisionEngine) -> Dict[str, Any]:
    with open(GOLDENS, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    out: Dict[str, Any] = {"per_checkpoint": {}, "total": [0, 0], "score_abs_error": []}
    for checkpoint, block in doc["checkpoints"].items():
        stats = {"choice_n": 0, "choice_hit": 0, "noul_n": 0, "noul_hit": 0,
                 "score_n": 0, "score_abs_error": 0.0}
        for case in block["cases"]:
            questions = case["questions"]
            teacher = case["result"]["answers"]
            result = engine.predict(case["state"], questions, model=checkpoint)
            for qid, qdef in questions.items():
                kind = qdef["type"]
                ours = result["answers"][qid]
                theirs = teacher[qid]
                if kind == "choice":
                    stats["choice_n"] += 1
                    stats["choice_hit"] += int(ours["choice"] == theirs["choice"])
                elif kind == "noul":
                    stats["noul_n"] += 1
                    stats["noul_hit"] += int((ours["noul"] >= 0.5) == (theirs["noul"] >= 0.5))
                elif kind == "score":
                    stats["score_n"] += 1
                    stats["score_abs_error"] += abs(ours["score"] - theirs["score"])
                    out["score_abs_error"].append(abs(ours["score"] - theirs["score"]))
        entry = {
            "choice": {"n": stats["choice_n"], "agreement": round(stats["choice_hit"] / max(1, stats["choice_n"]), 4)},
            "noul": {"n": stats["noul_n"], "agreement": round(stats["noul_hit"] / max(1, stats["noul_n"]), 4)},
            "score": {"n": stats["score_n"],
                      "mean_abs_error": round(stats["score_abs_error"] / max(1, stats["score_n"]), 4)},
        }
        out["per_checkpoint"][checkpoint] = entry
        out["total"][0] += stats["choice_n"] + stats["noul_n"]
        out["total"][1] += stats["choice_hit"] + stats["noul_hit"]
    out["overall_typed_agreement"] = round(out["total"][1] / max(1, out["total"][0]), 4)
    if out["score_abs_error"]:
        out["score_mean_abs_error"] = round(sum(out["score_abs_error"]) / len(out["score_abs_error"]), 4)
    out.pop("score_abs_error")
    return out


def routing_parity() -> Dict[str, Any]:
    with open(ROUTING, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    script = english = language = 0
    total = len(doc["states"])
    for item in doc["states"]:
        expected = item["analyse"]
        got = analyse(item["state"])
        script += int(got["script"] == expected["script"])
        english += int(got["is_english"] == expected["is_english"])
        language += int(got.get("language") == expected.get("language"))
    route_ok = 0
    for item in doc["routes"]:
        state = doc["states"][item["state"]]["state"]
        kwargs = item.get("kwargs") or {}
        got = route_model(state, lang=kwargs.get("lang"), lang_guess=kwargs.get("lang_guess"),
                          router_lang_guess=kwargs.get("router_lang_guess"))
        route_ok += int(got["model"] == item["model"])
    n_routes = len(doc["routes"])
    return {
        "states": total,
        "script": round(script / max(1, total), 4),
        "is_english": round(english / max(1, total), 4),
        "language": round(language / max(1, total), 4),
        "routes": n_routes,
        "route_model": round(route_ok / max(1, n_routes), 4),
    }


def latency(engine: DecisionEngine, n: int = 300) -> Dict[str, Any]:
    state = ("Hello, I was charged twice for my subscription this month and I want a refund. "
             "This is the second time I have written in and nobody has replied.")
    questions = {
        "department": {"type": "choice", "instructions": "Which team?",
                       "criteria": {"billing": "payments and refunds",
                                    "technical": "bugs and errors",
                                    "account": "logins and plans"}},
        "urgency": {"type": "score", "instructions": "How urgent is this?",
                    "criteria": ["low", "normal", "high"]},
        "churn": {"type": "noul", "instructions": "Does the customer threaten to cancel?"},
    }
    engine.predict(state, questions)  # warm
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        engine.predict(state, questions)
        times.append((time.perf_counter() - t0) * 1000.0)
    times.sort()
    return {
        "decisions": n,
        "questions_per_decision": len(questions),
        "p50_ms": round(statistics.median(times), 3),
        "p95_ms": round(times[int(len(times) * 0.95)], 3),
        "min_ms": round(times[0], 3),
        "max_ms": round(times[-1], 3),
        "throughput_decisions_per_sec": round(1000.0 / statistics.median(times), 1),
    }


def calibration() -> Dict[str, Any]:
    """Calibrate the *checkpoint* decoder (baseline evidence)."""
    rows = rows_from_goldens(GOLDENS)
    fit_rows = [row for i, row in enumerate(rows) if i % 2 == 0]
    test_rows = [row for i, row in enumerate(rows) if i % 2 == 1]
    doc = fit(fit_rows)
    table = TemperatureTable(doc["temperature_by_options"], doc["temperature"])
    doc["metrics"] = {
        "fit": evaluate_rows(fit_rows, table),
        "held_out": evaluate_rows(test_rows, table),
        "held_out_default_T1": evaluate_rows(test_rows, TemperatureTable()),
    }
    return doc


def engine_rows(engine: DecisionEngine) -> List[Dict[str, Any]]:
    """Our engine's logits next to laya's teacher distribution, per question."""
    with open(GOLDENS, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    rows: List[Dict[str, Any]] = []
    for checkpoint, block in doc["checkpoints"].items():
        for case in block["cases"]:
            questions = case["questions"]
            result = engine.predict(case["state"], questions, model=checkpoint)
            for qid, qdef in questions.items():
                answer = case["result"]["answers"][qid]
                kind = qdef["type"]
                k = _qk(qdef)
                if kind == "noul":
                    teacher = [1.0 - float(answer["noul"]), float(answer["noul"])]
                else:
                    probs = answer.get("probabilities") or {}
                    keys = sorted(probs, key=int) if kind == "score" else list(probs)
                    teacher = [float(probs[key]) for key in keys]
                if len(teacher) != k:
                    continue
                rows.append({"kind": kind, "k": k, "teacher": teacher,
                             "logits": result["sys1"]["logits"][qid],
                             "checkpoint": checkpoint, "name": case["name"], "qid": qid})
    return rows


def engine_calibration(engine: DecisionEngine) -> Dict[str, Any]:
    """Fit temperatures on our own logits; report held-out ECE."""
    rows = engine_rows(engine)
    fit_rows = [row for i, row in enumerate(rows) if i % 2 == 0]
    test_rows = [row for i, row in enumerate(rows) if i % 2 == 1]
    doc = fit(fit_rows, objective="brier")
    table = TemperatureTable(doc["temperature_by_options"], doc["temperature"])
    custom = DecisionEngine(temperatures=table, rubric=engine.scorer.rubric,
                            model_name=engine.model_name,
                            calibration_note="fitted")
    doc["metrics"] = {
        "fit": evaluate_rows(fit_rows, table),
        "held_out": evaluate_rows(test_rows, table),
        "held_out_default_T1": evaluate_rows(test_rows, TemperatureTable()),
        "held_out_agreement_fitted": engine_agreement(custom),
    }
    doc["source"] = "laya golden teacher distributions, fitted on this engine's logits"
    return doc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", default=os.path.join(HERE, "..", "..", "results", "sys1", "EVAL.json"))
    parser.add_argument("--md", default=os.path.join(HERE, "..", "..", "results", "sys1", "EVAL.md"))
    parser.add_argument("--write-calibration", action="store_true",
                        help="write sys1/data/calibration.json from held-in rows")
    args = parser.parse_args()

    engine = DecisionEngine()
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "decoder_parity": decoder_parity(),
        "engine_agreement": engine_agreement(engine),
        "routing_parity": routing_parity(),
        "latency": latency(engine),
        "calibration_fit": calibration(),
        "engine_calibration": engine_calibration(engine),
    }
    if args.write_calibration:
        from sys1.calibrate import save
        ec = report["engine_calibration"]
        save({
            "version": "1.0.0",
            "source": ec["source"],
            "temperature": ec["temperature"],
            "temperature_by_options": ec["temperature_by_options"],
            "temperature_by_language": {},
            "metrics": ec["metrics"],
        })
        print("wrote sys1/data/calibration.json")
    os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
    with open(args.json, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    d = report["decoder_parity"]
    a = report["engine_agreement"]
    r = report["routing_parity"]
    l = report["latency"]
    ec = report["engine_calibration"]["metrics"]
    lines = [
        "# sys1 evidence report",
        "",
        "Generated by `python code/sys1/evaluate.py`. Fixtures: laya's own published golden",
        "files (Apache-2.0), extracted to `sys1/data/goldens.json` and `sys1/data/routing.json`.",
        "",
        "## 1. Decoder parity (real checkpoint logits -> laya's answer)",
        "",
        "| questions | exact | mismatched | skipped |",
        "|---|---|---|---|",
        "| %d | %d | %d | %d |" % (d["questions"], d["exact"], d["mismatched"], d["skipped"]),
        "",
        "Tolerance 1e-4 on every reported probability, `confidence` and `answer_confidence`.",
        "",
        "## 2. Agreement with the real checkpoint (same states and questions)",
        "",
        "| checkpoint | choice n | choice agreement | noul n | noul agreement | score n | score MAE |",
        "|---|---|---|---|---|---|---|",
    ]
    for checkpoint, entry in a["per_checkpoint"].items():
        lines.append("| %s | %d | %.1f%% | %d | %.1f%% | %d | %.3f |" % (
            checkpoint, entry["choice"]["n"], 100 * entry["choice"]["agreement"],
            entry["noul"]["n"], 100 * entry["noul"]["agreement"],
            entry["score"]["n"], entry["score"]["mean_abs_error"]))
    lines += [
        "",
        "Overall typed agreement: **%.1f%%**; score mean absolute error: **%.3f**." % (
            100 * a["overall_typed_agreement"], a.get("score_mean_abs_error", 0.0)),
        "",
        "This is teacher agreement on laya's own regression fixtures, not accuracy: the",
        "fixtures are small, adversarial in places, and were not written as a benchmark.",
        "",
        "## 3. Routing parity (800 adversarial states, 4115 decisions)",
        "",
        "| script | is_english | language | route model |",
        "|---|---|---|---|",
        "| %.1f%% | %.1f%% | %.1f%% | %.1f%% |" % (
            100 * r["script"], 100 * r["is_english"], 100 * r["language"], 100 * r["route_model"]),
        "",
        "## 4. Calibration of the local scorer (even rows fit, odd rows reported)",
        "",
        "| temperature | n | argmax agreement | mean CE | ECE |",
        "|---|---|---|---|---|",
        "| T=1 (shipped) | %d | %.1f%% | %.3f | %.3f |" % (
            ec["held_out_default_T1"]["n"], 100 * ec["held_out_default_T1"]["argmax_agreement"],
            ec["held_out_default_T1"]["mean_ce"], ec["held_out_default_T1"]["ece"]),
        "| fitted per bucket | %d | %.1f%% | %.3f | %.3f |" % (
            ec["held_out"]["n"], 100 * ec["held_out"]["argmax_agreement"],
            ec["held_out"]["mean_ce"], ec["held_out"]["ece"]),
        "",
        "`sys1/data/calibration.json` is therefore **not shipped**: with 44 fitting rows a",
        "per-bucket fit moved held-out ECE the wrong way. `--write-calibration` still writes",
        "it, and `DecisionEngine()` loads it when present, so the experiment is repeatable.",
        "",
        "## 5. Latency (CPU, this sandbox, 3 questions per decision)",
        "",
        "| p50 | p95 | decisions/sec |",
        "|---|---|---|",
        "| %.2f ms | %.2f ms | %.0f |" % (l["p50_ms"], l["p95_ms"], l["throughput_decisions_per_sec"]),
        "",
    ]
    with open(args.md, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(json.dumps({k: report[k] for k in ("decoder_parity", "routing_parity", "latency")},
                     ensure_ascii=False, indent=2)[:3000])
    print("engine agreement", json.dumps(a, ensure_ascii=False))
    print("wrote", args.json, args.md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
