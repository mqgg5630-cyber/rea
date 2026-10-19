# hpc_follow.ps1 - install-once follower for a Windows check host.
#
# WHY: the Arena-side driver requests a round by committing a handshake and
# code\tasks\r<N>.sh to a branch; somebody on this machine must notice, run
# it and push the result back. Doing that by hand every conversation meant
# reinstalling/re-syncing whole repos over and over. This script is the
# install-once answer:
#
#   1. INSTALL ONCE. -Install registers ONE scheduled task (every minute +
#      at logon) and keeps all state under %LOCALAPPDATA%\hpc_follow - not
#      inside any session checkout. New conversations reuse it as-is.
#   2. RESULTS ONLY. A tick fetches ONE branch (the one being served),
#      shallow + blob-filtered, reuses ONE checkout, runs the round task,
#      commits ONLY results\ and pushes that. It never clones other repos
#      and never fetches every branch's objects.
#   3. -Prefer SEMANTICS. While the preferred branch has an unanswered
#      round, serve only it. Once answered, fall back to discovery: the
#      newest arena/* branch (by tip commit time) with an unanswered round.
#   4. HONEST INSTALL. A scheduled task that cannot reach the remote is NOT
#      "installed". -Install probes git first with prompts disabled (the
#      exact failure mode of unattended tasks: credential prompts hang or
#      publickey auth fails without an interactive session). If the probe
#      fails it does NOT register the task; it starts a resident loop from
#      this interactive shell instead (which has working credentials) and
#      says so. -Status re-probes live and quotes git's own error.
#
# ROUND PROTOCOL (same handshake as the rest of this repo):
#   results/status/handshake.json {"round": N,
#       "arena_state": "awaiting_check", "local_state": "pending", ...}
#   code/tasks/r<N>.sh            the job (run with Git Bash)
# The follower answers in results/ only: updated handshake.json,
# check_r<N>_<stamp>.log and hpc_r<N>.json (receipt), one commit, one push.
#
# Usage (PowerShell, from any directory):
#   .\code\hpc_follow.ps1 -Install -Repo <git-url> [-Prefer arena/branch]
#   .\code\hpc_follow.ps1 -Status
#   .\code\hpc_follow.ps1 -Tick          (scheduled-task entry point)
#   .\code\hpc_follow.ps1 -Uninstall
#
# ASCII-only on purpose (Windows PowerShell 5.1 decodes BOM-less .ps1 as
# ANSI/GBK). Write-Output only (callers capture stdout).

[CmdletBinding()]
param(
    [switch]$Install,
    [switch]$Status,
    [switch]$Tick,
    [switch]$RunLoop,
    [switch]$Uninstall,
    [string]$Repo = '',
    [string]$Prefer = $null,
    [int]$TimeoutMin = 120
)

$ErrorActionPreference = 'Continue'
$script:TaskName = 'hpc_follow_tick'
$script:Marker = 'hpc_follow'
$script:HandshakePath = 'results/status/handshake.json'
$script:ExcludePatterns = @('.env', '.env.*', '**/*.pem', '**/*.key',
    '**/credentials*', '**/*secret*', '**/*token*')

# ---------------------------------------------------------------- utilities

function Get-FollowHome {
    if ($env:HPC_FOLLOW_HOME) { return $env:HPC_FOLLOW_HOME }
    if ($env:LOCALAPPDATA) { return (Join-Path $env:LOCALAPPDATA 'hpc_follow') }
    return (Join-Path $HOME '.local/state/hpc_follow')
}

