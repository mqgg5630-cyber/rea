# Agent as the decision engine (no API, no checkpoint)

Every logit below was produced by the agent reading the state and option text in
this conversation. `sys1` did the rest: routing, laya's prompt rendering,
temperature -> softmax -> typed answer, `confidence`, `answer_confidence` and
`x_jev_confidence`. Nothing left the machine; `selfcheck.py` proves the engine still
works with `socket.create_connection` patched to raise.

| case | question | decision | distribution | answer_conf | jev_conf |
|---|---|---|---|---|---|
| en-refund-threat | department | `billing` | billing=0.904 technical=0.017 account=0.074 other=0.005 | 0.904 | 0.872 |
| en-refund-threat | urgency | 1.86 | 0=0.013 1=0.118 2=0.869 | 0.869 | 0.785 |
| en-refund-threat | churn | 0.976 | p(yes) | 0.976 | nan |
| zh-double-charge | department | `billing` | billing=0.946 technical=0.009 account=0.043 other=0.003 | 0.946 | 0.928 |
| zh-double-charge | churn | 0.990 | p(yes) | 0.990 | nan |
| es-refund | intent | `refund` | refund=0.914 cancel=0.030 question=0.056 | 0.914 | 0.871 |
| es-refund | urgency | 1.65 | 0=0.038 1=0.278 2=0.684 | 0.684 | 0.470 |
| de-outage | department | `technical` | billing=0.005 technical=0.948 account=0.032 other=0.016 | 0.948 | 0.931 |
| de-outage | severity | 1.87 | 0=0.013 1=0.108 2=0.879 | 0.879 | 0.799 |
| json-state | department | `billing` | billing=0.949 technical=0.009 account=0.039 other=0.004 | 0.949 | 0.932 |
| noul-ambiguous | churn | 0.007 | p(yes) | 0.993 | nan |

## Mixed mode (`engine=auto`)

`department` came from the agent logits, `churn` fell back to the local scorer:

```json
{
  "engines_used": {
    "department": "agent",
    "churn": "local"
  },
  "routing": "english",
  "department": "technical",
  "churn": 0.4127
}
```

## What the agent saw: one rendered prompt

```text
[CLS] choice question: Which team owns this ticket? [SEP] [MASK] billing: invoices, payments, refunds, subscription charges [MASK] technical: bugs, crashes, outages, performance [MASK] account: login, seats, permissions, profile [MASK] other: anything that is not billing, technical, or account [SEP] I was charged twice for the Pro plan this month. Please refund the duplicate charge - if this is not sorted today I will cancel the subscription. [SEP]
```

The prompt is byte-for-byte laya's layout (`[CLS] <type> question: <instructions>
[SEP] [MASK] <option> ... [SEP] <state> [SEP]`), so the same request can be replayed
against a checkpoint later and the answers compared one-for-one.
