"""The decision engine: routing -> logits -> laya/Jev decoding -> typed answers.

Two interchangeable sources of logits:

``local``
    :class:`sys1.scoring.LexicalScorer`. No model download, no network, no API
    key, deterministic.

``agent``
    Per-option logits supplied by the calling agent (this conversation, a local
    MCP client, or a decision pack on disk). This is the "use your own ability"
    path: the engine renders laya's exact prompt, the agent scores the options
    with its own reasoning, and every downstream step stays laya's.

Mixing is allowed: ``engine="auto"`` uses agent logits for questions that have
them and the local scorer for the rest.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .decode import (
    TemperatureTable,
    add_jev_confidence,
    apply_confidence_gate,
    decode_answers,
    jev_confidence,
)
from .lang import route_model
from .protocol import (
    QuestionError,
    build_prompt,
    estimate_tokens,
    normalize_questions,
    option_count,
    parse_min_confidence,
    render_options,
    serialize_state,
    state_usage,
)
from .scoring import LexicalScorer, Rubric

VERSION = "1.0.0"
DEFAULT_MODEL_NAME = "sys1-1.0.0"

#: Names laya accepts for its three checkpoints, and the published Hub ids.
MODEL_ALIASES = {
    "english": "english",
    "laya": "english",
    "convaiinnovations/laya": "english",
    "multilingual": "multilingual",
    "ml": "multilingual",
    "laya-multilingual": "multilingual",
    "convaiinnovations/laya-multilingual": "multilingual",
    "typed-decisions": "typed-decisions",
    "typed_decisions": "typed-decisions",
    "laya-typed-decisions": "typed-decisions",
    "convaiinnovations/laya-typed-decisions": "typed-decisions",
}


class NeedsAgentScores(Exception):
    """Raised when the agent engine is selected but no logits were supplied.

    Carries everything the caller needs to answer: the rendered prompt, the
    option order, and the exact response schema.
    """

    def __init__(self, questions: Dict[str, Dict[str, Any]], state: Any,
                 max_len: int, head_max_len: int):
        super().__init__("agent logits are required for this request")
        self.questions = questions
        self.state = state
        self.max_len = max_len
        self.head_max_len = head_max_len

    def payload(self) -> Dict[str, Any]:
        out = {}
        for qid, q in self.questions.items():
            opts = render_options(q)
            out[qid] = {
                "type": q["t"],
                "instructions": q["ins"],
                "options": opts,
                "prompt": build_prompt(self.state, q, self.max_len, self.head_max_len),
                "logits": {
                    "count": len(opts),
                    "meaning": "one finite number per option, in the order shown; higher = more likely",
                },
            }
        return {
            "status": "needs_agent_scores",
            "reason": "engine=agent: score each option yourself, then resend with agent_logits",
            "questions": out,
            "response_schema": {
                "state": "<same state>",
                "questions": "<same questions>",
                "engine": "agent",
                "agent_logits": {"<question id>": [0.0, 1.0, "..."]},
            },
        }


def resolve_model_name(model: Any) -> Optional[str]:
    """Map a client ``model`` value onto our checkpoint label, or None."""
    if model is None:
        return None
    if not isinstance(model, str):
        raise QuestionError("model must be a string")
    text = model.strip()
    if not text:
        return None
    key = text.lower()
    if key in MODEL_ALIASES:
        return MODEL_ALIASES[key]
    if key.startswith("jev-") or key in ("jev", "jev-latest", "jev-preview"):
        return None  # a Jev id means "let routing choose"
    if text[0] in ".~" or "/" in text or "\\" in text:
        raise QuestionError(
            "%r is not a checkpoint this server can load, or omit model to let the router choose"
            % text
        )
    raise QuestionError(
        "%r is not a known checkpoint (english, multilingual, typed-decisions), "
        "or omit model to let the router choose" % text
    )


def _truncate_tokens(text: str, room: int) -> str:
    """Keep the first ``room`` estimated tokens."""
    if room <= 0:
        return ""
    used = 0
    out = []
    for ch in text:
        cost = 1 if (
            0x3040 <= ord(ch) <= 0x30FF
            or 0x3400 <= ord(ch) <= 0x4DBF
            or 0x4E00 <= ord(ch) <= 0x9FFF
            or 0xAC00 <= ord(ch) <= 0xD7AF
            or 0xF900 <= ord(ch) <= 0xFAFF
        ) else 0.25
        if used + cost > room + 1e-9:
            break
        used += cost
        out.append(ch)
    return "".join(out)


class DecisionEngine:
    def __init__(self, temperatures: Optional[TemperatureTable] = None,
                 rubric: Optional[Rubric] = None,
                 model_name: Optional[str] = None,
                 default_route: str = "multilingual",
                 calibration_note: Optional[str] = None):
        if temperatures is None:
            from .calibrate import DEFAULT_PATH, load as _load_calibration
            temperatures = _load_calibration()
            if calibration_note is None:
                calibration_note = "fitted" if os.path.exists(DEFAULT_PATH) else "default"
        self.temperatures = temperatures
        self.scorer = LexicalScorer(rubric or Rubric.load())
        self.model_name = model_name or os.environ.get("SYS1_MODEL_NAME") or DEFAULT_MODEL_NAME
        self.default_route = default_route
        self.calibration_note = calibration_note or "default"

    # ------------------------------------------------------------------ routing
    def route(self, state: Any, questions: Optional[Dict[str, Any]] = None,
              model: Optional[str] = None, task: Optional[str] = None,
              lang: Optional[str] = None, lang_guess: Optional[str] = None) -> Dict[str, Any]:
        pinned = resolve_model_name(model)
        if pinned:
            return {"model": pinned, "reason": "explicit model=%r" % model,
                    "detection": None, "workflow": None}
        if task:
            label = str(task).strip().lower().replace("-", "_")
            if label not in ("english", "multilingual", "typed_decisions", "typed-decisions"):
                raise QuestionError("unknown task %r" % (task,))
            name = "typed-decisions" if label.startswith("typed") else label
            return {"model": name, "reason": "explicit task=%r" % task,
                    "detection": None, "workflow": None}
        decision = route_model(state, lang=lang, lang_guess=lang_guess,
                               default=self.default_route)
        return decision

    # ------------------------------------------------------------------ predict
    def predict(self, state: Any, questions: Dict[str, Any], *,
                model: Optional[str] = None, task: Optional[str] = None,
                lang: Optional[str] = None, lang_guess: Optional[str] = None,
                max_len: int = 512, head_max_len: int = 192,
                min_confidence: Any = None,
                engine: str = "local",
                agent_logits: Optional[Dict[str, Sequence[float]]] = None,
                agent_temperature: float = 1.0,
                include_prompts: bool = False) -> Dict[str, Any]:
        started = time.perf_counter()
        if state is None:
            raise QuestionError("'state' is required")
        if not isinstance(max_len, int) or isinstance(max_len, bool) or max_len <= 0:
            raise QuestionError("max_len must be a positive integer")
        if not isinstance(head_max_len, int) or isinstance(head_max_len, bool) or head_max_len <= 0:
            raise QuestionError("head_max_len must be a positive integer")
        if not isinstance(agent_temperature, (int, float)) or isinstance(agent_temperature, bool) \
                or not float(agent_temperature) > 0:
            raise QuestionError("agent_temperature must be a positive number")
        engine = (engine or "local").lower()
        if engine not in ("local", "agent", "auto"):
            raise QuestionError("engine must be one of local, agent, auto")
        questions = normalize_questions(questions, jev_limits=False)
        if not questions:
            return {
                "model": self.model_name,
                "answers": {},
                "usage": {"input_tokens": 0, "output_tokens": 0},
                "routing": self.route(state, questions, model, task, lang, lang_guess),
                "sys1": {"engine": engine, "version": VERSION, "latency_ms": 0.0},
            }

        decision = self.route(state, questions, model, task, lang, lang_guess)
        state_text = serialize_state(state)
        mc = parse_min_confidence(min_confidence) if min_confidence is not None else None

        supplied = agent_logits or {}
        if engine == "agent" and not supplied:
            raise NeedsAgentScores(questions, state, max_len, head_max_len)
        if engine == "agent":
            missing = [qid for qid in questions if qid not in supplied]
            if missing:
                raise QuestionError("agent_logits missing for %s" % ", ".join(sorted(missing)))

        logits: Dict[str, List[float]] = {}
        engines_used: Dict[str, str] = {}
        for qid, q in questions.items():
            k = option_count(q)
            if qid in supplied:
                values = supplied[qid]
                if not isinstance(values, (list, tuple)) or len(values) != k:
                    raise QuestionError(
                        "agent_logits[%r] must be a list of %d numbers" % (qid, k)
                    )
                try:
                    vals = [float(v) for v in values]
                except (TypeError, ValueError):
                    raise QuestionError("agent_logits[%r] contains a non-number" % (qid,)) from None
                logits[qid] = vals
                engines_used[qid] = "agent"
            else:
                room = max(0, max_len - 64 - 2)
                visible = _truncate_tokens(state_text, room)
                logits[qid] = self.scorer.score(visible, q)
                engines_used[qid] = "local"

        overrides = {qid: float(agent_temperature) for qid in supplied if qid in questions}
        answers = decode_answers(questions, logits, self.temperatures,
                                 lang=lang, act_logits=None, temperature_overrides=overrides)
        usage = self._aggregate_usage(questions, state_text, max_len, head_max_len)
        result: Dict[str, Any] = {
            "model": self.model_name,
            "answers": answers,
            "usage": usage,
            "routing": decision,
        }
        if include_prompts:
            result["prompts"] = {qid: build_prompt(state, q, max_len, head_max_len)
                                 for qid, q in questions.items()}
        result = add_jev_confidence(result)
        apply_confidence_gate(result, mc)
        result["sys1"] = {
            "engine": engine,
            "engines_used": engines_used,
            "version": VERSION,
            "calibration": self.calibration_note,
            "latency_ms": round((time.perf_counter() - started) * 1000.0, 3),
            "logits": {qid: [round(v, 4) for v in vals] for qid, vals in logits.items()},
            "tokenizer": "estimate",
        }
        return result

    def predict_batch(self, states: Sequence[Any], questions: Dict[str, Any], *,
                      model: Optional[str] = None, task: Optional[str] = None,
                      lang: Optional[str] = None, lang_guess: Optional[str] = None,
                      max_len: int = 512, head_max_len: int = 192,
                      min_confidence: Any = None, engine: str = "local",
                      agent_logits: Optional[Dict[str, Dict[str, Sequence[float]]]] = None,
                      agent_temperature: float = 1.0,
                      include_prompts: bool = False) -> Dict[str, Any]:
        if not isinstance(states, (list, tuple)) or not states:
            raise QuestionError("'states' must be a non-empty list")
        if any(s is None for s in states):
            raise QuestionError("state must not be None; pass a string, dict, or list")
        started = time.perf_counter()
        results = []
        for index, state in enumerate(states):
            per_state = None
            if agent_logits is not None:
                per_state = agent_logits.get(str(index))
                if per_state is None:
                    per_state = agent_logits.get(index)  # type: ignore[arg-type]
            results.append(self.predict(
                state, questions, model=model, task=task, lang=lang, lang_guess=lang_guess,
                max_len=max_len, head_max_len=head_max_len, min_confidence=min_confidence,
                engine=engine, agent_logits=per_state, agent_temperature=agent_temperature,
                include_prompts=include_prompts,
            ))
        total_in = sum(int(r.get("usage", {}).get("input_tokens", 0)) for r in results)
        total_out = sum(int(r.get("usage", {}).get("output_tokens", 0)) for r in results)
        return {
            "results": results,
            "total_usage": {"input_tokens": total_in, "output_tokens": total_out},
            "sys1": {
                "engine": engine,
                "version": VERSION,
                "latency_ms": round((time.perf_counter() - started) * 1000.0, 3),
            },
        }

    # ------------------------------------------------------------------ helpers
    def _aggregate_usage(self, questions: Dict[str, Dict[str, Any]], state_text: str,
                         max_len: int, head_max_len: int) -> Dict[str, Any]:
        per_q = []
        for qid, q in questions.items():
            q = dict(q)
            q["_id"] = qid
            per_q.append(state_usage(q, state_text, max_len, head_max_len))
        input_tokens = sum(u["input_tokens"] for u in per_q)
        state_tokens = max(u["state_tokens"] for u in per_q)
        dropped = max(u["state_tokens_dropped"] for u in per_q)
        truncated = [qid for qid, u in zip(questions, per_q) if u["truncated"]]
        usage: Dict[str, Any] = {
            "input_tokens": input_tokens,
            "output_tokens": 0,
            "state_tokens": state_tokens,
            "state_tokens_dropped": dropped,
            "truncated": bool(truncated),
            "truncated_questions": truncated,
        }
        options = {}
        for qid, u in zip(questions, per_q):
            if "options" in u:
                options.update(u["options"])
        if options:
            usage["options"] = options
        return usage


__all__ = [
    "DecisionEngine", "NeedsAgentScores", "resolve_model_name", "VERSION",
    "MODEL_ALIASES", "jev_confidence",
]
