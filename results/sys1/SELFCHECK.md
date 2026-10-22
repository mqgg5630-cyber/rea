# sys1 self-check

- version: `1.0.0`
- result: **21/21 PASS**
- host: `e2b.local` (Linux-6.1.158+-x86_64-with-glibc2.36, Python 3.11.2)
- latency: p50 1.221 ms, p95 1.313 ms, 818.7 decisions/sec

| check | result |
|---|---|
| render_options keeps order | OK |
| prompt layout | OK |
| softmax sums to 1 | OK |
| entropy confidence of uniform | OK |
| answer_confidence is max | OK |
| jev choice confidence | OK |
| jev score confidence | OK |
| decoder parity 100% | OK |
| routing natural sentences | OK |
| script detection | OK |
| english triage | OK |
| cjk cross-lingual | OK |
| abstention gate | OK |
| agent logits decode | OK |
| agent prompt request | OK |
| deterministic | OK |
| HTTP Jev contract | OK |
| MCP stdio | OK |
| no outbound client imports | OK |
| works with sockets blocked | OK |
| latency under 25 ms p95 | OK |
