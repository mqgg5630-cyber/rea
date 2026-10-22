"""Extract a compact, attributed fixture from laya's published golden files.

Usage::

    python tools/extract_laya_goldens.py /path/to/laya

The golden JSON files live in ``laya-dotnet/tests/Laya.Tests/golden`` in the
laya repository (Apache-2.0). Each one records a state, a question set, the
checkpoint's raw option logits and the answer laya produced from them. We keep
only those fields plus the checkpoint's fitted temperatures; token ids, padded
batches and tokenizer probes are dropped.

The result (``sys1/data/goldens.json``) is the evidence base for:

* decoder parity (logits + temperature -> laya's exact answer),
* teacher-distribution calibration,
* agreement between this engine and the real checkpoint.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict


def load_case(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def compact(case: Dict[str, Any]) -> Dict[str, Any]:
    questions = case.get("questions") or {}
    answers = (case.get("result") or {}).get("answers") or {}
    row_count = len(case.get("logits") or [])
    if row_count != len(questions):
        raise ValueError("logit rows do not match questions")
    clean_questions = {}
    for qid, qdef in questions.items():
        answer = answers.get(qid) or {}
        k = 2 if qdef.get("type") == "noul" else len(qdef.get("criteria") or [])
        probs = answer.get("probabilities")
        if probs is not None and len(probs) != k:
            raise ValueError("answer probabilities do not cover every option")
        clean_questions[qid] = qdef
    return {
        "name": case.get("name"),
        "state": case.get("state"),
        "questions": clean_questions,
        "logits": case.get("logits"),
        "act_logits": case.get("act_logits"),
        "result": case.get("result"),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    root = os.path.abspath(sys.argv[1])
    golden_root = os.path.join(root, "laya-dotnet", "tests", "Laya.Tests", "golden")
    if not os.path.isdir(golden_root):
        print("no golden directory under %s" % root)
        return 2
    out: Dict[str, Any] = {
        "source": "https://github.com/NandhaKishorM/laya",
        "path": "laya-dotnet/tests/Laya.Tests/golden",
        "laya_version": None,
        "license": "Apache-2.0",
        "note": "Compact extraction of laya's published golden fixtures; see NOTICE.",
        "checkpoints": {},
    }
    for checkpoint in ("english", "multilingual", "typed-decisions"):
        directory = os.path.join(golden_root, checkpoint)
        if not os.path.isdir(directory):
            continue
        with open(os.path.join(directory, "meta.json"), "r", encoding="utf-8") as fh:
            meta = json.load(fh)
        if out["laya_version"] is None:
            out["laya_version"] = meta.get("laya_version")
        temps = {
            "temperature": meta.get("config", {}).get("temperature"),
            "temperature_by_options": meta.get("config", {}).get("temperature_by_options", {}),
        }
        cases = []
        for name in sorted(os.listdir(directory)):
            if not name.endswith(".json") or name in ("meta.json", "index.json"):
                continue
            path = os.path.join(directory, name)
            try:
                case = load_case(path)
                if "logits" not in case or "result" not in case:
                    continue
                cases.append(compact(case))
            except (ValueError, KeyError, TypeError) as exc:
                print("skip %s/%s: %s" % (checkpoint, name, exc))
        out["checkpoints"][checkpoint] = {"temperatures": temps, "cases": cases}
        print("%-16s %d cases" % (checkpoint, len(cases)))
    target = os.path.join(os.path.dirname(__file__), "..", "sys1", "data", "goldens.json")
    target = os.path.abspath(target)
    with open(target, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
    print("wrote %s (%.1f KiB)" % (target, os.path.getsize(target) / 1024.0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
