# One machine-level poller for all sparse git-sync checkouts under E:\0github.
# ASCII-only for Windows PowerShell 5.1.
param(
    [switch]$Install,
    [switch]$Remove,
    [switch]$Status,
    [switch]$Loop,
    [switch]$Once,
    [ValidateRange(1, 60)][int]$Interval = 2
)
$ErrorActionPreference = 'Continue'
$TaskName = 'git-sync-hub'
$Root = $PSScriptRoot
$ParentDir = Split-Path -Parent $PSScriptRoot
if ((Split-Path -Leaf $ParentDir) -eq '.git-sync') { $Root = Split-Path -Parent $ParentDir }
$CloneRoot = Join-Path $Root '.git-sync'
$StateRoot = Join-Path $env:LOCALAPPDATA 'git-sync\hub'
$LogPath = Join-Path $StateRoot 'hub-watch.log'

function Write-HubLog([string]$Text) {
    if (-not (Test-Path -LiteralPath $StateRoot)) { New-Item -ItemType Directory -Force -Path $StateRoot | Out-Null }
    $line = '[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Text
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
    Write-Output $line
}
function Get-CloneDirs {
    if (-not (Test-Path -LiteralPath $CloneRoot)) { return @() }
    return @(Get-ChildItem -LiteralPath $CloneRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName '.git') } | Sort-Object FullName)
}
function Sync-RemoteBranches {
    # Every registered remote acts as a project seed. Discover all its arena/*
    # branches and materialize only the result/agent paths, never source trees.
    $seeds = @(Get-CloneDirs)
    foreach ($seed in $seeds) {
        $origin = (& git -C $seed.FullName remote get-url origin 2>$null | Select-Object -First 1)
        if (-not $origin) { continue }
        $known = @{}
        foreach ($c in @(Get-CloneDirs)) {
            $u = (& git -C $c.FullName remote get-url origin 2>$null | Select-Object -First 1)
            $b = (& git -C $c.FullName branch --show-current 2>$null | Select-Object -First 1)
            if ($u -eq $origin -and $b) { $known[$b] = $true }
        }
        $refs = @(& git ls-remote --heads $origin 'refs/heads/arena/*' 2>$null)
        foreach ($line in $refs) {
            $ref = ([string]$line -split "`t")[-1]
            if (-not $ref.StartsWith('refs/heads/arena/')) { continue }
            $branch = $ref.Substring('refs/heads/'.Length)
            if ($known.ContainsKey($branch)) { continue }
            $repoName = ([string]$origin).TrimEnd('/').Split('/')[-1] -replace '\.git$',''
            if (-not $repoName) { $repoName = $seed.Name }
            $tail = ($branch -split '/')[-1]
            $name = (($repoName + '-' + $tail) -replace '[^A-Za-z0-9_.-]','-')
            $dest = Join-Path $CloneRoot $name
            if (Test-Path -LiteralPath $dest) { $known[$branch] = $true; continue }
            Write-HubLog ("discover {0} from {1}; sparse clone only" -f $branch, $origin)
            & git clone --filter=blob:none --sparse --branch $branch $origin $dest 2>&1 |
                ForEach-Object { Write-HubLog ([string]$_) }
            if ($LASTEXITCODE -ne 0) { Write-HubLog ("clone failed for {0}" -f $branch); continue }
            & git -C $dest sparse-checkout set results deliverable code skills 2>&1 | Out-Null
            $known[$branch] = $true
        }
    }
}
function Invoke-HubTick {
    Sync-RemoteBranches
    $clones = @(Get-CloneDirs)
    Write-HubLog ("tick begin; {0} sparse checkout(s)" -f $clones.Count)
    foreach ($clone in $clones) {
        $watch = Join-Path $clone.FullName 'watch.ps1'
        if (-not (Test-Path -LiteralPath $watch)) {
            Write-HubLog ("skip {0}; watch.ps1 absent" -f $clone.Name)
            continue
        }
        Write-HubLog ("poll {0}" -f $clone.Name)
        try {
            & powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $watch
            $code = $LASTEXITCODE
            Write-HubLog ("done {0}; exit={1}" -f $clone.Name, $code)
        } catch {
            Write-HubLog ("ERROR {0}: {1}" -f $clone.Name, $_.Exception.Message)
        }
    }
    $resultRoot = Join-Path $Root 'results'
    foreach ($clone in $clones) {
        $target = Join-Path $resultRoot $clone.Name
        foreach ($leaf in @('results', 'deliverable')) {
            $source = Join-Path $clone.FullName $leaf
            if (Test-Path -LiteralPath $source) {
                $dest = if ($leaf -eq 'results') { $target } else { Join-Path $target 'deliverable' }
                if (-not (Test-Path -LiteralPath $dest)) { New-Item -ItemType Directory -Force -Path $dest | Out-Null }
                Copy-Item -Path (Join-Path $source '*') -Destination $dest -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
    }
    Write-HubLog 'tick end; results mirrored without Python'
}

if ($Install) {
    if (-not (Test-Path -LiteralPath $CloneRoot)) { New-Item -ItemType Directory -Force -Path $CloneRoot | Out-Null }
    # Migrate from per-clone scheduled tasks and stop their current loops.
    foreach ($clone in @(Get-CloneDirs)) {
        $watch = Join-Path $clone.FullName 'watch.ps1'
        if (Test-Path -LiteralPath $watch) {
            try { & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $watch -Pause | Out-Null } catch { }
        }
    }
    try {
        Get-ScheduledTask -TaskName 'git-sync-watch-*' -ErrorAction SilentlyContinue |
            ForEach-Object { Unregister-ScheduledTask -TaskName $_.TaskName -Confirm:$false -ErrorAction SilentlyContinue }
    } catch { }
    $ps = Join-Path $PSHOME 'powershell.exe'
    $taskArgs = '-NoLogo -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}" -Loop -Interval {1}' -f $PSCommandPath, $Interval
    $action = New-ScheduledTaskAction -Execute $ps -Argument $taskArgs
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Days 0)
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description 'Single git-sync poller for sparse project checkouts' -Force | Out-Null
    Start-ScheduledTask -TaskName $TaskName
    Write-HubLog ("installed and started {0}; logon trigger; interval={1}m" -f $TaskName, $Interval)
    exit 0
}
if ($Remove) {
    try { Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue } catch { }
    try { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue } catch { }
    Write-Output ("removed {0}" -f $TaskName)
    exit 0
}
if ($Status) {
    try {
        $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
        $i = Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction SilentlyContinue
        Write-Output ("task={0} state={1} last_run={2}" -f $TaskName, $t.State, $i.LastRunTime)
    } catch { Write-Output ("task={0} absent" -f $TaskName) }
    Write-Output ("root={0} clones={1} log={2}" -f $Root, @(Get-CloneDirs).Count, $LogPath)
    if (Test-Path -LiteralPath $LogPath) { Get-Content -LiteralPath $LogPath -Tail 12 }
    exit 0
}
if ($Once) { Invoke-HubTick; exit 0 }
if ($Loop) {
    Write-HubLog ("loop start pid={0} interval={1}m" -f $PID, $Interval)
    while ($true) {
        Invoke-HubTick
        Start-Sleep -Seconds ($Interval * 60)
    }
}
Write-Output 'Usage: .\hub-watch.ps1 -Install | -Status | -Once | -Remove'
exit 2
