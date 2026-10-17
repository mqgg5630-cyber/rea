#!/usr/bin/env bash
# Round 30: merge the duplicate-clone mess down to results only.
# Delete local duplicate session clones under E:/0github/git-sync, but ONLY
# when all three safety checks pass for that directory:
#   1. it is a git repo with a CLEAN working tree (no uncommitted work)
#   2. its HEAD commit exists on its remote (nothing unpushed is lost)
#   3. if it had a results/ dir, the archive copy exists in _results_archive
# Everything else is skipped and reported, never forced.
set -u
BASE="/e/0github/git-sync"
ARCHIVE="$BASE/_results_archive"
REPORT="results/out/hpc_cleanup_r30.txt"
mkdir -p results/out

TARGETS="
agentarena agentarena-int agentarena-w1 agentarena-w2
BrowserSkill-01a0b25b
git-pull-arena git-pull-arena-01a0a9ba git-pull-arena-01a0a9f0
git-pull-arena-01a0aa00 git-pull-arena-01a0ad15 git-pull-arena-01a0fa39
git-pull-arena-01a0ff64 git-pull-arena-01a0ff69 git-pull-arena-01a10bde
git-pull-arena-01a10bf3 git-pull-arena-01a10bfd git-pull-arena-s2
git-pull-arena-v268
goutoujunshi-01a101bf
image-to-editable-pptx
Light-skills-ae80330d
new-01a0a839 new-01a0a90b new-01a0ae7a new-01a0aeb9
rea-1bfdc2ed
skills1-def3bdd3
subs-check-pro-d2a66b2d3
zhongqi-01a0a95e zhongqi-01a0a984
"

size_mb() { du -sm "$1" 2>/dev/null | cut -f1; }

total_before=$(size_mb "$BASE")
{
  echo "cleanup round=${HPC_ROUND:-?} host=$(hostname) time=$(date '+%Y-%m-%d %H:%M:%S %z')"
  echo "base_total_before_mb=$total_before"
  freed=0
  for name in $TARGETS; do
    d="$BASE/$name"
    if [ ! -d "$d" ]; then echo "SKIP $name: not found"; continue; fi
    if [ ! -d "$d/.git" ]; then echo "SKIP $name: not a git repo"; continue; fi
    dirty=$(git -C "$d" status --porcelain 2>/dev/null | wc -l)
    if [ "$dirty" != "0" ]; then echo "SKIP $name: dirty files=$dirty"; continue; fi
    head_sha=$(git -C "$d" rev-parse HEAD 2>/dev/null)
    if ! git -C "$d" ls-remote origin 2>/dev/null | grep -q "^$head_sha"; then
      echo "SKIP $name: HEAD not on remote"; continue
    fi
    if [ -d "$d/results" ] && [ ! -d "$ARCHIVE/$name" ]; then
      echo "SKIP $name: results not archived"; continue
    fi
    sz=$(size_mb "$d")
    if rm -rf "$d" && [ ! -d "$d" ]; then
      echo "DELETED $name: ${sz} MB"
      freed=$((freed + sz))
    else
      echo "SKIP $name: rm failed"
    fi
  done
  total_after=$(size_mb "$BASE")
  echo "deleted_total_mb=$freed"
  echo "base_total_after_mb=$total_after"
} | tee "$REPORT"
