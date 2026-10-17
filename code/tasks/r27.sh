#!/usr/bin/env bash
# Round 27: prove the Windows host can act on the real machine, not just
# inside the repo - create a "test succeeded" txt on the user's Desktop.
# Contract: the Desktop file is the deliverable on the host; under results/
# we only write the confirmation that hpc_follow pushes back.
set -eu

# Locate the Desktop from inside Git Bash (USERPROFILE has backslashes).
DESKTOP=""
if [ -n "${USERPROFILE:-}" ] && command -v cygpath >/dev/null 2>&1; then
  DESKTOP="$(cygpath -u "$USERPROFILE")/Desktop"
fi
if [ -z "$DESKTOP" ] || [ ! -d "$DESKTOP" ]; then
  DESKTOP="$HOME/Desktop"
fi
mkdir -p "$DESKTOP"

TARGET="$DESKTOP/测试成功.txt"
{
  echo "测试成功"
  echo "host=$(hostname)"
  echo "round=${HPC_ROUND:-?} branch=${HPC_BRANCH:-?}"
  echo "time=$(date '+%Y-%m-%d %H:%M:%S %z')"
  echo "by=hpc_follow (Windows install-once follower)"
} > "$TARGET"

mkdir -p results/out
{
  echo "desktop_file=$TARGET"
  echo "exists=$([ -f "$TARGET" ] && echo yes || echo no)"
  echo "bytes=$(wc -c < "$TARGET")"
} > results/out/hpc_desktop_r27.txt
cat results/out/hpc_desktop_r27.txt
