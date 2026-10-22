# t3_sys1_selfcheck.ps1 - round 2: run the sys1 decision engine ON THE LOCAL MACHINE.
#
# The agent's answer to "no API, use your own ability" is code/sys1: a
# dependency-free re-implementation of laya's typed-decision protocol plus an
# engine whose logits come from the agent. This task proves it runs on the real
# Windows machine, with no network and no model download:
#   1. selfcheck.py - 21 local checks (decoder parity, routing, HTTP, MCP,
#      sockets-blocked, latency)
#   2. sys1 decide - the agent's own logits decoded by laya's math
#   3. demo_agent.py - six multi-lingual states the agent scored in conversation
#
# ASCII-only on purpose (Windows PowerShell 5.1 decodes .ps1 as ANSI/GBK).
# Write-Output only: the watcher captures stdout into the round receipt.

$ErrorActionPreference = 'Continue'
Set-Location (Join-Path $PSScriptRoot '..\..')
$repoRoot = (Get-Location).Path
$outDir = Join-Path $repoRoot 'results\sys1\local'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$reportPath = Join-Path $outDir 'SYS1_LOCAL.md'

$lines = New-Object System.Collections.Generic.List[string]
function Add-Line([string]$Text) {
    [void]$script:lines.Add($Text)
    Write-Output $Text
}

function Get-GitLine([string[]]$GitArgs) {
    try {
        $first = (& git @GitArgs 2>$null | Select-Object -First 1)
        if ($null -eq $first) { return '' }
        return ([string]$first).Trim()
    } catch {
        return ''
    }
}

function Get-Python {
    $cands = @(
        @{ Exe = 'python'; Args = @() },
        @{ Exe = 'py'; Args = @('-3') },
        @{ Exe = 'python3'; Args = @() }
    )
    foreach ($c in $cands) {
        $name = [string]$c.Exe
        if (-not (Get-Command $name -ErrorAction SilentlyContinue)) { continue }
        try {
            $probe = @('-c', 'import sys; print(sys.version.split()[0])')
            $ver = (& $name @($c.Args + $probe) 2>$null | Select-Object -First 1)
            if ($LASTEXITCODE -eq 0 -and $ver) {
                return @{ Exe = $name; Args = @($c.Args); Version = ([string]$ver).Trim() }
            }
        } catch {
        }
    }
    return $null
}

