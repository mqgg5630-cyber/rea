"""Laya-compatible question protocol: validation, rendering, budgets, usage.

This module is a clean-room reimplementation of the *observable* protocol of
``laya`` 0.4.13 (Apache-2.0), reconstructed from ``laya/common.py`` and from the
golden fixtures in ``laya-dotnet/tests/Laya.Tests/golden`` published by the same
project. No laya source code is copied; the constants and rendering rules are
facts about the wire/prompt contract.

The one deliberate divergence: laya budgets in BPE tokens, and the checkpoint's
tokenizer is not part of this repository. ``estimate_tokens`` is a documented
character-class proxy used only for ``usage`` and truncation reports, never for
deciding an answer.
"""

from __future__ import annotations

import json
import math
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

QTYPES = {"choice": 0, "score": 1, "noul": 2}
QTYPE_NAMES = {v: k for k, v in QTYPES.items()}
DEFAULT_NOUL_LABELS = {"false": "false", "true": "true"}

#: laya-serve's amplification guard (MAX_CHOICE_OPTIONS).
MAX_CHOICE_OPTIONS = 100
#: Jev's published maxima.
JEV_MAX_CHOICE = 255
JEV_MAX_SCORE = 10
MAX_QUESTIONS = 100

#: laya's per-option token cap inside the head (`max_length=48`).
PER_OPTION_MAX = 48
#: The floor laya leaves the instruction (`head_ids[:max(8, opt_budget)]`).
MIN_INSTRUCTION_TOKENS = 8


class QuestionError(ValueError):
    """A caller-supplied question or state is unusable."""


def serialize_state(state: Any) -> str:
    """laya's state serialization: strings pass through, everything else is JSON."""
    if isinstance(state, str):
        return state
    if isinstance(state, (bytes, bytearray)):
        return bytes(state).decode("utf-8", "replace")
    try:
        return json.dumps(state, ensure_ascii=False)
    except (TypeError, ValueError) as exc:  # circular or non-serializable
        raise QuestionError("'state' must be JSON-serializable") from exc


def render_criterion(value: Any) -> str:
    """Render one criterion value (laya/common.py: render_criterion)."""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, separators=(", ", ": "), default=str)
    except (TypeError, ValueError):
        return str(value)


def resolve_noul_labels(labels: Any) -> Tuple[str, str]:
    if labels is None:
        labels = DEFAULT_NOUL_LABELS
    if not isinstance(labels, dict) or set(labels) != {"false", "true"}:
        raise QuestionError(
            "noul labels must map exactly 'false' and 'true' to distinct non-empty strings"
        )
    false_label, true_label = labels["false"], labels["true"]
    if not isinstance(false_label, str) or not isinstance(true_label, str):
        raise QuestionError(
            "noul labels must map exactly 'false' and 'true' to distinct non-empty strings"
        )
    false_label, true_label = false_label.strip(), true_label.strip()
    if not false_label or not true_label or false_label == true_label:
        raise QuestionError(
            "noul labels must map exactly 'false' and 'true' to distinct non-empty strings"
        )
    return false_label, true_label


