"""Command line: decide, serve, mcp, route, prompt, eval, selfcheck."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Optional

from .engine import DecisionEngine, NeedsAgentScores, VERSION
from .protocol import build_prompt, normalize_questions


def _read(value: Optional[str]) -> Any:
    if value is None:
        return None
    if value == "-":
        return sys.stdin.read()
    if value.startswith("@"):
        with open(value[1:], "r", encoding="utf-8") as fh:
            return fh.read()
    return value


def _json_arg(value: Optional[str]) -> Any:
    text = _read(value)
    if text is None:
        return None
    if isinstance(text, (dict, list)):
        return text
    try:
        return json.loads(text)
    except ValueError:
        path = value[1:] if value and value.startswith("@") else value
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)


def _print_result(result: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print("routing : %s (%s)" % (result["routing"]["model"], result["routing"]["reason"]))
    for qid, answer in result["answers"].items():
        if answer["type"] == "choice":
            probs = ", ".join("%s=%.3f" % (k, v) for k, v in answer["probabilities"].items())
            print("%-10s choice=%s  %s" % (qid, answer["choice"], probs))
        elif answer["type"] == "score":
            print("%-10s score=%.3f  legend=%s" % (qid, answer["score"], answer["legend"]))
        else:
            print("%-10s noul=%.3f" % (qid, answer["noul"]))
        extras = "confidence=%s" % answer.get("answer_confidence")
        if answer.get("x_jev_confidence") is not None:
            extras += " jev=%s" % answer["x_jev_confidence"]
        if answer.get("low_confidence"):
            extras += " LOW_CONFIDENCE"
        print("           %s" % extras)
    print("engine  : %s, %s ms, calibration=%s"
          % (result["sys1"]["engine"], result["sys1"]["latency_ms"], result["sys1"]["calibration"]))


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(prog="sys1", description="Local System One decisions (laya/Jev compatible)")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("decide", help="answer typed questions over a state")
    p.add_argument("--state", default="-", help="text, @file, or - for stdin (default)")
    p.add_argument("--questions", required=True, help="@questions.json (question id -> definition)")
    p.add_argument("--engine", default="local", choices=["local", "agent", "auto"])
    p.add_argument("--agent-logits", help="@logits.json mapping question id to one number per option")
    p.add_argument("--model")
    p.add_argument("--task")
    p.add_argument("--lang")
    p.add_argument("--lang-guess")
    p.add_argument("--max-len", type=int, default=512)
    p.add_argument("--head-max-len", type=int, default=192)
    p.add_argument("--min-confidence")
    p.add_argument("--prompt", action="store_true", help="print laya's rendered prompt too")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("route", help="routing decision only")
    p.add_argument("--state", default="-")
    p.add_argument("--model")
    p.add_argument("--task")
    p.add_argument("--lang")
    p.add_argument("--lang-guess")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("prompt", help="render laya's prompt")
    p.add_argument("--state", default="-")
    p.add_argument("--questions", required=True)
    p.add_argument("--max-len", type=int, default=512)
    p.add_argument("--head-max-len", type=int, default=192)

    p = sub.add_parser("serve", help="Jev-compatible HTTP server")
    p.add_argument("--host", default=os.environ.get("SYS1_HOST", "0.0.0.0"))
    p.add_argument("--port", type=int, default=int(os.environ.get("SYS1_PORT", "8000")))

    sub.add_parser("mcp", help="MCP server over stdio")
    sub.add_parser("version")

    p = sub.add_parser("eval", help="run the evidence report")
    p.add_argument("--json", default=os.path.join(os.path.dirname(__file__), "..", "..", "results", "sys1", "EVAL.json"))
    p.add_argument("--md", default=os.path.join(os.path.dirname(__file__), "..", "..", "results", "sys1", "EVAL.md"))

    p = sub.add_parser("selfcheck", help="offline self-check")
    p.add_argument("--local", action="store_true")
    p.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    if args.command == "version":
        print("sys1 %s (calibration: %s)" % (VERSION, DecisionEngine().calibration_note))
        return 0
    if args.command == "serve":
        from .serve import create_server
        server = create_server(args.host, args.port)
        print("sys1 %s on http://%s:%d" % (VERSION, args.host, args.port))
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return 0
    if args.command == "mcp":
        from .mcp import main as mcp_main
        return mcp_main()

    engine = DecisionEngine()
    if args.command == "decide":
        state = _read(args.state)
        questions = _json_arg(args.questions)
        logits = _json_arg(args.agent_logits) if args.agent_logits else None
        try:
            result = engine.predict(
                state, questions, engine=args.engine, agent_logits=logits,
                model=args.model, task=args.task, lang=args.lang, lang_guess=args.lang_guess,
                max_len=args.max_len, head_max_len=args.head_max_len,
                min_confidence=args.min_confidence, include_prompts=args.prompt)
        except NeedsAgentScores as exc:
            print(json.dumps(exc.payload(), ensure_ascii=False, indent=2))
            return 3
        _print_result(result, args.json)
        if args.prompt and not args.json:
            for qid, prompt in result.get("prompts", {}).items():
                print("\n## %s\n%s" % (qid, prompt))
        return 0
    if args.command == "route":
        decision = engine.route(_read(args.state), model=args.model, task=args.task,
                                lang=args.lang, lang_guess=args.lang_guess)
        print(json.dumps(decision, ensure_ascii=False, indent=2) if args.json else
              "%s: %s" % (decision["model"], decision["reason"]))
        return 0
    if args.command == "prompt":
        questions = normalize_questions(_json_arg(args.questions))
        state = _read(args.state)
        for qid, q in questions.items():
            print("## %s\n%s\n" % (qid, build_prompt(state, q, args.max_len, args.head_max_len)))
        return 0
    if args.command == "eval":
        import subprocess
        script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "evaluate.py")
        return subprocess.call([sys.executable, script, "--json", args.json, "--md", args.md])
    if args.command == "selfcheck":
        import subprocess
        script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "selfcheck.py")
        cmd = [sys.executable, script]
        if args.local:
            cmd.append("--local")
        if args.json:
            cmd.append("--json")
        return subprocess.call(cmd)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