Add-Line 'SYS1_ROUND=2'
Add-Line ('time_local=' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'))
Add-Line ('time_utc=' + (Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss'))
Add-Line ('host=' + $env:COMPUTERNAME)
try {
    Add-Line ('os=' + ([string](Get-CimInstance Win32_OperatingSystem).Caption))
} catch {
    Add-Line 'os=unknown'
}
Add-Line ('git=' + (Get-GitLine @('--version')))
Add-Line ('git_branch=' + (Get-GitLine @('rev-parse', '--abbrev-ref', 'HEAD')))
Add-Line ('git_head=' + (Get-GitLine @('rev-parse', '--short', 'HEAD')))
Add-Line ('git_subject=' + (Get-GitLine @('log', '-1', '--pretty=%s')))

$py = Get-Python
if ($null -eq $py) {
    Add-Line 'PYTHON=missing'
    Add-Line 'SYS1_LOCAL_OK=False'
    try {
        [System.IO.File]::WriteAllText($reportPath, (($lines -join "`r`n") + "`r`n"), (New-Object System.Text.UTF8Encoding($false)))
    } catch {
    }
    exit 1
}
$pyExe = [string]$py.Exe
$pyArgs = @($py.Args)
Add-Line ('PYTHON=' + $pyExe + ' ' + ($pyArgs -join ' ') + ' ' + [string]$py.Version)
Add-Line ('repo_path=' + $repoRoot)

$env:PYTHONPATH = (Join-Path $repoRoot 'code\sys1')

# 1. the offline self-check (writes results\sys1\local\SELFCHECK.md/.json)
$selfCode = 1
try {
    & $pyExe @($pyArgs + @('code\sys1\selfcheck.py', '--local', '--out', 'results\sys1\local')) 2>&1 |
        ForEach-Object { Write-Output $_ }
    $selfCode = $LASTEXITCODE
} catch {
    Add-Line ('SELFCHECK_ERROR=' + $_.Exception.Message)
    $selfCode = 1
}

$passed = -1
$total = -1
$httpOk = $false
$mcpOk = $false
$p50 = ''
$scPath = Join-Path $outDir 'SELFCHECK.json'
if (Test-Path -LiteralPath $scPath) {
    try {
        $sc = Get-Content -LiteralPath $scPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $passed = [int]$sc.passed
        $total = [int]$sc.total
        $p50 = [string]$sc.latency.p50_ms
        $httpCheck = $sc.checks | Where-Object { $_.check -eq 'HTTP Jev contract' } | Select-Object -First 1
        $mcpCheck = $sc.checks | Where-Object { $_.check -eq 'MCP stdio' } | Select-Object -First 1
        if ($null -ne $httpCheck) { $httpOk = [bool]$httpCheck.ok }
        if ($null -ne $mcpCheck) { $mcpOk = [bool]$mcpCheck.ok }
    } catch {
        Add-Line ('SELFCHECK_JSON_ERROR=' + $_.Exception.Message)
    }
}
Add-Line ('SYS1_SELFCHECK=' + [string]$passed + '/' + [string]$total)
Add-Line ('SYS1_HTTP_OK=' + [string]$httpOk)
Add-Line ('SYS1_MCP_OK=' + [string]$mcpOk)
Add-Line ('SYS1_LATENCY_P50_MS=' + $p50)

# 2. the agent's own logits, decoded on this machine
$choice = ''
$conf = ''
$decideCode = 1
try {
    $decideOut = & $pyExe @($pyArgs + @(
        '-m', 'sys1', 'decide',
        '--state', '@code\sys1\examples\ticket_state.txt',
        '--questions', '@code\sys1\examples\ticket_questions.json',
        '--agent-logits', '@code\sys1\examples\ticket_agent_logits.json',
        '--json')) 2>&1
    $decideCode = $LASTEXITCODE
    $decideText = ($decideOut | Out-String)
    $dec = $decideText | ConvertFrom-Json
    $choice = [string]$dec.answers.department.choice
    $conf = [string]$dec.answers.department.answer_confidence
} catch {
    Add-Line ('DECIDE_ERROR=' + $_.Exception.Message)
    $decideCode = 1
}
Add-Line ('SYS1_DECIDE_OK=' + [string]($decideCode -eq 0))
Add-Line ('SYS1_AGENT_CHOICE=' + $choice)
Add-Line ('SYS1_ANSWER_CONFIDENCE=' + $conf)

# 3. the multi-lingual demo (writes results\sys1\AGENT_DEMO.md)
$demoCode = 1
try {
    & $pyExe @($pyArgs + @('code\sys1\demo_agent.py')) 2>&1 | ForEach-Object { Write-Output $_ }
    $demoCode = $LASTEXITCODE
} catch {
    Add-Line ('DEMO_ERROR=' + $_.Exception.Message)
    $demoCode = 1
}
Add-Line ('SYS1_DEMO_OK=' + [string]($demoCode -eq 0))

$ok = ($selfCode -eq 0) -and ($decideCode -eq 0) -and ($demoCode -eq 0) -and $httpOk -and $mcpOk -and ($choice -eq 'billing')
Add-Line ('SYS1_LOCAL_OK=' + [string]$ok)

try {
    [System.IO.File]::WriteAllText($reportPath, (($lines -join "`r`n") + "`r`n"), (New-Object System.Text.UTF8Encoding($false)))
} catch {
    Write-Output ('REPORT_WRITE_ERROR=' + $_.Exception.Message)
}
if ($ok) { exit 0 }
exit 1
