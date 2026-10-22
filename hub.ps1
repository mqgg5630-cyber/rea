# hub.ps1 - one entrypoint for every git-sync clone under the local root.
#
# The real work is code\hub\hub.py (python, testable off-Windows); this wrapper
# only finds a python 3 and points it at the right --root. It works from the
# repo root or from .git-sync\<name>, so the daily commands are:
#
#     .\hub.ps1 status              # every clone: branch, dirty, watcher, sparse paths
#     .\hub.ps1 mirror              # results\ + deliverable\ -> E:\0github\results\<name>
#     .\hub.ps1 trim                # keep only results/deliverable/code/skills
#     .\hub.ps1 prune               # drop watcher tasks whose folder is gone
#     .\hub.ps1 add <url> <branch>  # sparse clone + bootstrap + watcher
#
# ASCII-only on purpose (Windows PowerShell 5.1 decodes .ps1 as ANSI/GBK).

param(
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest
)

$ErrorActionPreference = 'Stop'

$repo = $PSScriptRoot
if (-not $repo) { $repo = (Get-Location).Path }
while ($repo -and -not (Test-Path -LiteralPath (Join-Path $repo '.git'))) {
    $up = Split-Path -Parent $repo
    if (-not $up -or $up -eq $repo) { break }
    $repo = $up
}
if (-not (Test-Path -LiteralPath (Join-Path $repo 'code\hub\hub.py'))) {
    Write-Host "[ERROR] code\hub\hub.py not found under $repo" -ForegroundColor Red
    Write-Host "        run this from a clone of the repo that carries the hub." -ForegroundColor Yellow
    exit 1
}

$py = ''
$pyArgs = @()
foreach ($cand in @(
    @{ Exe = 'python';  Args = @() },
    @{ Exe = 'py';      Args = @('-3') },
    @{ Exe = 'python3'; Args = @() }
)) {
    $name = [string]$cand.Exe
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) { continue }
    try {
        $probe = @($cand.Args) + @('-c', 'import sys; print(sys.version_info[0])')
        & $name @probe *> $null
        if ($LASTEXITCODE -eq 0) {
            $py = $name
            $pyArgs = @($cand.Args)
            break
        }
    } catch {
    }
}
if (-not $py) {
    Write-Host '[ERROR] python 3 not found on PATH' -ForegroundColor Red
    exit 1
}

$root = ''
$parent = Split-Path -Parent $repo
if ($parent -and (Split-Path -Leaf $parent) -eq '.git-sync') {
    $root = Split-Path -Parent $parent
}

$forward = @()
if ($root) { $forward += @('--root', $root) }
$forward += @($Rest)

$argv = @($pyArgs) + @((Join-Path $repo 'code\hub\hub.py')) + @($forward)
& $py @argv
exit $LASTEXITCODE
