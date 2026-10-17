#!/usr/bin/env bash
# Round 28: the Desktop is redirected to D: on this host. Do NOT guess the
# path from USERPROFILE - ask Windows for the real known-folder location,
# write the test txt there, and remove the wrong one round 27 left on C:.
set -eu

DESKTOP_WIN="$(powershell.exe -NoProfile -Command "[Environment]::GetFolderPath('Desktop')" | tr -d '\r\n')"
DESKTOP="$(cygpath -u "$DESKTOP_WIN")"
echo "real desktop: $DESKTOP_WIN -> $DESKTOP"
mkdir -p "$DESKTOP"

TARGET="$DESKTOP/测试成功.txt"
{
  echo "测试成功"
  echo "host=$(hostname)"
  echo "round=${HPC_ROUND:-?} branch=${HPC_BRANCH:-?}"
  echo "time=$(date '+%Y-%m-%d %H:%M:%S %z')"
  echo "desktop=$DESKTOP_WIN"
  echo "by=hpc_follow (Windows install-once follower)"
} > "$TARGET"

# remove the misplaced C: copy from round 27 if it is not the real desktop
WRONG="$(cygpath -u "$USERPROFILE")/Desktop/测试成功.txt"
removed="no"
if [ -f "$WRONG" ] && [ "$WRONG" != "$TARGET" ]; then
  rm -f "$WRONG" && removed="yes"
fi

mkdir -p results/out
{
  echo "desktop_win=$DESKTOP_WIN"
  echo "desktop_file=$TARGET"
  echo "exists=$([ -f "$TARGET" ] && echo yes || echo no)"
  echo "bytes=$(wc -c < "$TARGET")"
  echo "wrong_c_copy_removed=$removed"
} > results/out/hpc_desktop_r28.txt
cat results/out/hpc_desktop_r28.txt
