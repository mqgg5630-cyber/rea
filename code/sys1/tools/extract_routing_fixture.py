"""Extract laya's routing golden into a compact fixture.

    python tools/extract_routing_fixture.py /path/to/laya

Keeps the states, laya's expected ``analyse`` result, and every route decision
that names those states (plus explicit model/task/lang cases). Writes
``sys1/data/routing.json``.
"""

from __future__ import annotations

import json
import os
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    root = os.path.abspath(sys.argv[1])
    source = os.path.join(root, "laya-dotnet", "tests", "Laya.Tests", "golden",
                          "routing", "differential_probe.json")
    with open(source, "r", encoding="utf-8") as fh:
        probe = json.load(fh)

    states = []
    for item in probe.get("lang", []):
        states.append({
            "label": item.get("label"),
            "state": item.get("state"),
            "analyse": item.get("analyse"),
        })

    routes = []
    for item in probe.get("route", []):
        index = item.get("state")
        if not isinstance(index, int) or not 0 <= index < len(states):
            continue
        routes.append({
            "state": index,
            "kwargs": item.get("kwargs") or {},
            "model": item.get("model"),
            "reason": item.get("reason"),
        })

    out = {
        "source": "https://github.com/NandhaKishorM/laya",
        "path": "laya-dotnet/tests/Laya.Tests/golden/routing/differential_probe.json",
        "license": "Apache-2.0",
        "seed": probe.get("seed"),
        "states": states,
        "routes": routes,
    }
    target = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sys1", "data", "routing.json"))
    with open(target, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
    print("wrote %s: %d states, %d routes, %.1f KiB"
          % (target, len(states), len(routes), os.path.getsize(target) / 1024.0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
