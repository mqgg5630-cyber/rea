#!/usr/bin/env python3
"""local hub for the git-sync loop: one place, many repos, results only.

The user's machine keeps **no project clones**: every repo lives in
``<root>\\.git-sync\\<name>`` as a *sparse, blobless* checkout that materialises
only the paths the loop needs (root scripts, ``code``, ``skills``, ``results``,
``deliverable``), and every branch's output is copied to
``<root>\\results\\<name>``.  Source trees are never downloaded.

    python code/hub/hub.py init
    python code/hub/hub.py add https://github.com/me/repo.git arena/x-1
    python code/hub/hub.py register
    python code/hub/hub.py status
    python code/hub/hub.py mirror
    python code/hub/hub.py trim --keep results,deliverable,code,skills

The PowerShell wrapper ``hub.ps1`` is only a python finder.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from typing import Dict, List, Optional

DEFAULT_KEEP = ["results", "deliverable", "code", "skills"]
HUB_DIR = ".git-sync"
RESULTS_DIR = "results"
IS_WINDOWS = os.name == "nt"


# --------------------------------------------------------------------- helpers
def git(repo: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True,
                          check=check)


def _default_root() -> str:
    env = os.environ.get("GIT_SYNC_ROOT")
    if env:
        return env
    cwd = os.path.abspath(os.getcwd())
    if os.path.basename(os.path.dirname(cwd)) == HUB_DIR:
        return os.path.dirname(os.path.dirname(cwd))
    return r"E:\0github" if IS_WINDOWS else os.path.join(os.path.expanduser("~"), "0github")


def _slug(url: str, branch: str) -> str:
    repo = url.rstrip("/").rsplit("/", 1)[-1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    tail = branch.rsplit("/", 1)[-1][:12]
    return "%s-%s" % (repo, tail) if tail else repo


def _clones(root: str) -> List[str]:
    base = os.path.join(root, HUB_DIR)
    if not os.path.isdir(base):
        return []
    out = []
    for name in sorted(os.listdir(base)):
        path = os.path.join(base, name)
        if os.path.isdir(os.path.join(path, ".git")):
            out.append(path)
    return out


def _task_name(path: str) -> str:
    return "git-sync-watch-" + os.path.basename(path)


def _task_state(name: str) -> str:
    if not IS_WINDOWS:
        return "-"
    try:
        proc = subprocess.run(["schtasks", "/Query", "/TN", name, "/FO", "LIST"],
                              capture_output=True, text=True)
    except OSError:
        return "?"
    if proc.returncode != 0:
        return "absent"
    for line in proc.stdout.splitlines():
        if line.lower().startswith(("status", "状态")):
            return line.split(":", 1)[-1].strip()
    return "registered"


def _powershell() -> Optional[str]:
    for name in ("powershell", "pwsh"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _run_ps(script: str, cwd: str) -> int:
    exe = _powershell()
    if not exe:
        print("  [skip] no PowerShell on this host")
        return 1
    return subprocess.call([exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script],
                           cwd=cwd)


def _sparse_set(path: str, keep: List[str]) -> None:
    """Cone-mode sparse checkout: root files plus the kept top-level dirs."""
    git(path, "sparse-checkout", "init", "--cone", check=False)
    dirs = [d for d in keep if d]
    git(path, "sparse-checkout", "set", *dirs, check=False)
    git(path, "sparse-checkout", "reapply", check=False)


def _tree_dirs(path: str) -> List[str]:
    proc = git(path, "ls-tree", "-d", "--name-only", "HEAD", check=False)
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


# --------------------------------------------------------------------- commands
def cmd_init(args) -> int:
    for sub in (HUB_DIR, RESULTS_DIR):
        os.makedirs(os.path.join(args.root, sub), exist_ok=True)
    print("root   :", args.root)
    print("clones :", os.path.join(args.root, HUB_DIR))
    print("results:", os.path.join(args.root, RESULTS_DIR))
    return 0


def cmd_add(args) -> int:
    name = args.name or _slug(args.url, args.branch)
    dest = os.path.join(args.root, HUB_DIR, name)
    if os.path.exists(dest):
        print("[skip] already exists:", dest)
        return 0
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    cmd = ["git", "clone", "--sparse", "--branch", args.branch]
    if not args.no_filter:
        cmd[2:2] = ["--filter=blob:none"]
    cmd += [args.url, dest]
    print("== clone", name, "->", dest)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        # some servers/transports refuse partial clone: retry without the filter
        print("  [warn] partial clone refused, retrying without filter")
        proc = subprocess.run(["git", "clone", "--sparse", "--branch", args.branch,
                               args.url, dest], capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stderr.strip()[-800:])
        return 1
    keep = [d for d in (args.keep or DEFAULT_KEEP) if d in _tree_dirs(dest)]
    if not keep:
        keep = ["results"] if "results" in _tree_dirs(dest) else []
    _sparse_set(dest, keep)
    print("  sparse:", ", ".join(keep) or "(root files only)")
    if args.bootstrap and os.path.exists(os.path.join(dest, "bootstrap.ps1")):
        print("== bootstrap (auth + watcher)")
        _run_ps(os.path.join(dest, "bootstrap.ps1"), dest)
    return 0


def cmd_register(args) -> int:
    code = 0
    for path in _clones(args.root):
        script = os.path.join(path, "watch.ps1")
        if not os.path.exists(script):
            print("[skip]", os.path.basename(path), "(no watch.ps1)")
            continue
        print("== register", os.path.basename(path))
        code |= _run_ps(script, path) and 1
    return code


def cmd_status(args) -> int:
    rows = []
    for path in _clones(args.root):
        name = os.path.basename(path)
        branch = git(path, "rev-parse", "--abbrev-ref", "HEAD", check=False).stdout.strip()
        head = git(path, "rev-parse", "--short", "HEAD", check=False).stdout.strip()
        dirty = len([l for l in git(path, "status", "--porcelain", check=False).stdout.splitlines() if l])
        sparse = git(path, "sparse-checkout", "list", check=False).stdout.split()
        receipt = os.path.join(path, "results", "sync", "last_sync.md")
        when = ""
        if os.path.exists(receipt):
            when = datetime.fromtimestamp(os.path.getmtime(receipt)).strftime("%m-%d %H:%M")
        mirror = os.path.join(args.root, RESULTS_DIR, name)
        rows.append({
            "name": name, "branch": branch, "head": head, "dirty": dirty,
            "watch": _task_state(_task_name(path)),
            "sparse": ",".join(sparse), "last_sync": when,
            "results": mirror if os.path.isdir(mirror) else "",
        })
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print("no clones under", os.path.join(args.root, HUB_DIR))
        return 0
    width = max(len(r["name"]) for r in rows) + 1
    print("%-*s %-28s %-7s %-4s %-10s %-9s %s" % (width, "name", "branch", "head", "dirty",
                                                   "watcher", "last_sync", "sparse"))
    for r in rows:
        print("%-*s %-28s %-7s %-4d %-10s %-9s %s" % (width, r["name"], r["branch"], r["head"],
                                                       r["dirty"], r["watch"], r["last_sync"],
                                                       r["sparse"]))
    print("\nmirror: python code/hub/hub.py mirror")
    return 0


def _copy_tree(src: str, dst: str) -> int:
    if not os.path.isdir(src):
        return 0
    count = 0
    for base, _dirs, files in os.walk(src):
        rel = os.path.relpath(base, src)
        target = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(target, exist_ok=True)
        for name in files:
            shutil.copy2(os.path.join(base, name), os.path.join(target, name))
            count += 1
    return count


def cmd_mirror(args) -> int:
    total = 0
    for path in _clones(args.root):
        name = os.path.basename(path)
        dst = os.path.join(args.root, RESULTS_DIR, name)
        n = _copy_tree(os.path.join(path, "results"), dst)
        n += _copy_tree(os.path.join(path, "deliverable"), os.path.join(dst, "deliverable"))
        total += n
        print("%-28s %5d file(s) -> %s" % (name, n, dst))
    print("mirrored", total, "file(s) (project sources are not copied)")
    return 0


def cmd_trim(args) -> int:
    """Shrink every clone to the kept paths (source trees stay on the remote)."""
    keep = [k for k in (args.keep or DEFAULT_KEEP) if k]
    for path in _clones(args.root):
        dirs = _tree_dirs(path)
        picked = [d for d in keep if d in dirs]
        _sparse_set(path, picked)
        print("%-28s -> %s" % (os.path.basename(path), ", ".join(picked) or "(root only)"))
    return 0


def cmd_prune(args) -> int:
    """Forget clones whose folder is gone (their watcher task would loop on a missing path)."""
    if not IS_WINDOWS:
        print("nothing to prune outside Windows")
        return 0
    exe = _powershell()
    if not exe:
        return 1
    ps = ("Get-ScheduledTask -TaskName 'git-sync-watch-*' -ErrorAction SilentlyContinue | "
          "ForEach-Object { $_.TaskName }")
    names = subprocess.run([exe, "-NoProfile", "-Command", ps], capture_output=True,
                           text=True).stdout.split()
    alive = {_task_name(p) for p in _clones(args.root)}
    stale = [n for n in names if n not in alive]
    for name in stale:
        print("unregister", name)
        subprocess.call([exe, "-NoProfile", "-Command",
                         "Unregister-ScheduledTask -TaskName '%s' -Confirm:$false" % name])
    if not stale:
        print("no stale watcher tasks")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="hub", description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=_default_root())
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("init")

    p = sub.add_parser("add")
    p.add_argument("url")
    p.add_argument("branch")
    p.add_argument("--name")
    p.add_argument("--keep", default="")
    p.add_argument("--no-filter", action="store_true")
    p.add_argument("--no-bootstrap", dest="bootstrap", action="store_false")
    p.set_defaults(bootstrap=True)

    sub.add_parser("register")
    sub.add_parser("status").add_argument("--json", action="store_true")
    sub.add_parser("mirror")
    p = sub.add_parser("trim")
    p.add_argument("--keep", default="")
    sub.add_parser("prune")

    args = parser.parse_args(argv)
    if args.cmd is None:
        parser.print_help()
        return 2
    if getattr(args, "keep", ""):
        args.keep = [k.strip() for k in args.keep.split(",") if k.strip()]
    else:
        args.keep = list(DEFAULT_KEEP)
    os.makedirs(args.root, exist_ok=True)
    return {
        "init": cmd_init, "add": cmd_add, "register": cmd_register,
        "status": cmd_status, "mirror": cmd_mirror, "trim": cmd_trim,
        "prune": cmd_prune,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