def normalize_question(qid: str, qdef: Any, *, jev_limits: bool = False) -> Dict[str, Any]:
    """Validate one question and return laya's internal representation.

    ``{"t": type, "ins": instructions, "crit": criteria-or-None, ...}``
    """
    if not isinstance(qdef, dict):
        raise QuestionError("question %r must be an object" % (qid,))
    kind = qdef.get("type")
    if kind not in QTYPES:
        raise QuestionError(
            "question %r: type must be one of choice, score, noul, got %r" % (qid, kind)
        )
    if "instructions" not in qdef:
        raise QuestionError("question %r is missing 'instructions'" % (qid,))
    ins = qdef["instructions"]
    if not isinstance(ins, str):
        ins = json.dumps(ins, ensure_ascii=False)

    crit = qdef.get("criteria")
    if kind == "choice":
        if crit is None:
            raise QuestionError("question %r is a choice but has no criteria" % (qid,))
        if isinstance(crit, (list, tuple)):
            crit = {str(c): None for c in crit}
        if not isinstance(crit, dict) or len(crit) < 1:
            raise QuestionError("question %r: choice criteria must be a non-empty object or list" % (qid,))
        limit = JEV_MAX_CHOICE if jev_limits else MAX_CHOICE_OPTIONS
        if len(crit) > limit:
            raise QuestionError(
                "question %r has %d options, over the %d-option limit" % (qid, len(crit), limit)
            )
        crit = {str(k): v for k, v in crit.items()}
    elif kind == "score":
        if not isinstance(crit, (list, tuple)):
            raise QuestionError("question %r: score criteria must be an ordered array" % (qid,))
        if len(crit) < 2:
            raise QuestionError("question %r: a score needs at least two levels" % (qid,))
        if jev_limits and len(crit) > JEV_MAX_SCORE:
            raise QuestionError(
                "question %r: a score accepts at most %d levels" % (qid, JEV_MAX_SCORE)
            )
        crit = list(crit)
    else:
        if crit is None:
            crit = {}
        if not isinstance(crit, dict):
            raise QuestionError("question %r: noul criteria must be an object" % (qid,))
        crit = {str(k).lower(): v for k, v in crit.items()}
        if set(crit) - {"true", "false"}:
            raise QuestionError(
                "question %r: noul criteria may only name 'true' and 'false'" % (qid,)
            )
        labels = qdef.get("labels")
        if labels is not None:
            resolve_noul_labels(labels)

    out: Dict[str, Any] = {"t": kind, "ins": ins, "crit": crit}
    if kind == "noul" and "labels" in qdef:
        out["labels"] = qdef["labels"]
    if "option_order" in qdef:
        out["option_order"] = [int(i) for i in qdef["option_order"]]
    return out


def render_options(q: Dict[str, Any]) -> List[str]:
    """The option texts laya puts behind one ``[MASK]`` each."""
    kind, crit = q["t"], q.get("crit")
    if kind == "choice":
        return [
            str(k) if v is None or v == "" else "%s: %s" % (k, render_criterion(v))
            for k, v in crit.items()
        ]
    if kind == "score":
        return ["level %d: %s" % (i, render_criterion(c)) for i, c in enumerate(crit)]
    false_label, true_label = resolve_noul_labels(q.get("labels"))
    crit = crit or {}
    false_crit, true_crit = crit.get("false"), crit.get("true")
    return [
        false_label + ": "
        + (render_criterion(false_crit) if false_crit not in (None, "") else "no, the statement does not hold"),
        true_label + ": "
        + (render_criterion(true_crit) if true_crit not in (None, "") else "yes, the statement holds"),
    ]


def head_text(q: Dict[str, Any]) -> str:
    """laya's head prefix: ``"%s question: %s" % (type, instructions)``."""
    return "%s question: %s" % (q["t"], q["ins"])


