#!/usr/bin/env bash
# Round 29: retry of r28 (write test txt to the real, redirected Desktop).
# r28 failed because `cygpath -u "D:\<chinese>"` returned an EMPTY string on
# this host. So: never run the localized path through cygpath - convert the
# drive path with pure bash string ops (byte-preserving, locale-proof).
set -eu

DESKTOP_WIN="$(powershell.exe -NoProfile -Command "[Environment]::GetFolderPath('Desktop')" | tr -d '\r\n')"
DRIVE="${DESKTOP_WIN%%:*}"
DRIVE="$(printf '%s' "$DRIVE" | tr '[:upper:]' '[:lower:]')"
REST="${DESKTOP_WIN#*:}"
REST="${REST//\\//}"
DESKTOP="/$DRIVE$REST"
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
WRONG_USERPROFILE="$(printf '%s' "${USERPROFILE:-}" | tr -d '\r')"
WDRIVE="$(printf '%s' "${WRONG_USERPROFILE%%:*}" | tr '[:upper:]' '[:lower:]')"
WREST="${WRONG_USERPROFILE#*:}"
WREST="${WREST//\\//}"
WRONG="/$WDRIVE$WREST/Desktop/测试成功.txt"
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
} > results/out/hpc_desktop_r29.txt
cat results/out/hpc_desktop_r29.txt
