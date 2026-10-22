"""Decision decoding and confidence, matching laya 0.4.13.

Every formula here was checked against real checkpoint logits: for all 87
unambiguous question rows in laya's published golden fixtures, recomputing from
``logits`` + the checkpoint's fitted temperatures reproduces laya's reported
probabilities, scores, `confidence` and `answer_confidence` to four decimals.

Formulas (laya/common.py, laya/confidence.py):

* probabilities = softmax(logits / T_bucket)
* choice/score `confidence` = 1 - H(p) / log(k)   (normalized entropy)
* noul `confidence` = max(p_yes, p_no)
* `answer_confidence` = max(p)                    (the calibrated quantity)
* Jev choice confidence = (p_max - 1/n) / (1 - 1/n)
* Jev score confidence = max(0, 1 - spread / uniform_spread)
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

from .protocol import (
    QTYPE_NAMES,
    QuestionError,
    option_count,
    render_criterion,
    round4,
    temp_bucket,
)


class TemperatureTable:
    """Per-checkpoint, per-bucket temperatures, clamped exactly like laya.

    laya refuses a fitted temperature outside [0.5, 5.0] (`clamp_temperature`)
    because a sub-0.5 value turns a coin flip into a claimed certainty.
    """

    MIN = 0.5
    MAX = 5.0

    def __init__(self, by_bucket: Optional[Dict[str, float]] = None,
                 by_type: Optional[Dict[str, float]] = None,
                 by_language: Optional[Dict[str, Dict[str, Any]]] = None):
        self.by_bucket = {k: self._clamp(v) for k, v in (by_bucket or {}).items()}
        if isinstance(by_type, (list, tuple)):
            # laya's checkpoint config stores [choice, score, noul].
            names = ("choice", "score", "noul")
            self.by_type = {name: self._clamp(v) for name, v in zip(names, by_type)}
        else:
            self.by_type = {k: self._clamp(v) for k, v in (by_type or {}).items()}
        self.by_language = by_language or {}

    @classmethod
    def _clamp(cls, value: Any) -> float:
        try:
            v = float(value)
        except (TypeError, ValueError):
            return 1.0
        if not math.isfinite(v):
            return 1.0
        return cls.MIN if v < cls.MIN else cls.MAX if v > cls.MAX else v

    def get(self, kind: str, options: int, lang: Optional[str] = None) -> float:
        if lang:
            base = str(lang).split("-")[0].lower()
            if base in self.by_language:
                entry = self.by_language[base]
                bucket = (entry.get("temperature_by_options") or {})
                if temp_bucket(kind, options) in bucket:
                    return self._clamp(bucket[temp_bucket(kind, options)])
                by_type = entry.get("temperature") or {}
                if kind in by_type:
                    return self._clamp(by_type[kind])
        key = temp_bucket(kind, options)
        if key in self.by_bucket:
            return self.by_bucket[key]
        if kind in self.by_type:
            return self.by_type[kind]
        return 1.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "temperature": dict(self.by_type),
            "temperature_by_options": dict(self.by_bucket),
            "temperature_by_language": self.by_language,
            "clamp": [self.MIN, self.MAX],
        }


def softmax(logits: Sequence[float], temperature: float = 1.0) -> List[float]:
    if not logits:
        return []
    t = TemperatureTable._clamp(temperature)
    z = [float(v) / t for v in logits]
    m = max(z)
    exps = [math.exp(v - m) for v in z]
    total = sum(exps)
    if not math.isfinite(total) or total <= 0:
        return [1.0 / len(z)] * len(z)
    return [v / total for v in exps]


def confidence_from_probs(probs: Sequence[float], k: int) -> float:
    """Normalized Shannon entropy confidence (laya confidence_from_probs)."""
    if k < 2:
        return 1.0
    pk = list(probs[:k])
    entropy = -sum(v * math.log(min(max(v, 1e-12), 1.0)) for v in pk)
    score = 1.0 - entropy / math.log(k)
    return 0.0 if score < 0.0 else 1.0 if score > 1.0 else score


def answer_confidence(probs: Sequence[float], k: int) -> float:
    if k < 1:
        return 1.0
    val = float(max(probs[:k]))
    return 0.0 if val < 0.0 else 1.0 if val > 1.0 else val


def jev_confidence(answer: Dict[str, Any]) -> Optional[float]:
    """TypeSafe's confidence for a choice/score answer, or None.

    choice: (p_max - 1/n) / (1 - 1/n)
    score:  max(0, 1 - sum(p_i * |i - mode|) / uniform_spread)
    """
    kind = answer.get("type")
    probs = answer.get("probabilities")
    if kind not in ("choice", "score") or not isinstance(probs, dict) or not probs:
        return None
    try:
        if kind == "score":
            values = [float(probs[key]) for key in sorted(probs, key=int)]
        else:
            values = [float(v) for v in probs.values()]
    except (TypeError, ValueError):
        return None
    if any(isinstance(v, bool) for v in probs.values()):
        return None
    if not all(math.isfinite(v) and v >= 0.0 for v in values):
        return None
    n = len(values)
    if n == 1:
        return 1.0
    total = sum(values)
    p = [v / total for v in values] if total else [1.0 / n] * n
    if kind == "choice":
        return (max(p) - 1.0 / n) / (1.0 - 1.0 / n)
    mode = max(range(n), key=p.__getitem__)
    spread = sum(v * abs(i - mode) for i, v in enumerate(p))
    center = (n - 1) / 2
    uniform_spread = sum(abs(i - center) for i in range(n)) / n
    return max(0.0, 1.0 - spread / uniform_spread)


def _act_probability(act_logit: Optional[float]) -> float:
    if act_logit is None:
        return 1.0
    if not math.isfinite(act_logit):
        return 1.0
    if act_logit >= 0:
        return 1.0 / (1.0 + math.exp(-act_logit))
    e = math.exp(act_logit)
    return e / (1.0 + e)


def decode_answers(
    questions: Dict[str, Dict[str, Any]],
    logits_by_qid: Dict[str, Sequence[float]],
    temperatures: TemperatureTable,
    *,
    lang: Optional[str] = None,
    act_logits: Optional[Dict[str, float]] = None,
    temperature_overrides: Optional[Dict[str, float]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Turn per-question option logits into laya's typed answer objects.

    ``temperature_overrides`` lets one request mix logit scales: the local
    scorer speaks its own fitted scale, an agent speaks the scale it was asked
    for (nats of evidence, 1.0). Everything after the temperature is identical.
    """
    answers: Dict[str, Dict[str, Any]] = {}
    act_logits = act_logits or {}
    for qid, q in questions.items():
        if qid not in logits_by_qid:
            raise QuestionError("no logits for question %r" % (qid,))
        kind = q["t"]
        k = option_count(q)
        logits = list(logits_by_qid[qid])[:k]
        if len(logits) != k:
            raise QuestionError(
                "question %r: expected %d option logits, got %d" % (qid, k, len(logits))
            )
        for i, value in enumerate(logits):
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
                raise QuestionError("question %r: option logit %d is not a finite number" % (qid, i))
        t = (temperature_overrides or {}).get(qid, temperatures.get(kind, k, lang))
        probs = softmax(logits, t)
        ans_conf = round4(answer_confidence(probs, k))
        ext = {"act_probability": round4(_act_probability(act_logits.get(qid)))}

        if kind == "choice":
            keys = [str(key) for key in q["crit"].keys()]
            probs = _unpermute(probs, q.get("option_order"))
            answers[qid] = {
                "type": "choice",
                "choice": keys[int(max(range(k), key=lambda i: probs[i]))],
                "probabilities": {key: round4(v) for key, v in zip(keys, probs)},
                "confidence": round4(confidence_from_probs(probs, k)),
                "answer_confidence": ans_conf,
                "action": ext,
            }
        elif kind == "score":
            probs = _unpermute(probs, q.get("option_order"))
            expected = float(sum(i * v for i, v in enumerate(probs)))
            answers[qid] = {
                "type": "score",
                "score": round4(expected),
                "legend": {str(i): render_criterion(c) for i, c in enumerate(q["crit"])},
                "probabilities": {str(i): round4(v) for i, v in enumerate(probs)},
                "confidence": round4(confidence_from_probs(probs, k)),
                "answer_confidence": ans_conf,
                "action": ext,
            }
        else:
            p_yes = probs[1] if len(probs) > 1 else 0.0
            answers[qid] = {
                "type": "noul",
                "noul": round4(p_yes),
                "confidence": round4(max(p_yes, 1.0 - p_yes)),
                "answer_confidence": ans_conf,
                "action": ext,
            }
    return answers


