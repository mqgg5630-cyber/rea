#!/usr/bin/env bash
# Round 26 smoke test for hpc_follow.ps1 (Windows install-once follower).
# Runs on the Windows host via Git Bash. Contract: write ONLY under results/.
set -eu
mkdir -p results/out
{
  echo "hpc_follow smoke round=${HPC_ROUND:-?} branch=${HPC_BRANCH:-?}"
  echo "host=$(hostname) date=$(date '+%Y-%m-%d %H:%M:%S %z')"
  echo "os=$(uname -a)"
} > results/out/hpc_smoke_r26.txt
cat results/out/hpc_smoke_r26.txt