def marker_positions(q: Dict[str, Any], head_max_len: int = 192) -> List[int]:
    """Approximate token positions of the option markers inside the head.

    Mirrors laya/common.py:build_head with ``estimate_tokens`` in place of the
    checkpoint tokenizer, so budgets and truncation reports have the same shape.
    """
    opts = render_options(q)
    head_len = estimate_tokens(head_text(q))
    opt_lengths = [1 + min(PER_OPTION_MAX, estimate_tokens(" " + o)) for o in opts]
    opt_budget = head_max_len - sum(opt_lengths)
    per_option = None
    if opt_budget < 16:
        per_option = max(4, (head_max_len - 16) // max(1, len(opt_lengths)))
        opt_lengths = [min(n, per_option) for n in opt_lengths]
        opt_budget = head_max_len - sum(opt_lengths)
    head_len = min(head_len, max(MIN_INSTRUCTION_TOKENS, opt_budget))
    pos = 1 + head_len + 1  # [CLS] + instruction + [SEP]
    markers = []
    for n in opt_lengths:
        markers.append(pos)
        pos += n
    return markers


def option_stats(q: Dict[str, Any], head_max_len: int = 192) -> Dict[str, Any]:
    """``{options, options_distinct, tokens_per_option}`` as laya reports them."""
    opts = render_options(q)
    rendered = [" " + o for o in opts]
    lengths = [1 + min(PER_OPTION_MAX, estimate_tokens(t)) for t in rendered]
    per_option = None
    if head_max_len - sum(lengths) < 16:
        per_option = max(4, (head_max_len - 16) // max(1, len(lengths)))
        lengths = [min(n, per_option) for n in lengths]
    return {
        "options": len(opts),
        "options_distinct": len({" ".join(o.split()) for o in opts}),
        "tokens_per_option": per_option,
    }


def state_room(q: Dict[str, Any], max_len: int = 512, head_max_len: int = 192) -> int:
    """Tokens left for the state after this question's head and closing separators."""
    markers = marker_positions(q, head_max_len)
    head_end = (markers[-1] + 1) if markers else 0
    return max(0, max_len - head_end - 2)


def estimate_tokens(text: str) -> int:
    """A tokenizer-free token estimate.

    CJK/kana/hangul characters count as one token each, other characters as
    ``ceil(len/4)``. Calibrated so English prose lands near ModernBERT's BPE
    length (within ~10% on the laya goldens) and CJK near one token per
    character. Used for budgets and usage only.
    """
    if not text:
        return 0
    wide = 0
    for ch in text:
        cp = ord(ch)
        if (
            0x3040 <= cp <= 0x30FF
            or 0x3400 <= cp <= 0x4DBF
            or 0x4E00 <= cp <= 0x9FFF
            or 0xAC00 <= cp <= 0xD7AF
            or 0xF900 <= cp <= 0xFAFF
        ):
            wide += 1
    narrow = len(text) - wide
    return wide + int(math.ceil(narrow / 4.0))


def build_prompt(state: Any, q: Dict[str, Any], max_len: int = 512, head_max_len: int = 192) -> str:
    """Render laya's sequence layout as text.

    ``[CLS] <type> question: <instructions> [SEP] [MASK] opt0 [MASK] opt1 ... [SEP] state [SEP]``

    A real forward pass uses token ids; this string is the same layout with the
    tokenizer's special tokens spelled out, so an agent can read the exact
    prompt the checkpoint sees.
    """
    opts = render_options(q)
    room_chars = max(0, state_room(q, max_len, head_max_len) * 4)
    st = serialize_state(state)
    if len(st) > room_chars:
        st = st[:room_chars]
    parts = ["[CLS]", head_text(q), "[SEP]"]
    for o in opts:
        parts.extend(["[MASK]", o])
    parts.extend(["[SEP]", st, "[SEP]"])
    return " ".join(parts)


def state_usage(q: Dict[str, Any], state_text: str, max_len: int = 512,
                head_max_len: int = 192) -> Dict[str, Any]:
    """The ``usage`` block for one question over one state."""
    markers = marker_positions(q, head_max_len)
    head_end = (markers[-1] + 1) if markers else 2
    room = max(0, max_len - head_end - 2)
    state_tokens = estimate_tokens(state_text)
    used = min(room, state_tokens)
    dropped = state_tokens - used
    stats = option_stats(q, head_max_len)
    collapsed = {}
    if stats["options_distinct"] < stats["options"]:
        collapsed[q.get("_id", "q")] = {
            "total": stats["options"],
            "distinct": stats["options_distinct"],
            "tokens_per_option": stats["tokens_per_option"],
        }
    usage: Dict[str, Any] = {
        "input_tokens": head_end + used + 1,
        "output_tokens": 0,
        "state_tokens": state_tokens,
        "state_tokens_dropped": dropped,
        "truncated": dropped > 0,
        "truncated_questions": [q["_id"]] if dropped > 0 else [],
    }
    if collapsed:
        usage["options"] = collapsed
    return usage


def estimate_agreeing_tokens(text: str) -> int:
    """Alias kept for readability in reports."""
    return estimate_tokens(text)


_TOKEN_SAFE = set(" \t\r\n[](){}<>:;,./\\-_=+*&^%$#@!?\"'`|~")


def render_prompt_plain(state: Any, q: Dict[str, Any]) -> str:
    """A lossless, single-line rendering for logs (no truncation)."""
    opts = render_options(q)
    body = " | ".join("[MASK] " + o for o in opts)
    st = serialize_state(state)
    return "[CLS] %s [SEP] %s [SEP] %s [SEP]" % (head_text(q), body, st)


def normalize_questions(questions: Any, *, jev_limits: bool = False) -> Dict[str, Dict[str, Any]]:
    if not isinstance(questions, dict):
        raise QuestionError("questions must be a dict of question id -> definition")
    if len(questions) > MAX_QUESTIONS:
        raise QuestionError("at most %d questions per request" % MAX_QUESTIONS)
    out: Dict[str, Dict[str, Any]] = {}
    for qid, qdef in questions.items():
        q = normalize_question(qid, qdef, jev_limits=jev_limits)
        q["_id"] = qid
        out[qid] = q
    return out


def option_count(q: Dict[str, Any]) -> int:
    if q["t"] == "noul":
        return 2
    return len(q["crit"])


def answer_kind(q: Dict[str, Any]) -> str:
    return q["t"]


def temp_bucket(kind: str, k: int) -> str:
    size = "2" if k <= 2 else "3-5" if k <= 5 else "6-10" if k <= 10 else "11+"
    return "%s:%s" % (kind, size)


def valid_bucket(key: str) -> bool:
    return key in {"%s:%s" % (t, s) for t in ("choice", "score", "noul")
                   for s in ("2", "3-5", "6-10", "11+")} or key == "default"


def parse_min_confidence(value: Any) -> Any:
    """Validate laya's scalar-or-per-bucket ``min_confidence``."""
    def one(v: Any) -> float:
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise QuestionError("min_confidence must be a float in [0.0, 1.0], got %r" % (v,))
        if v < 0.0 or v > 1.0:
            raise QuestionError("min_confidence must be a float in [0.0, 1.0], got %r" % (v,))
        return float(v)

    if isinstance(value, dict):
        if not value:
            raise QuestionError("a min_confidence map must be a non-empty dict")
        out = {}
        for key, val in value.items():
            if not isinstance(key, str) or not valid_bucket(key):
                raise QuestionError(
                    "min_confidence map keys must be a bucket like 'choice:3-5' or 'default', got %r"
                    % (key,)
                )
            out[key] = one(val)
        return out
    return one(value)


def iter_text(state: Any, max_chars: int = 4000) -> str:
    """String leaves of a state, keys ignored (laya/lang.py:state_text)."""
    parts: List[str] = []
    budget = max_chars

    def walk(node: Any, depth: int = 0) -> None:
        nonlocal budget
        if depth > 6 or budget <= 0:
            return
        if isinstance(node, str):
            parts.append(node[:budget])
            budget -= len(node) + 1
        elif isinstance(node, dict):
            for v in node.values():
                walk(v, depth + 1)
        elif isinstance(node, (list, tuple)):
            for v in node:
                walk(v, depth + 1)

    walk(state)
    return " ".join(parts)[:max_chars]


def normalize_text(text: str) -> str:
    """NFKC + casefold, the normalization every lexical layer shares."""
    return unicodedata.normalize("NFKC", text).casefold()


def round4(value: float) -> float:
    return round(float(value), 4)


def clamp(value: float, lo: float, hi: float) -> float:
    return lo if value < lo else hi if value > hi else value


__all__ = [
    "QTYPES", "QTYPE_NAMES", "DEFAULT_NOUL_LABELS", "MAX_CHOICE_OPTIONS",
    "JEV_MAX_CHOICE", "JEV_MAX_SCORE", "QuestionError", "serialize_state",
    "render_criterion", "render_options", "head_text", "normalize_question",
    "normalize_questions", "build_prompt", "render_prompt_plain", "state_usage",
    "state_room", "marker_positions", "option_stats", "estimate_tokens",
    "temp_bucket", "parse_min_confidence", "iter_text", "normalize_text",
    "round4", "clamp", "option_count",
]