def _unpermute(probs: Sequence[float], order: Optional[Sequence[int]]) -> List[float]:
    if order is None or len(order) != len(probs):
        return list(probs)
    out = [0.0] * len(probs)
    for slot, original in enumerate(order):
        out[int(original)] = probs[slot]
    return out


def _bucket_of(answer: Dict[str, Any]) -> Optional[str]:
    kind = answer.get("type")
    if kind not in ("choice", "score", "noul"):
        return None
    if kind == "noul":
        k = 2
    else:
        probs = answer.get("probabilities")
        if not isinstance(probs, dict) or not probs:
            return None
        k = len(probs)
    size = "2" if k <= 2 else "3-5" if k <= 5 else "6-10" if k <= 10 else "11+"
    return "%s:%s" % (kind, size)


def apply_confidence_gate(result: Dict[str, Any], min_confidence: Any) -> None:
    """Mark low-confidence answers, in place, exactly like laya's gate."""
    if min_confidence is None:
        return
    is_map = isinstance(min_confidence, dict)
    answers = result.get("answers")
    if not isinstance(answers, dict):
        return
    for answer in answers.values():
        if not isinstance(answer, dict):
            continue
        conf = answer.get("answer_confidence")
        if not isinstance(conf, (int, float)) or isinstance(conf, bool) or not math.isfinite(conf):
            conf = answer.get("confidence")
        if isinstance(conf, (int, float)) and not isinstance(conf, bool) and math.isfinite(conf):
            if is_map:
                bucket = _bucket_of(answer)
                threshold = min_confidence.get(bucket, min_confidence.get("default", 0.0)) \
                    if bucket else min_confidence.get("default", 0.0)
            else:
                threshold = float(min_confidence)
            if conf < threshold:
                answer["low_confidence"] = True
            else:
                answer.pop("low_confidence", None)
            answer["abstention"] = "abstained" if conf < threshold else "passed"
            answer["abstention_threshold"] = float(threshold)
        else:
            answer.pop("low_confidence", None)
            answer["abstention"] = "unevaluated"
            answer["abstention_threshold"] = 0.0


