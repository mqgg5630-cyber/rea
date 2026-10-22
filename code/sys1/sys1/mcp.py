"""MCP server over stdio (JSON-RPC 2.0), standard library only.

    python -m sys1 mcp

Tools
-----
``system_one``
    A laya-compatible decision. With ``engine="agent"`` and no
    ``agent_logits`` the call returns laya's rendered prompts and the exact
    response schema, so the calling agent can score the options itself and
    resend. That is the API-free "your ability is the model" path.
``system_one_local``
    The deterministic offline engine, one call.
``system_one_route``
    Routing only (no inference).
``system_one_prompt``
    The rendered prompt laya would feed the checkpoint.
``system_one_health``
    Version, calibration, dependency audit.

No network, no API key: MCP is a pipe to the client.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional

from .engine import DecisionEngine, NeedsAgentScores, VERSION

PROTOCOL_VERSION = "2024-11-05"

_QUESTIONS_SCHEMA = {
    "type": "object",
    "description": "question id -> {type: choice|score|noul, instructions, criteria, labels?}",
    "additionalProperties": {
        "type": "object",
        "required": ["type", "instructions"],
        "properties": {
            "type": {"enum": ["choice", "score", "noul"]},
            "instructions": {},
            "criteria": {},
            "labels": {"type": "object"},
            "option_order": {"type": "array", "items": {"type": "integer"}},
        },
    },
}

_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "system_one",
        "description": (
            "Typed decision (choice / score / noul) over any state, in laya's protocol and "
            "Jev's wire shape. engine=local runs the offline scorer; engine=agent lets the "
            "calling model supply one logit per option (the engine returns the rendered prompt "
            "and schema first when agent_logits is absent)."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["state", "questions"],
            "properties": {
                "state": {"description": "text, JSON object, or conversation turn list"},
                "questions": _QUESTIONS_SCHEMA,
                "model": {"type": "string"},
                "task": {"type": "string"},
                "lang": {"type": "string"},
                "lang_guess": {"type": "string"},
                "max_len": {"type": "integer"},
                "head_max_len": {"type": "integer"},
                "min_confidence": {},
                "engine": {"enum": ["local", "agent", "auto"]},
                "agent_logits": {"type": "object"},
                "include_prompts": {"type": "boolean"},
            },
        },
    },
    {
        "name": "system_one_local",
        "description": "Same as system_one with engine=local.",
        "inputSchema": {
            "type": "object",
            "required": ["state", "questions"],
            "properties": {
                "state": {}, "questions": _QUESTIONS_SCHEMA, "lang": {"type": "string"},
                "min_confidence": {},
            },
        },
    },
    {
        "name": "system_one_route",
        "description": "Which laya checkpoint would take this state, and why.",
        "inputSchema": {
            "type": "object",
            "required": ["state"],
            "properties": {
                "state": {}, "model": {"type": "string"}, "task": {"type": "string"},
                "lang": {"type": "string"}, "lang_guess": {"type": "string"},
            },
        },
    },
    {
        "name": "system_one_prompt",
        "description": "Render laya's exact [CLS] instruction [SEP] [MASK] option ... [SEP] state [SEP] prompt.",
        "inputSchema": {
            "type": "object",
            "required": ["state", "questions"],
            "properties": {"state": {}, "questions": _QUESTIONS_SCHEMA,
                           "max_len": {"type": "integer"},
                           "head_max_len": {"type": "integer"}},
        },
    },
    {
        "name": "system_one_health",
        "description": "Version, calibration, engine mode and the offline audit.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


class Server:
    def __init__(self, engine: Optional[DecisionEngine] = None, stdin=None, stdout=None):
        self.engine = engine or DecisionEngine()
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout

    # ------------------------------------------------------------------ transport
    def send(self, payload: Dict[str, Any]) -> None:
        self.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.stdout.flush()

    def result(self, msg_id: Any, result: Any) -> None:
        self.send({"jsonrpc": "2.0", "id": msg_id, "result": result})

    def error(self, msg_id: Any, code: int, message: str) -> None:
        self.send({"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}})

    def text(self, payload: Any) -> Dict[str, Any]:
        return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
                "isError": False}

    def serve(self) -> int:
        for line in self.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except ValueError:
                self.error(None, -32700, "parse error")
                continue
            if not isinstance(message, dict):
                self.error(None, -32600, "invalid request")
                continue
            self.handle(message)
        return 0

    def handle(self, message: Dict[str, Any]) -> None:
        method = message.get("method")
        msg_id = message.get("id")
        if msg_id is None:  # notification
            return
        if method == "initialize":
            self.result(msg_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "sys1", "version": VERSION},
                "instructions": ("Local System One decisions. engine=agent returns laya's prompt "
                                 "for you to score; nothing leaves this machine."),
            })
        elif method == "ping":
            self.result(msg_id, {})
        elif method == "tools/list":
            self.result(msg_id, {"tools": _TOOLS})
        elif method == "tools/call":
            params = message.get("params") or {}
            name = params.get("name")
            args = params.get("arguments") or {}
            if not isinstance(args, dict):
                self.error(msg_id, -32602, "arguments must be an object")
                return
            try:
                payload = self.call(name, args)
            except NeedsAgentScores as exc:
                self.result(msg_id, self.text(exc.payload()))
            except (KeyError, TypeError, ValueError) as exc:
                self.result(msg_id, {"content": [{"type": "text", "text": str(exc)}], "isError": True})
            except Exception as exc:  # noqa: BLE001
                self.result(msg_id, {"content": [{"type": "text", "text": "internal error: %r" % (exc,)}],
                                     "isError": True})
            else:
                self.result(msg_id, self.text(payload))
        else:
            self.error(msg_id, -32601, "method not found: %s" % method)

    # ------------------------------------------------------------------ tools
    def call(self, name: Optional[str], args: Dict[str, Any]) -> Any:
        if name == "system_one":
            return self.engine.predict(
                args["state"], args["questions"],
                model=args.get("model"), task=args.get("task"),
                lang=args.get("lang"), lang_guess=args.get("lang_guess"),
                max_len=args.get("max_len", 512), head_max_len=args.get("head_max_len", 192),
                min_confidence=args.get("min_confidence"),
                engine=args.get("engine", "local"),
                agent_logits=args.get("agent_logits"),
                include_prompts=bool(args.get("include_prompts", False)),
            )
        if name == "system_one_local":
            return self.engine.predict(
                args["state"], args["questions"], lang=args.get("lang"),
                min_confidence=args.get("min_confidence"), engine="local")
        if name == "system_one_route":
            return self.engine.route(args["state"], model=args.get("model"),
                                     task=args.get("task"), lang=args.get("lang"),
                                     lang_guess=args.get("lang_guess"))
        if name == "system_one_prompt":
            from .protocol import build_prompt, normalize_questions
            questions = normalize_questions(args["questions"])
            return {qid: build_prompt(args["state"], q, args.get("max_len", 512),
                                      args.get("head_max_len", 192))
                    for qid, q in questions.items()}
        if name == "system_one_health":
            from .selfcheck import audit
            return {"version": VERSION, "calibration": self.engine.calibration_note,
                    "temperatures": self.engine.temperatures.as_dict(),
                    "offline": audit()}
        raise ValueError("unknown tool: %s" % (name,))


def main(argv: Optional[List[str]] = None) -> int:
    return Server().serve()


if __name__ == "__main__":
    raise SystemExit(main())
