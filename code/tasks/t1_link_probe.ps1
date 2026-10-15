# t1_link_probe.ps1 - round 1 link proof for rea x git-sync.
#
# Runs ON THE LOCAL MACHINE inside code\local_check.ps1 section 4, i.e. only
# after the watcher has pulled this branch. It records which machine ran it and
# on which commit, writes results\link\LINK_PROBE.md/.json, and the watcher
# pushes them back together with the verdict:  pull -> execute -> push.
#
# Read-only on the machine (it only writes inside this clone's results\).
# ASCII-only on purpose (Windows PowerShell 5.1 decodes .ps1 as ANSI/GBK);
# Write-Output only (the watcher captures stdout into the round receipt).

$ErrorActionPreference = 'Continue'
Set-Location (Join-Path $PSScriptRoot '..\..')
$repoRoot = (Get-Location).Path
$outDir = Join-Path $repoRoot 'results\link'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$reportMd = Join-Path $outDir 'LINK_PROBE.md'
$reportJson = Join-Path $outDir 'LINK_PROBE.json'

$report = New-Object System.Collections.Generic.List[string]
function Add-ReportLine([string]$Text) {
    [void]$script:report.Add($Text)
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

# --- round number (the handshake the agent pushed)
$round = -1
try {
    $hs = Get-Content -LiteralPath (Join-Path $repoRoot 'results\status\handshake.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $round = [int]$hs.round
} catch {
    $round = -1
}

# --- configured branch vs the branch this clone is on
$cfgBranch = ''
try {
    $cfg = Get-Content -LiteralPath (Join-Path $repoRoot 'skills\git-sync\sync.config.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $cfgBranch = [string]$cfg.branch
} catch {
    $cfgBranch = ''
}
$headBranch = Get-GitLine @('rev-parse', '--abbrev-ref', 'HEAD')
$headSha = Get-GitLine @('rev-parse', '--short', 'HEAD')
$headSubject = Get-GitLine @('log', '-1', '--pretty=%s')
$gitVersion = Get-GitLine @('--version')
$remoteUrl = Get-GitLine @('remote', 'get-url', 'origin')

# --- machine facts (no user names, no secrets)
$osText = ''
try {
    $osInfo = Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop
    $osText = ([string]$osInfo.Caption).Trim() + ' (build ' + [string]$osInfo.BuildNumber + ')'
} catch {
    $osText = [string][Environment]::OSVersion.VersionString
}
$sessionId = -1
try { $sessionId = [int](Get-Process -Id $PID).SessionId } catch { $sessionId = -1 }

# --- the watcher task that is running this round
$taskName = 'git-sync-watch-' + (Split-Path -Leaf $repoRoot)
$taskState = 'not found'
$taskMode = ''
try {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
    $taskState = [string]$task.State
    $exe = [string]$task.Actions[0].Execute
    if ($exe -match 'watchhost') { $taskMode = 'zero-window launcher' }
    elseif ([string]$task.Principal.LogonType -eq 'S4U') { $taskMode = 'S4U / session 0' }
    else { $taskMode = 'powershell loop' }
} catch {
    $taskState = 'not found'
}

$branchOk = ($cfgBranch -ne '' -and $headBranch -eq $cfgBranch)
$gitOk = ($gitVersion -ne '' -and $headSha -ne '')
$probeOk = ($round -ge 1 -and $branchOk -and $gitOk)
$nowLocal = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz')
$nowUtc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm:ss')

Add-ReportLine '# rea x git-sync link probe'
Add-ReportLine ''
Add-ReportLine 'Executed ON THE LOCAL MACHINE by the git-sync watcher (code/local_check.ps1 section 4):'
Add-ReportLine 'the agent pushed this script, the watcher pulled it, ran it here, and pushes this file back.'
Add-ReportLine ''
Add-ReportLine ('LINK_PROBE_ROUND=' + $round)
Add-ReportLine ('time_local=' + $nowLocal)
Add-ReportLine ('time_utc=' + $nowUtc)
Add-ReportLine ('host=' + $env:COMPUTERNAME)
Add-ReportLine ('os=' + $osText)
Add-ReportLine ('powershell=' + [string]$PSVersionTable.PSVersion)
Add-ReportLine ('session_id=' + $sessionId + ' interactive=' + [Environment]::UserInteractive)
Add-ReportLine ('git=' + $gitVersion)
Add-ReportLine ('repo_path=' + $repoRoot)
Add-ReportLine ('remote=' + $remoteUrl)
Add-ReportLine ('config_branch=' + $cfgBranch)
Add-ReportLine ('head_branch=' + $headBranch + ' branch_matches_config=' + $branchOk)
Add-ReportLine ('head=' + $headSha + ' ' + $headSubject)
Add-ReportLine ('watcher_task=' + $taskName + ' state=' + $taskState + ' mode=' + $taskMode)
Add-ReportLine ('LINK_PROBE_OK=' + $probeOk)

try {
    Set-Content -LiteralPath $reportMd -Value $report -Encoding UTF8
    $obj = [ordered]@{
        round = $round
        ok = $probeOk
        time_local = $nowLocal
        time_utc = $nowUtc
        host = [string]$env:COMPUTERNAME
        os = $osText
        powershell = [string]$PSVersionTable.PSVersion
        session_id = $sessionId
        git = $gitVersion
        repo_path = $repoRoot
        config_branch = $cfgBranch
        head_branch = $headBranch
        head = $headSha
        watcher_task = $taskName
        watcher_state = $taskState
        watcher_mode = $taskMode
    }
    Set-Content -LiteralPath $reportJson -Value ($obj | ConvertTo-Json -Depth 4) -Encoding UTF8
    Write-Output ('== link probe report: results/link/LINK_PROBE.md (ok=' + $probeOk + ')')
} catch {
    Write-Output ('[FAIL] could not write the link probe report: ' + $_.Exception.Message)
    exit 1
}

if (-not $probeOk) {
    Write-Output '[FAIL] link probe: wrong branch, no git, or no handshake round - see the lines above'
    exit 1
}
exit 0