def project_jev_strict(result: Dict[str, Any]) -> Dict[str, Any]:
    """Project a full result onto the strict Jev wire contract."""
    answers: Dict[str, Any] = {}
    for qid, answer in (result.get("answers") or {}).items():
        kind = answer.get("type") if isinstance(answer, dict) else None
        if kind == "choice":
            answers[qid] = {"type": "choice", "choice": answer["choice"],
                            "confidence": answer["confidence"],
                            "probabilities": answer["probabilities"]}
        elif kind == "score":
            answers[qid] = {"type": "score", "score": answer["score"],
                            "confidence": answer["confidence"],
                            "probabilities": answer["probabilities"],
                            "legend": answer["legend"]}
        elif kind == "noul":
            answers[qid] = {"type": "noul", "noul": answer["noul"]}
        else:
            answers[qid] = answer
    usage = result.get("usage") or {}
    return {
        "model": result["model"],
        "answers": answers,
        "usage": {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
        },
    }


def add_jev_confidence(result: Dict[str, Any]) -> Dict[str, Any]:
    """Add ``x_jev_confidence`` to every choice/score answer."""
    answers = result.get("answers")
    if not isinstance(answers, dict):
        return result
    out = {}
    for qid, answer in answers.items():
        conf = jev_confidence(answer) if isinstance(answer, dict) else None
        out[qid] = answer if conf is None else {**answer, "x_jev_confidence": round4(conf)}
    return {**result, "answers": out}


__all__ = [
    "TemperatureTable", "softmax", "confidence_from_probs", "answer_confidence",
    "jev_confidence", "decode_answers", "apply_confidence_gate",
    "project_jev_strict", "add_jev_confidence", "QTYPE_NAMES",
]