function Get-NowStr { return (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') }

function Write-FollowLog([string]$Msg) {
    # file only, on purpose: Write-Output here would pollute the return
    # stream of every function that logs (PowerShell returns ALL uncaptured
    # output), breaking exit codes and boolean checks upstream.
    $line = '[{0}] {1}' -f (Get-NowStr), $Msg
    try {
        $home2 = Get-FollowHome
        if (-not (Test-Path -LiteralPath $home2)) {
            New-Item -ItemType Directory -Force -Path $home2 | Out-Null
        }
        Add-Content -LiteralPath (Join-Path $home2 'follow.log') -Value $line -Encoding UTF8
    } catch { }
}

function Set-ObjProp($Obj, [string]$Name, $Value) {
    if ($Obj.PSObject.Properties[$Name]) { $Obj.$Name = $Value }
    else { $Obj | Add-Member -NotePropertyName $Name -NotePropertyValue $Value }
}

function Read-JsonFile([string]$Path, $Default) {
    try {
        if (Test-Path -LiteralPath $Path) {
            $txt = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
            if ($txt) { return ($txt | ConvertFrom-Json) }
        }
    } catch { }
    return $Default
}

function Save-JsonFile([string]$Path, $Obj) {
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    $tmp = $Path + '.tmp'
    ($Obj | ConvertTo-Json -Depth 8) | Set-Content -LiteralPath $tmp -Encoding UTF8
    Move-Item -LiteralPath $tmp -Destination $Path -Force
}

function Set-UnattendedGitEnv {
    $env:GIT_TERMINAL_PROMPT = '0'
    $env:GCM_INTERACTIVE = 'Never'
    if (-not $env:GIT_SSH_COMMAND) {
        $env:GIT_SSH_COMMAND = 'ssh -o BatchMode=yes'
    }
}

function Invoke-Capture {
    # Run a process with a hard timeout; return @{rc; out}.
    param([string]$File, [string[]]$ArgList, [string]$Cwd = '',
          [int]$TimeoutSec = 120, [hashtable]$ExtraEnv = @{})
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $File
    $psi.Arguments = (($ArgList | ForEach-Object {
        if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ }
    }) -join ' ')
    if ($Cwd) { $psi.WorkingDirectory = $Cwd }
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    foreach ($k in $ExtraEnv.Keys) { $psi.EnvironmentVariables[$k] = [string]$ExtraEnv[$k] }
    $p = New-Object System.Diagnostics.Process
    $p.StartInfo = $psi
    [void]$p.Start()
    $outTask = $p.StandardOutput.ReadToEndAsync()
    $errTask = $p.StandardError.ReadToEndAsync()
    if (-not $p.WaitForExit($TimeoutSec * 1000)) {
        try { $p.Kill() } catch { }
        return @{ rc = 124; out = ('TIMEOUT after {0}s running {1}' -f $TimeoutSec, $File) }
    }
    $out = ''
    try { $out = $outTask.Result + $errTask.Result } catch { }
    return @{ rc = $p.ExitCode; out = [string]$out }
}

function Invoke-Git {
    param([string]$RepoDir, [string[]]$GitArgs, [int]$TimeoutSec = 180)
    $all = @('-C', $RepoDir) + $GitArgs
    return (Invoke-Capture -File 'git' -ArgList $all -TimeoutSec $TimeoutSec)
}

function Test-AgentNote {
    # Windows OpenSSH agent is a service, so unlike cron it is reachable
    # from scheduled tasks of the same user; we only report, never guess.
    $svc = $null
    try { $svc = Get-Service -Name 'ssh-agent' -ErrorAction SilentlyContinue } catch { }
    if ($svc) { return ('ssh-agent service: {0}' -f $svc.Status) }
    return 'ssh-agent service: not found (https/GCM auth unaffected)'
}

# ------------------------------------------------------------------- config

function Get-ConfigPath { return (Join-Path (Get-FollowHome) 'config.json') }
function Get-StatePath { return (Join-Path (Get-FollowHome) 'state.json') }
function Get-RepoDir { return (Join-Path (Get-FollowHome) 'repo') }

function Load-Config {
    $cfg = Read-JsonFile (Get-ConfigPath) $null
    if (-not $cfg) { $cfg = [pscustomobject]@{} }
    if (-not $cfg.PSObject.Properties['repo']) { $cfg | Add-Member repo '' }
    if (-not $cfg.PSObject.Properties['prefer']) { $cfg | Add-Member prefer '' }
    if (-not $cfg.PSObject.Properties['timeout_min']) { $cfg | Add-Member timeout_min 120 }
    if (-not $cfg.PSObject.Properties['branch_glob']) { $cfg | Add-Member branch_glob 'arena/*' }
    return $cfg
}

function Load-State {
    $st = Read-JsonFile (Get-StatePath) $null
    if (-not $st) { $st = [pscustomobject]@{} }
    if (-not $st.PSObject.Properties['served']) { $st | Add-Member served ([pscustomobject]@{}) }
    if (-not $st.PSObject.Properties['last_tick']) { $st | Add-Member last_tick '' }
    if (-not $st.PSObject.Properties['last_action']) { $st | Add-Member last_action '' }
    if (-not $st.PSObject.Properties['last_detail']) { $st | Add-Member last_detail '' }
    return $st
}

function Probe-Git([string]$RepoUrl) {
    Set-UnattendedGitEnv
    $r = Invoke-Capture -File 'git' -ArgList @('ls-remote', '--heads', $RepoUrl) -TimeoutSec 60
    if ($r.rc -eq 0) { return @{ ok = $true; detail = 'ls-remote ok' } }
    $lines = @($r.out -split "`n" | Where-Object { $_.Trim() })
    $tail = if ($lines.Count) { $lines[$lines.Count - 1].Trim() } else { 'no output' }
    return @{ ok = $false; detail = $tail }
}

# ------------------------------------------------------------- repo plumbing

function Ensure-Repo($Cfg) {
    $d = Get-RepoDir
    if (-not (Test-Path -LiteralPath (Join-Path $d '.git'))) {
        New-Item -ItemType Directory -Force -Path $d | Out-Null
        $r = Invoke-Capture -File 'git' -ArgList @('init', '-q', $d)
        if ($r.rc -ne 0) { Write-FollowLog ('git init failed: ' + $r.out.Trim()); return $false }
        [void](Invoke-Git $d @('remote', 'add', 'origin', $Cfg.repo))
        [void](Invoke-Git $d @('config', 'user.name', 'hpc-follow'))
        [void](Invoke-Git $d @('config', 'user.email', 'hpc-follow@localhost'))
    } else {
        $cur = Invoke-Git $d @('remote', 'get-url', 'origin')
        if ($cur.out.Trim() -ne $Cfg.repo) {
            [void](Invoke-Git $d @('remote', 'set-url', 'origin', $Cfg.repo))
        }
    }
    return $true
}

function Fetch-Tip([string]$D, [string]$Branch) {
    # Shallow, single-branch, blob-filtered: cheap to probe AND to serve.
    $ref = 'refs/follow/' + $Branch
    $r = Invoke-Git $D @('fetch', '-q', '--depth', '1', '--filter=blob:none',
        'origin', ('+refs/heads/{0}:{1}' -f $Branch, $ref))
    return ($r.rc -eq 0)
}

function Read-At([string]$D, [string]$Branch, [string]$Path) {
    $r = Invoke-Git $D @('show', ('refs/follow/{0}:{1}' -f $Branch, $Path))
    if ($r.rc -eq 0) { return $r.out }
    return $null
}

function Get-TipTime([string]$D, [string]$Branch) {
    $r = Invoke-Git $D @('log', '-1', '--format=%ct', ('refs/follow/' + $Branch))
    $t = 0
    [void][int]::TryParse($r.out.Trim(), [ref]$t)
    return $t
}

function Get-PendingRound([string]$D, [string]$Branch, $State) {
    $raw = Read-At $D $Branch $script:HandshakePath
    if (-not $raw) { return $null }
    $hs = $null
    try { $hs = $raw | ConvertFrom-Json } catch { return $null }
    if ($null -eq $hs.round) { return $null }
    if ($hs.arena_state -notin @('awaiting_check', 'requested', 'pending')) { return $null }
    if ($hs.local_state -in @('passed', 'failed')) { return $null }
    $sv = $State.served.PSObject.Properties[[string]$Branch]
    if ($sv -and $sv.Value.round -eq $hs.round -and
        $sv.Value.result -in @('passed', 'failed')) { return $null }
    $taskRaw = Read-At $D $Branch ('code/tasks/r{0}.sh' -f $hs.round)
    if (-not $taskRaw) {
        Write-FollowLog ('candidate {0}: round {1} pending but task file unreadable' -f $Branch, $hs.round)
        return $null
    }
    return @{ round = [int]$hs.round; hs = $hs }
}

function Find-BranchToServe([string]$D, $Cfg, $State) {
    Set-UnattendedGitEnv
    $lr = Invoke-Capture -File 'git' -ArgList @('ls-remote', '--heads', $Cfg.repo) -TimeoutSec 60
    if ($lr.rc -ne 0) {
        $lines = @($lr.out -split "`n" | Where-Object { $_.Trim() })
        $head = if ($lines.Count) { $lines[0].Trim() } else { 'no output' }
        throw ('ls-remote failed (exit {0}): {1}' -f $lr.rc, $head)
    }
    $branches = @()
    foreach ($line in ($lr.out -split "`n")) {
        $idx = $line.IndexOf('refs/heads/')
        if ($idx -ge 0) { $branches += $line.Substring($idx + 11).Trim() }
    }
    $cands = @()
    foreach ($b in $branches) {
        $isPrefer = ($Cfg.prefer -and $b -eq $Cfg.prefer)
        if (-not $isPrefer -and $b -notlike $Cfg.branch_glob) { continue }
        if (-not (Fetch-Tip $D $b)) { continue }
        $p = Get-PendingRound $D $b $State
        if (-not $p -and $isPrefer) {
            # the preferred branch is the one we must never silently skip:
            # record what the handshake at the fetched tip actually says
            $rawDbg = Read-At $D $b $script:HandshakePath
            if (-not $rawDbg) {
                Write-FollowLog ('candidate {0}: no handshake at fetched tip' -f $b)
            } else {
                try {
                    $dbg = $rawDbg | ConvertFrom-Json
                    Write-FollowLog ('candidate {0}: not pending (round={1} arena_state={2} local_state={3})' -f
                        $b, $dbg.round, $dbg.arena_state, $dbg.local_state)
                } catch {
                    Write-FollowLog ('candidate {0}: handshake unparsable: {1}' -f $b, $_.Exception.Message)
                }
            }
        }
        if ($p) {
            $cands += [pscustomobject]@{ branch = $b; round = $p.round
                hs = $p.hs; tip = (Get-TipTime $D $b); prefer = [bool]$isPrefer }
        }
    }
    if (-not $cands.Count) { return $null }
    $pref = @($cands | Where-Object { $_.prefer })
    if ($pref.Count) { return $pref[0] }
    return ($cands | Sort-Object tip -Descending | Select-Object -First 1)
}

function Find-Bash {
    $g = Get-Command git -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($g -and $g.Source) {
        $gitDir = Split-Path -Parent (Split-Path -Parent $g.Source)
        foreach ($cand in @((Join-Path $gitDir 'bin\bash.exe'),
                            (Join-Path $gitDir 'usr\bin\bash.exe'))) {
            if (Test-Path -LiteralPath $cand) { return $cand }
        }
    }
    $b = Get-Command bash -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($b) { return [string]$b.Source }
    $b2 = Get-Command bash.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($b2) { return [string]$b2.Source }
    return $null
}

function Serve-Round([string]$D, $Cfg, [string]$Branch, [int]$Round, $Hs) {
    $host2 = $env:COMPUTERNAME
    if (-not $host2) { $host2 = [System.Net.Dns]::GetHostName() }
    $receipt = [ordered]@{ round = $Round; branch = $Branch; host = $host2
        started = (Get-NowStr); fetch_error = $null
        agent = (Test-AgentNote); task = ('code/tasks/r{0}.sh' -f $Round)
        result = 'failed'; detail = '' }

    [void](Invoke-Git $D @('checkout', '-q', '-f', '-B', 'follow-work',
        ('refs/follow/' + $Branch)))
    [void](Invoke-Git $D @('reset', '-q', '--hard', ('refs/follow/' + $Branch)))

    $bash = Find-Bash
    if (-not $bash) {
        $receipt.detail = 'no bash found (install Git for Windows)'
        return $receipt
    }
    $taskPath = Join-Path $D ('code/tasks/r{0}.sh' -f $Round)
    $r = Invoke-Capture -File $bash -ArgList @($taskPath) -Cwd $D `
        -TimeoutSec ([int]$Cfg.timeout_min * 60) `
        -ExtraEnv @{ HPC_ROUND = [string]$Round; HPC_BRANCH = $Branch }
    $result = if ($r.rc -eq 0) { 'passed' } else { 'failed' }
    $receipt.result = $result
    $receipt.exit_code = $r.rc
    $receipt.finished = Get-NowStr
    if ($r.rc -ne 0) { $receipt.detail = ('task exit {0}' -f $r.rc) }

    # write the answer into results/ ONLY
    $stamp = (Get-Date).ToString('yyyyMMdd-HHmmss')
    $statusDir = Join-Path $D 'results/status'
    New-Item -ItemType Directory -Force -Path $statusDir | Out-Null
    $logName = 'check_r{0}_{1}.log' -f $Round, $stamp
    [System.IO.File]::WriteAllText((Join-Path $statusDir $logName),
        [string]$r.out, (New-Object System.Text.UTF8Encoding($false)))
    $hs2 = $Hs
    Set-ObjProp $hs2 'local_state' $result
    Set-ObjProp $hs2 'local_updated' (Get-NowStr)
    Set-ObjProp $hs2 'host' $host2
    Set-ObjProp $hs2 'note' ('hpc_follow: round {0} {1} on {2}' -f $Round, $result, $host2)
    Save-JsonFile (Join-Path $statusDir 'handshake.json') $hs2
    Save-JsonFile (Join-Path $statusDir ('hpc_r{0}.json' -f $Round)) $receipt

    # results-only sync: drop everything the task wrote outside results/
    # (the exclude matters: a plain checkout would revert the handshake too)
    [void](Invoke-Git $D @('checkout', '-q', '--', '.', ':(exclude)results'))
    [void](Invoke-Git $D @('clean', '-qfd', '--', '.', ':(exclude)results'))
    [void](Invoke-Git $D @('add', '-A', '--', 'results'))
    $staged = Invoke-Git $D @('diff', '--cached', '--name-only')
    $kept = @()
    foreach ($name in @($staged.out -split "`n")) {
        $n = $name.Trim()
        if (-not $n) { continue }
        $excluded = $false
        foreach ($pat in $script:ExcludePatterns) {
            if ($n -like $pat) { $excluded = $true; break }
        }
        if ($excluded) { [void](Invoke-Git $D @('reset', '-q', '--', $n)) }
        else { $kept += $n }
    }
    if (-not $kept.Count) {
        $receipt.detail = ($receipt.detail + ' nothing to push').Trim()
        return $receipt
    }
    $c = Invoke-Git $D @('commit', '-q', '-m',
        ('local: auto: check round {0} {1} on {2}' -f $Round, $result, $host2))
    if ($c.rc -ne 0) {
        $receipt.detail = 'commit failed: ' + $c.out.Trim()
        return $receipt
    }
    $p = Invoke-Git $D @('push', '-q', 'origin', ('HEAD:refs/heads/' + $Branch))
    if ($p.rc -ne 0) {
        $receipt.detail = 'push failed: ' + $p.out.Trim()
        $receipt.result = 'failed'
    }
    return $receipt
}

# ---------------------------------------------------------------------- tick

function Invoke-Tick($Cfg) {
    $homeDir = Get-FollowHome
    New-Item -ItemType Directory -Force -Path $homeDir | Out-Null
    $lockPath = Join-Path $homeDir 'tick.lock'
    $lock = $null
    try {
        $lock = [System.IO.File]::Open($lockPath,
            [System.IO.FileMode]::OpenOrCreate, [System.IO.FileAccess]::ReadWrite,
            [System.IO.FileShare]::None)
    } catch {
        Write-FollowLog 'another tick is running - yielding this minute'
        return 0
    }
    $state = Load-State
    $state.last_tick = Get-NowStr
    try {
        Set-UnattendedGitEnv
        if (-not (Ensure-Repo $Cfg)) {
            $state.last_action = 'repo init failed'
            return 1
        }
        $d = Get-RepoDir
        $found = $null
        try { $found = Find-BranchToServe $d $Cfg $state }
        catch {
            $state.last_action = 'fetch_failed'
            $state.last_detail = $_.Exception.Message
            Write-FollowLog ('tick: fetch_failed: {0} ({1})' -f
                $_.Exception.Message, (Test-AgentNote))
            return 1
        }
        if (-not $found) {
            $state.last_action = 'no unanswered round'
            Write-FollowLog ('tick: no unanswered round (prefer={0})' -f $Cfg.prefer)
            return 0
        }
        Write-FollowLog ('tick: serving round {0} on {1}' -f $found.round, $found.branch)
        $receipt = Serve-Round $d $Cfg $found.branch $found.round $found.hs
        $entry = [pscustomobject]@{ round = $found.round
            result = $receipt.result; finished = (Get-NowStr) }
        $prop = $state.served.PSObject.Properties[[string]$found.branch]
        if ($prop) { $prop.Value = $entry } else {
            $state.served | Add-Member -NotePropertyName ([string]$found.branch) -NotePropertyValue $entry
        }
        $state.last_action = 'round {0} on {1}: {2}' -f $found.round, $found.branch, $receipt.result
        $state.last_detail = [string]$receipt.detail
        if ($receipt.result -eq 'passed') { return 0 } else { return 1 }
    } finally {
        Save-JsonFile (Get-StatePath) $state
        if ($lock) { $lock.Close() }
    }
}

# ------------------------------------------------------------------ install

function Get-SelfCmd {
    $self = $PSCommandPath
    if (-not $self) { $self = $MyInvocation.MyCommand.Path }
    return $self
}

function Start-ResidentLoop {
    $pidPath = Join-Path (Get-FollowHome) 'daemon.pid'
    if (Test-Path -LiteralPath $pidPath) {
        $old = 0
        [void][int]::TryParse((Get-Content -LiteralPath $pidPath -Raw), [ref]$old)
        if ($old -and (Get-Process -Id $old -ErrorAction SilentlyContinue)) { return $old }
    }
    $self = Get-SelfCmd
    $logPath = Join-Path (Get-FollowHome) 'daemon.log'
    $proc = Start-Process -FilePath 'powershell.exe' -WindowStyle Hidden -PassThru `
        -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
            ('"{0}"' -f $self), '-RunLoop') `
        -RedirectStandardOutput $logPath -RedirectStandardError ($logPath + '.err')
    Set-Content -LiteralPath $pidPath -Value $proc.Id -Encoding ASCII
    return $proc.Id
}

function Get-HiddenLauncher([string]$Mode = 'Tick') {
    # A scheduled task that launches powershell.exe directly FLASHES a
    # console window for a split second even with -WindowStyle Hidden:
    # the console exists before PowerShell processes the switch. The fix
    # is to never create a console at all: wscript.exe is a GUI-subsystem
    # host, and its Run(..., 0, ...) starts the child truly windowless.
    # This writes (idempotently) the .vbs launcher and returns its path.
    $vbs = Join-Path (Get-FollowHome) ('run_{0}_hidden.vbs' -f $Mode.ToLower())
    $self = Get-SelfCmd
    $body = @(
        'Set sh = CreateObject("WScript.Shell")'
        ('sh.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File ""{0}"" -{1}", 0, False' -f $self, $Mode)
    ) -join "`r`n"
    $needWrite = $true
    if (Test-Path -LiteralPath $vbs) {
        $old = Get-Content -LiteralPath $vbs -Raw -ErrorAction SilentlyContinue
        if ($old -eq ($body + "`r`n")) { $needWrite = $false }
    }
    if ($needWrite) {
        Set-Content -LiteralPath $vbs -Value $body -Encoding ASCII
    }
    return $vbs
}

function Install-CronTask($Cfg) {
    $vbs = Get-HiddenLauncher
    # wscript //B = no script-error popups, //Nologo = no banner; the task
    # itself is the only thing being registered - no console, no flash
    $action = New-ScheduledTaskAction -Execute 'wscript.exe' `
        -Argument ('//B //Nologo "{0}"' -f $vbs)
    $t1 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
        -RepetitionInterval (New-TimeSpan -Minutes 1)
    $t2 = New-ScheduledTaskTrigger -AtLogOn
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Hours 3) -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName $script:TaskName -Action $action `
        -Trigger @($t1, $t2) -Settings $settings -Force | Out-Null
    return $true
}

function Out-Line([string]$Text) { [Console]::WriteLine($Text) }

function Invoke-Install {
    $cfg = Load-Config
    if ($Repo) { $cfg.repo = $Repo }
    if (-not $cfg.repo) {
        $r = Invoke-Capture -File 'git' -ArgList @('remote', 'get-url', 'origin')
        if ($r.rc -eq 0) { $cfg.repo = $r.out.Trim() }
    }
    if (-not $cfg.repo) {
        Out-Line '[FAIL] no repo URL: pass -Repo <url> (or run inside a checkout)'
        return 1
    }
    if ($null -ne $Prefer) { $cfg.prefer = $Prefer }
    $cfg.timeout_min = $TimeoutMin
    New-Item -ItemType Directory -Force -Path (Get-FollowHome) | Out-Null
    Save-JsonFile (Get-ConfigPath) $cfg

    Out-Line ('repo:   {0}' -f $cfg.repo)
    Out-Line ('prefer: {0}' -f $(if ($cfg.prefer) { $cfg.prefer } else { '(none - discovery mode)' }))
    Out-Line (Test-AgentNote)

    $probe = Probe-Git $cfg.repo
    if (-not $probe.ok) {
        # Do NOT register a task that cannot work (the unattended-auth trap:
        # it would look installed and fail silently every minute).
        Out-Line ('[WARN] unattended probe FAILED: {0}' -f $probe.detail)
        Out-Line '       not registering the scheduled task; starting a resident'
        Out-Line '       loop from this interactive shell instead (it inherits'
        Out-Line '       your working credentials).'
        $pid2 = Start-ResidentLoop
        Out-Line ('resident loop pid: {0} (log: {1})' -f $pid2,
            (Join-Path (Get-FollowHome) 'daemon.log'))
        Out-Line 'fix path: make git work non-interactively (credential manager'
        Out-Line 'token or a passphrase-less deploy key), then re-run -Install'
        Out-Line 'once and the scheduled task takes over.'
        return 0
    }
    Out-Line ('unattended probe: OK ({0})' -f $probe.detail)
    if ($env:OS -notlike 'Windows*') {
        Out-Line '[WARN] not on Windows: scheduled task not registered here.'
        Out-Line '       (run -Install on the Windows host to register the task;'
        Out-Line '        the tick logic itself was exercised by the test suite)'
        return 0
    }
    try {
        [void](Install-CronTask $cfg)
        Out-Line ('scheduled task "{0}" registered (every minute + at logon), idempotent' -f $script:TaskName)
    } catch {
        Out-Line ('[WARN] scheduled task registration failed: {0}' -f $_.Exception.Message)
        Out-Line ('falling back to resident loop, pid: {0}' -f (Start-ResidentLoop))
        return 0
    }
    # act now once, so a waiting round is not stuck until the next minute
    $vbs = Get-HiddenLauncher 'Tick'
    Start-Process -FilePath 'wscript.exe' `
        -ArgumentList @('//B', '//Nologo', ('"{0}"' -f $vbs)) | Out-Null
    Out-Line 'kicked an immediate first tick in the background'
    return 0
}

function Invoke-Status {
    $cfg = Load-Config
    $state = Load-State
    Out-Line ('installed at: {0}' -f (Get-FollowHome))
    Out-Line ('repo:   {0}' -f $(if ($cfg.repo) { $cfg.repo } else { '(unset - run -Install)' }))
    Out-Line ('prefer: {0}' -f $(if ($cfg.prefer) { $cfg.prefer } else { '(none - discovery mode)' }))
    $taskState = 'unknown (not on Windows or no permission)'
    try {
        $t = Get-ScheduledTask -TaskName $script:TaskName -ErrorAction SilentlyContinue
        $taskState = if ($t) { [string]$t.State } else { 'not registered' }
    } catch { }
    Out-Line ('scheduled task: {0}' -f $taskState)
    $pidPath = Join-Path (Get-FollowHome) 'daemon.pid'
    $daemon = 'not running'
    if (Test-Path -LiteralPath $pidPath) {
        $old = 0
        [void][int]::TryParse((Get-Content -LiteralPath $pidPath -Raw), [ref]$old)
        if ($old -and (Get-Process -Id $old -ErrorAction SilentlyContinue)) {
            $daemon = 'running pid {0}' -f $old
        }
    }
    Out-Line ('resident loop: {0}' -f $daemon)
    Out-Line (Test-AgentNote)
    if ($cfg.repo) {
        $probe = Probe-Git $cfg.repo
        Out-Line ('unattended git probe: {0} - {1}' -f
            $(if ($probe.ok) { 'OK' } else { 'FAILED' }), $probe.detail)
    }
    Out-Line ('last tick: {0}' -f $state.last_tick)
    Out-Line ('last action: {0}' -f $state.last_action)
    if ($state.last_detail) { Out-Line ('last detail: {0}' -f $state.last_detail) }
    foreach ($p in $state.served.PSObject.Properties) {
        Out-Line ('  served {0}: round {1} -> {2} ({3})' -f
            $p.Name, $p.Value.round, $p.Value.result, $p.Value.finished)
    }
    return 0
}

function Invoke-Uninstall {
    try {
        Unregister-ScheduledTask -TaskName $script:TaskName -Confirm:$false -ErrorAction SilentlyContinue
    } catch { }
    $pidPath = Join-Path (Get-FollowHome) 'daemon.pid'
    if (Test-Path -LiteralPath $pidPath) {
        $old = 0
        [void][int]::TryParse((Get-Content -LiteralPath $pidPath -Raw), [ref]$old)
        if ($old) { Stop-Process -Id $old -Force -ErrorAction SilentlyContinue }
    }
    Out-Line ('scheduled task removed; resident loop stopped. State kept at {0} (delete it manually for a full wipe)' -f (Get-FollowHome))
    return 0
}

# ---------------------------------------------------------------------- main

if ($Install) { exit (Invoke-Install) }
if ($Status) { exit (Invoke-Status) }
if ($Uninstall) { exit (Invoke-Uninstall) }
if ($RunLoop) {
    $cfg = Load-Config
    while ($true) {
        [void](Invoke-Tick $cfg)
        Start-Sleep -Seconds 60
    }
}
if ($Tick) {
    $cfg = Load-Config
    if (-not $cfg.repo) {
        Write-Output 'not installed (no repo configured); run -Install first'
        exit 1
    }
    $code = Invoke-Tick $cfg
    # say the outcome on the console too; the log file alone made a failed
    # tick look like "nothing happened" in the field
    $st = Load-State
    [Console]::WriteLine(('tick done (exit {0}): {1} {2}' -f $code, $st.last_action, $st.last_detail))
    exit $code
}
Write-Output 'usage: hpc_follow.ps1 -Install [-Repo <url>] [-Prefer <branch>] | -Status | -Tick | -Uninstall'
exit 2
