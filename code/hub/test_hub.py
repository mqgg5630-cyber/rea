#!/usr/bin/env python3
"""Regression for hub.py against a throw-away git repo (no network).

    python code/hub/test_hub.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hub  # noqa: E402


def sh(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True)


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="hubtest-")
    try:
        origin = os.path.join(tmp, "origin")
        os.makedirs(os.path.join(origin, "results"))
        os.makedirs(os.path.join(origin, "src"))
        os.makedirs(os.path.join(origin, "code"))
        with open(os.path.join(origin, "results", "r.txt"), "w") as fh:
            fh.write("result\n")
        with open(os.path.join(origin, "src", "big.bin"), "wb") as fh:
            fh.write(b"x" * 4096)
        with open(os.path.join(origin, "code", "c.py"), "w") as fh:
            fh.write("# code\n")
        with open(os.path.join(origin, "README.md"), "w") as fh:
            fh.write("# demo\n")
        sh("git", "init", "-q", "-b", "main", cwd=origin)
        sh("git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A", cwd=origin)
        sh("git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init", cwd=origin)

        root = os.path.join(tmp, "root")
        argv = ["--root", root]
        assert hub.main(argv + ["init"]) == 0
        assert hub.main(argv + ["add", origin, "main", "--name", "demo", "--no-bootstrap"]) == 0

        clone = os.path.join(root, ".git-sync", "demo")
        assert os.path.isdir(os.path.join(clone, ".git")), clone
        assert os.path.isfile(os.path.join(clone, "README.md")), "root file must be present"
        assert os.path.isfile(os.path.join(clone, "results", "r.txt")), "results lost"
        assert not os.path.exists(os.path.join(clone, "src")), "src must stay off disk"

        assert hub.main(argv + ["status"]) == 0
        assert hub.main(argv + ["mirror"]) == 0
        mirrored = os.path.join(root, "results", "demo", "r.txt")
        assert os.path.isfile(mirrored), mirrored
        assert not os.path.exists(os.path.join(root, "results", "demo", "src")), \
            "sources must not be mirrored"

        assert hub.main(argv + ["trim", "--keep", "results"]) == 0
        assert not os.path.exists(os.path.join(clone, "code")), "trim kept code"
        assert os.path.isfile(os.path.join(clone, "results", "r.txt"))
        print("hub ok: clone sparse, status, mirror, trim")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
