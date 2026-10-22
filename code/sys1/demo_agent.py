"""The agent is the decision engine: fixed agent logits, laya's math.

Every number in ``CASES`` below was produced by the agent reading the state and
the option text in this conversation - no hosted model, no local checkpoint, no
network. ``sys1`` only renders laya's prompt, applies laya's temperature ->
softmax -> typed-answer decoding, and reports laya's confidence.

Run:  python code/sys1/demo_agent.py [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from sys1 import DecisionEngine  # noqa: E402
from sys1.protocol import build_prompt, normalize_questions  # noqa: E402

DEPARTMENTS = {
    "billing": "invoices, payments, refunds, subscription charges",
    "technical": "bugs, crashes, outages, performance",
    "account": "login, seats, permissions, profile",
    "other": "anything that is not billing, technical, or account",
}

CASES = [
    {
        "name": "en-refund-threat",
        "state": ("I was charged twice for the Pro plan this month. Please refund the duplicate "
                  "charge - if this is not sorted today I will cancel the subscription."),
        "questions": {
            "department": {"type": "choice", "instructions": "Which team owns this ticket?",
                           "criteria": DEPARTMENTS},
            "urgency": {"type": "score", "instructions": "How urgent is the request?",
                        "criteria": ["can wait", "normal", "today or churn"]},
            "churn": {"type": "noul", "instructions": "Does the customer threaten to cancel?"},
        },
        "logits": {"department": [3.4, -0.6, 0.9, -1.8], "urgency": [-2.0, 0.2, 2.2],
                   "churn": [-1.6, 2.1]},
    },
    {
        "name": "zh-double-charge",
        "state": "这个月的会员费又扣了两次，我要求马上退款，不然就取消订阅。",
        "questions": {
            "department": {"type": "choice", "instructions": "Which team owns this ticket?",
                           "criteria": DEPARTMENTS},
            "churn": {"type": "noul", "instructions": "Does the customer threaten to cancel?"},
        },
        "logits": {"department": [3.8, -0.9, 0.7, -2.0], "churn": [-2.0, 2.6]},
    },
    {
        "name": "es-refund",
        "state": "Me cobraron dos veces la suscripción anual. Necesito la devolución hoy mismo.",
        "questions": {
            "intent": {"type": "choice", "instructions": "What does the customer want?",
                       "criteria": {"refund": "money back for a charge",
                                    "cancel": "end the subscription",
                                    "question": "information only"}},
            "urgency": {"type": "score", "instructions": "How urgent is the request?",
                        "criteria": ["can wait", "normal", "today"]},
        },
        "logits": {"intent": [3.0, -0.4, 0.2], "urgency": [-1.4, 0.6, 1.5]},
    },
    {
        "name": "de-outage",
        "state": ("Seit dem letzten Update stürzt die App direkt beim Start ab. "
                  "Wir können nicht arbeiten."),
        "questions": {
            "department": {"type": "choice", "instructions": "Which team owns this ticket?",
                           "criteria": DEPARTMENTS},
            "severity": {"type": "score", "instructions": "How severe is the impact?",
                         "criteria": ["cosmetic", "degraded", "blocking"]},
        },
        "logits": {"department": [-2.2, 3.1, -0.3, -1.0], "severity": [-1.8, 0.3, 2.4]},
    },
    {
        "name": "json-state",
        "state": {"channel": "email", "plan": "team", "tenure_months": 14,
                  "message": "Invoice INV-2231 shows two charges for March. Please refund."},
        "questions": {
            "department": {"type": "choice", "instructions": "Which team owns this ticket?",
                           "criteria": DEPARTMENTS},
        },
        "logits": {"department": [3.6, -1.1, 0.4, -2.0]},
    },
    {
        "name": "noul-ambiguous",
        "state": "The dashboard is a little slow sometimes, but otherwise everything is fine.",
        "questions": {
            "churn": {"type": "noul", "instructions": "Does the customer threaten to cancel?"},
        },
        "logits": {"churn": [2.4, -2.6]},
    },
]


def row(case_name: str, qid: str, answer: dict) -> str:
    if answer["type"] == "choice":
        head = "`%s`" % answer["choice"]
        detail = " ".join("%s=%.3f" % (k, v) for k, v in answer["probabilities"].items())
    elif answer["type"] == "score":
        head = "%.2f" % answer["score"]
        detail = " ".join("%s=%.3f" % (k, v) for k, v in answer["probabilities"].items())
    else:
        head = "%.3f" % answer["noul"]
        detail = "p(yes)"
    return "| %s | %s | %s | %s | %.3f | %.3f |" % (
        case_name, qid, head, detail, answer["answer_confidence"],
        answer.get("x_jev_confidence") if answer.get("x_jev_confidence") is not None else float("nan"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", default=os.path.join(HERE, "..", "..", "results", "sys1", "AGENT_DEMO.md"))
    args = parser.parse_args()

    engine = DecisionEngine()
    bundle = []
    for case in CASES:
        result = engine.predict(case["state"], case["questions"], engine="agent",
                                agent_logits=case["logits"], include_prompts=True)
        bundle.append({"case": case["name"], "state": case["state"], "result": result})

    mixed = engine.predict(
        "App crashes on launch after the update. Also, where is my invoice?",
        {"department": {"type": "choice", "instructions": "Which team owns this ticket?",
                        "criteria": DEPARTMENTS},
         "churn": {"type": "noul", "instructions": "Does the customer threaten to cancel?"}},
        engine="auto", agent_logits={"department": [0.2, 2.8, -0.5, -1.5]})

    if args.json:
        print(json.dumps({"cases": bundle, "mixed": mixed}, ensure_ascii=False, indent=2))
        return 0

    lines = [
        "# Agent as the decision engine (no API, no checkpoint)",
        "",
        "Every logit below was produced by the agent reading the state and option text in",
        "this conversation. `sys1` did the rest: routing, laya's prompt rendering,",
        "temperature -> softmax -> typed answer, `confidence`, `answer_confidence` and",
        "`x_jev_confidence`. Nothing left the machine; `selfcheck.py` proves the engine still",
        "works with `socket.create_connection` patched to raise.",
        "",
        "| case | question | decision | distribution | answer_conf | jev_conf |",
        "|---|---|---|---|---|---|",
    ]
    for entry in bundle:
        for qid, answer in entry["result"]["answers"].items():
            lines.append(row(entry["case"], qid, answer))
    lines += [
        "",
        "## Mixed mode (`engine=auto`)",
        "",
        "`department` came from the agent logits, `churn` fell back to the local scorer:",
        "",
        "```json",
        json.dumps({"engines_used": mixed["sys1"]["engines_used"],
                    "routing": mixed["routing"]["model"],
                    "department": mixed["answers"]["department"]["choice"],
                    "churn": mixed["answers"]["churn"]["noul"]},
                   ensure_ascii=False, indent=2),
        "```",
        "",
        "## What the agent saw: one rendered prompt",
        "",
        "```text",
        build_prompt(CASES[0]["state"],
                     normalize_questions(CASES[0]["questions"])["department"]),
        "```",
        "",
        "The prompt is byte-for-byte laya's layout (`[CLS] <type> question: <instructions>",
        "[SEP] [MASK] <option> ... [SEP] <state> [SEP]`), so the same request can be replayed",
        "against a checkpoint later and the answers compared one-for-one.",
        "",
    ]
    with open(os.path.abspath(args.out), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    for entry in bundle:
        print(entry["case"])
        for qid, answer in entry["result"]["answers"].items():
            if answer["type"] == "choice":
                print("  %-10s %-9s %.3f  (%s)" % (qid, answer["choice"],
                                                   answer["answer_confidence"],
                                                   " ".join("%s=%.2f" % (k, v) for k, v in
                                                            answer["probabilities"].items())))
            elif answer["type"] == "score":
                print("  %-10s score=%.2f  conf=%.3f" % (qid, answer["score"],
                                                         answer["answer_confidence"]))
            else:
                print("  %-10s noul=%.3f conf=%.3f" % (qid, answer["noul"],
                                                       answer["answer_confidence"]))
    print("mixed engines:", mixed["sys1"]["engines_used"], mixed["answers"]["department"]["choice"])
    print("wrote", os.path.abspath(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
