#!/usr/bin/env bash
# Round 31: two jobs.
# (1) Desktop txt, take 3. r29 wrote it from Git Bash and its own check said
#     "exists", yet the user cannot see it on the Desktop: the Chinese file
#     name was almost certainly mangled by bash/MSYS codepage conversion on
#     its way to NTFS. So this time PowerShell itself creates the file, and
#     the Chinese name is built from Unicode code points INSIDE PowerShell
#     (no non-ASCII bytes ever cross the bash -> powershell boundary).
#     Test=U+6D4B, Shi=U+8BD5, Cheng=U+6210, Gong=U+529F.
# (2) Then run r30 (duplicate-clone cleanup) so that pending job is not
#     lost by superseding round 30.
set -eu

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command '
$d = [Environment]::GetFolderPath("Desktop")
$name = (-join ([char[]](0x6D4B, 0x8BD5, 0x6210, 0x529F))) + ".txt"
$p = Join-Path $d $name
$lines = @((-join ([char[]](0x6D4B, 0x8BD5, 0x6210, 0x529F))),
  ("host=" + $env:COMPUTERNAME),
  ("time=" + (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")),
  "by=hpc_follow round 31 (written by PowerShell, unicode-safe name)")
Set-Content -LiteralPath $p -Value $lines -Encoding UTF8
New-Item -ItemType Directory -Force -Path "results/out" | Out-Null
$rep = @("desktop=" + $d, "file=" + $p,
  ("exists=" + (Test-Path -LiteralPath $p)),
  ("bytes=" + (Get-Item -LiteralPath $p).Length))
$rep | Out-File -FilePath "results/out/hpc_desktop_r31.txt" -Encoding utf8
Get-ChildItem -LiteralPath $d -File | Select-Object -ExpandProperty Name |
  Out-File -FilePath "results/out/hpc_desktop_r31_dirlist.txt" -Encoding utf8
'
cat results/out/hpc_desktop_r31.txt

# (2) the pending cleanup from round 30, unchanged
bash code/tasks/r30.sh
