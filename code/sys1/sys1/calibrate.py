"""Temperature fitting and expected calibration error, laya-style.

laya fits one temperature per ``(question type, option-count bucket)`` on held
out decisions, clamps it to [0.5, 5.0], and reports ECE on ``max(p)``. The same
fit is reproduced here, with the teacher being laya's own checkpoint output
from its golden fixtures rather than human labels.

Why this matters for a distilled engine: the raw lexical logits have their own
scale, so a temperature fitted on *these* logits is the difference between
"confident" meaning something and it being decoration.
"""

from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .decode import TemperatureTable, softmax
from .protocol import temp_bucket

GRID = [0.5 + 0.02 * i for i in range(int((5.0 - 0.5) / 0.02) + 1)]

DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "data", "calibration.json")


def _k_of(q: Dict[str, Any]) -> int:
    if q.get("type") == "noul":
        return 2
    return len(q.get("criteria") or [])


def rows_from_goldens(path: str) -> List[Dict[str, Any]]:
    """Flatten golden fixtures into rows of (checkpoint, kind, k, logits, teacher)."""
    with open(path, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    rows: List[Dict[str, Any]] = []
    for checkpoint, block in (doc.get("checkpoints") or {}).items():
        for case in block.get("cases") or []:
            questions = case.get("questions") or {}
            answers = ((case.get("result") or {}).get("answers")) or {}
            for index, (qid, qdef) in enumerate(questions.items()):
                answer = answers.get(qid) or {}
                kind = qdef.get("type")
                if kind not in ("choice", "score", "noul"):
                    continue
                probs = answer.get("probabilities")
                if kind == "noul":
                    teacher = [1.0 - float(answer.get("noul", 0.5)), float(answer.get("noul", 0.5))]
                elif isinstance(probs, dict):
                    keys = list(probs.keys())
                    if kind == "score":
                        keys = sorted(keys, key=int)
                    teacher = [float(probs[k]) for k in keys]
                else:
                    continue
                k = _k_of(qdef)
                if len(teacher) != k:
                    continue
                logits = list((case.get("logits") or [])[index])[:k]
                if len(logits) != k:
                    continue
                rows.append({"checkpoint": checkpoint, "name": case.get("name"), "qid": qid,
                             "kind": kind, "k": k, "logits": logits, "teacher": teacher})
    return rows


def _ce(teacher: Sequence[float], logits: Sequence[float], t: float) -> float:
    p = softmax(logits, t)
    total = sum(teacher) or 1.0
    return -sum((w / total) * math.log(max(pi, 1e-12)) for w, pi in zip(teacher, p))


def _hard(teacher: Sequence[float]) -> List[float]:
    k = len(teacher)
    best = max(range(k), key=lambda i: teacher[i])
    return [1.0 if i == best else 0.0 for i in range(k)]


def _brier(rows: Sequence[Dict[str, Any]], t: float) -> float:
    total = 0.0
    for row in rows:
        p = softmax(row["logits"], t)
        pred = max(range(len(p)), key=p.__getitem__)
        gold = max(range(len(row["teacher"])), key=row["teacher"].__getitem__)
        total += (max(p) - (1.0 if pred == gold else 0.0)) ** 2
    return total / max(1, len(rows))


def fit_bucket(rows: Sequence[Dict[str, Any]], hard: bool = False,
               objective: str = "soft") -> Tuple[float, float]:
    """Return (best temperature, mean CE at it) for one bucket of rows.

    ``hard=True`` fits against the teacher's *answer* rather than its full
    distribution. That is the right target for an abstention gate: the gate's
    promise is about correctness, while a soft target also rewards reproducing
    the teacher's uncertainty on cases it got wrong.
    """
    best_t, best_loss = 1.0, float("inf")
    for t in GRID:
        if objective == "brier":
            loss = _brier(rows, t)
        else:
            loss = 0.0
            for row in rows:
                target = _hard(row["teacher"]) if hard else row["teacher"]
                loss += _ce(target, row["logits"], t)
            loss /= max(1, len(rows))
        if loss < best_loss - 1e-12:
            best_t, best_loss = t, loss
    return TemperatureTable._clamp(best_t), best_loss


def ece(confidences: Sequence[float], correct: Sequence[bool], bins: int = 10) -> float:
    if not confidences:
        return 0.0
    total = len(confidences)
    error = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        members = [i for i, c in enumerate(confidences) if (lo <= c < hi) or (b == bins - 1 and c == 1.0)]
        if not members:
            continue
        avg_conf = sum(confidences[i] for i in members) / len(members)
        accuracy = sum(1.0 for i in members if correct[i]) / len(members)
        error += (len(members) / total) * abs(avg_conf - accuracy)
    return error


def evaluate_rows(rows: Sequence[Dict[str, Any]], table: TemperatureTable) -> Dict[str, Any]:
    """Argmax agreement, NLL, and ECE of a temperature table over rows."""
    confidences: List[float] = []
    correct: List[bool] = []
    losses: List[float] = []
    by_kind: Dict[str, List[int]] = {}
    for row in rows:
        p = softmax(row["logits"], table.get(row["kind"], row["k"]))
        teacher = row["teacher"]
        pred = max(range(len(p)), key=p.__getitem__)
        gold = max(range(len(teacher)), key=teacher.__getitem__)
        confidences.append(max(p))
        correct.append(pred == gold)
        losses.append(_ce(teacher, row["logits"], table.get(row["kind"], row["k"])))
        stats = by_kind.setdefault(row["kind"], [0, 0])
        stats[0] += 1
        stats[1] += int(pred == gold)
    agreement = sum(correct) / max(1, len(correct))
    return {
        "n": len(rows),
        "argmax_agreement": round(agreement, 4),
        "mean_ce": round(sum(losses) / max(1, len(losses)), 4),
        "ece": round(ece(confidences, correct), 4),
        "by_kind": {kind: {"n": n, "agreement": round(hit / max(1, n), 4)}
                    for kind, (n, hit) in by_kind.items()},
    }


def fit(rows: Sequence[Dict[str, Any]], hard: bool = False,
        objective: str = "soft") -> Dict[str, Any]:
    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        buckets.setdefault(temp_bucket(row["kind"], row["k"]), []).append(row)
    fitted = {key: fit_bucket(group, hard, objective)[0] for key, group in buckets.items()}
    by_type: Dict[str, float] = {}
    for kind in ("choice", "score", "noul"):
        members = [row for row in rows if row["kind"] == kind]
        if members:
            by_type[kind] = fit_bucket(members, hard, objective)[0]
    table = TemperatureTable(by_bucket=fitted, by_type=by_type)
    return {
        "temperature": by_type,
        "temperature_by_options": fitted,
        "temperature_by_language": {},
        "metrics": {
            "default_T1": evaluate_rows(rows, TemperatureTable()),
            "fitted": evaluate_rows(rows, table),
        },
        "n": len(rows),
        "buckets": sorted(fitted),
    }


def load(path: Optional[str] = None) -> TemperatureTable:
    path = path or DEFAULT_PATH
    try:
        with open(path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
        return TemperatureTable(doc.get("temperature_by_options"),
                                doc.get("temperature"),
                                doc.get("temperature_by_language"))
    except (OSError, ValueError):
        return TemperatureTable()


def save(doc: Dict[str, Any], path: Optional[str] = None) -> str:
    path = path or DEFAULT_PATH
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return path


__all__ = ["rows_from_goldens", "fit", "fit_bucket", "ece", "evaluate_rows", "load", "save", "DEFAULT_PATH"]
