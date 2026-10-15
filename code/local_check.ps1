# local_check.ps1 (rea, from git-pull-arena arena/01a0ff69) - this repo's
# checks, run on the real machine when the agent requests one.
# Section 4 is the remote task runner: code\tasks\manifest.json maps a round
# number to scripts in code\tasks\ that execute ON THIS MACHINE (that is how the
# agent "runs code locally": pull -> run -> push the receipt back).
# watch.ps1 executes this whenever the agent requests a check
# (config key check_cmd), captures all output to
# results\status\check_rN_<stamp>.log and pushes the verdict back.
#
# Exit 0 = passed, anything else = failed. Edit freely - this file belongs to
# the repo, the installer only creates it when it is missing.
#
# Ideas for real checks (pick what fits the repo):
#   - deliverable files exist and have sane sizes
#   - open an Office file via COM to prove it is not corrupt
#   - python -c "import torch; assert torch.cuda.is_available()"  (GPU smoke test)
#   - run a script from code\ and compare its output
#
# ASCII-only on purpose (Windows PowerShell 5.1 decodes .ps1 as ANSI/GBK).

$ErrorActionPreference = 'Continue'
Set-Location (Join-Path $PSScriptRoot '..')   # repo root (this file lives in code\)

$fail = 0

# 1. the standard gate (.ps1 ASCII + branch guard + script consistency)
#    (forward slashes on purpose: this also runs under the scheduled task,
#     where bash may eat backslashes; Write-Output on purpose: the watcher
#     captures stdout, and PS 5.1 Write-Host bypasses it)
if (Test-Path -LiteralPath '.\code\check_all.sh') {
    # prefer the bash that ships with the git we use - a WSL bash.exe on PATH
    # cannot always read a Windows working directory and would look like a
    # gate failure when it is really an environment mismatch
    $bashExe = ''
    $g = Get-Command git -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($g -and $g.Source) {
        $gitDir = Split-Path -Parent (Split-Path -Parent $g.Source)
        foreach ($cand in @((Join-Path $gitDir 'bin\bash.exe'), (Join-Path $gitDir 'usr\bin\bash.exe'))) {
            if (Test-Path -LiteralPath $cand) { $bashExe = $cand; break }
        }
    }
    $bashFrom = 'git'
    if (-not $bashExe) {
        $b = Get-Command bash -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($b) { $bashExe = [string]$b.Source; $bashFrom = 'PATH' }
    }
    if (-not $bashExe) {
        Write-Output '[WARN] no bash found (install Git for Windows) - the repo gate was skipped'
    } else {
        $gateOut = (& $bashExe 'code/check_all.sh' 2>&1 | Out-String)
        $gateCode = $LASTEXITCODE
        if ($gateOut) { Write-Output $gateOut }
        if ($gateCode -ne 0) {
            if (-not $gateOut) {
                Write-Output ('[WARN] the gate produced no output via ' + $bashExe + ' (' + $bashFrom + ') - skipped here, it still runs before every agent push')
            } else {
                Write-Output ('[FAIL] gate failed (exit ' + $gateCode + ')')
                $fail = 1
            }
        } else {
            Write-Output ('   (gate ran via ' + $bashExe + ' [' + $bashFrom + '])')
        }
    }
}

# 1b. the two hard requirements are asserted strictly in section 2 (2a/2b) -
#     they fail the round on purpose, because "push needs a click" and
#     "watcher flashes a window" are exactly what v2.5.0 had to fix.

# 2. v2.5.0 acceptance: the two hard requirements, asserted ON THIS MACHINE.
#    (Write-Output, not Write-Host: the watcher captures stdout only.)
#    2a. silent push - git must get a credential with ALL prompts disabled
if (Test-Path -LiteralPath '.\auth.ps1') {
    try {
        $auth = ((& .\auth.ps1 -Json -Verify) | Out-String) | ConvertFrom-Json
        if ($auth.push_dry_run -in @('passed', 'not-fast-forward') -and $auth.lsremote -eq 'passed') {
            if ($auth.push_dry_run -eq 'not-fast-forward') {
                Write-Output '== accept 2a: silent push PROVEN by the credential probe;'
                Write-Output '   the dry-run was only REJECTED (not a fast-forward) - the server had already accepted the token.'
                Write-Output '   run .\sync.ps1 so the next real push is a fast-forward.'
            } else {
                Write-Output '== accept 2a: silent push PROVEN (ls-remote + push --dry-run, prompts disabled)'
            }
        } else {
            Write-Output ("[FAIL] accept 2a: silent push NOT proven (lsremote=" + $auth.lsremote + " push_dry_run=" + $auth.push_dry_run + ")")
            Write-Output ("       detail: " + $auth.push_dry_run_detail)
            Write-Output '       fix once with:  .\auth.ps1 -Setup  then  .\auth.ps1 -Verify'
            $fail = 1
        }
    } catch {
        Write-Output '[FAIL] accept 2a: auth.ps1 probe failed (run .\auth.ps1 by hand to see why)'
        $fail = 1
    }
} else {
    Write-Output '[FAIL] accept 2a: auth.ps1 is missing (upgrade the skill)'
    $fail = 1
}

#    2b. how visible is the watcher? Graded, and the grade is printed:
#          zero-window launcher  -> nothing ever appears            (best)
#          S4U / session 0       -> nothing ever appears            (best, needs admin)
#          -Loop in one process  -> ONE brief flash per logon       (acceptable)
#          per-poll process      -> a flash every N minutes         (FAIL)
$taskName = 'git-sync-watch-' + (Split-Path -Leaf (Get-Location).Path)
try {
    $t = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
    $exec  = [string]$t.Actions[0].Execute
    $argl  = [string]$t.Actions[0].Arguments
    $logon = [string]$t.Principal.LogonType
    if ($exec -match 'watchhost') {
        Write-Output ("== accept 2b: ZERO window - launcher exe: " + $exec)
    } elseif ($logon -eq 'S4U' -or $logon -eq 'Password') {
        Write-Output ("== accept 2b: ZERO window - session 0 (S4U), logon type " + $logon)
    } elseif ($argl -match '-Loop') {
        Write-Output '== accept 2b (fallback): one LONG-LIVED loop process - one brief flash per logon,'
        Write-Output '   not per poll. For zero flash: admin PowerShell -> .\watch.ps1 -Unregister ;'
        Write-Output '   .\watch.ps1 -Register -Headless   (or fix the launcher, see watch-*.log)'
    } else {
        Write-Output ("[FAIL] accept 2b: the task starts a new process per poll (" + $exec + " " + $argl + ")")
        Write-Output '       fix with:  .\watch.ps1 -Unregister  then  .\watch.ps1 -Register'
        $fail = 1
    }
} catch {
    Write-Output ("[FAIL] accept 2b: scheduled task '" + $taskName + "' not found - run .\watch.ps1 -Register")
    $fail = 1
}

#    2c. every watcher poll exit must record a closing line, so a round can
#        never end in silence (a silent exit looks like a hung window). This is
#        the PowerShell twin of the gate check in code/check_all.sh (3c).
$loopChk = '.\code\check_loop_summary.ps1'
if (Test-Path -LiteralPath $loopChk) {
    try {
        $chkOut = (& $loopChk -WatchPath '.\watch.ps1' 2>&1 | Out-String)
        $chkCode = $LASTEXITCODE
        if ($chkOut.Trim()) { Write-Output $chkOut.TrimEnd() }
        if ($chkCode -eq 0) {
            Write-Output '== accept 2c: watcher closing lines verified (every exit path has its summary)'
        } else {
            Write-Output ('[FAIL] accept 2c: watcher closing-line check failed (exit ' + $chkCode + ')')
            $fail = 1
        }
    } catch {
        Write-Output ('[FAIL] accept 2c: check_loop_summary.ps1 threw: ' + $_.Exception.Message)
        $fail = 1
    }
} else {
    Write-Output '[WARN] accept 2c: code\check_loop_summary.ps1 is missing - skipped (upgrade the skill)'
}

# 3. the Office deliverables - proven ON THIS MACHINE, without Office installed.
#    For every file listed in deliverable/OFFICE_HASHES.json:
#      3a sha256 + byte size equal the copy the agent generated, which proves
#         that what arrived through git is that exact file and not a stale one
#      3b the package opens as a zip and every required OOXML part is present
#      3c every .xml / .rels part parses as XML
#      3d every relationship target resolves inside the package (a dangling
#         r:id is exactly what makes Office report unreadable content)
#      3e [Content_Types].xml covers every part
#      3f must_contain markers are found across the xml parts
#      3g pptx only: at least min_slides slides are present
$manRel = 'deliverable/OFFICE_HASHES.json'
if (Test-Path -LiteralPath $manRel) {
    try {
        Add-Type -AssemblyName System.IO.Compression
        Add-Type -AssemblyName System.IO.Compression.FileSystem
    } catch {
        Write-Output ('[WARN] cannot load System.IO.Compression - deliverable package checks skipped: ' + $_.Exception.Message)
    }

    function Read-ZipText {
        param($Archive, [string]$Name)
        $ze = $Archive.GetEntry($Name)
        if (-not $ze) { return $null }
        $sr = New-Object System.IO.StreamReader($ze.Open(), [System.Text.Encoding]::UTF8)
        $t = $sr.ReadToEnd()
        $sr.Dispose()
        return $t
    }

    function Resolve-ZipPath {
        param([string]$Base, [string]$Target)
        $segs = @()
        if ($Base) { $segs += ($Base -split '/') }
        foreach ($s in ($Target -split '/')) {
            if ($s -eq '' -or $s -eq '.') { continue }
            if ($s -eq '..') {
                if ($segs.Count -gt 1) { $segs = $segs[0..($segs.Count - 2)] } else { $segs = @() }
                continue
            }
            $segs += $s
        }
        return ($segs -join '/')
    }

    try {
        $man = Get-Content -LiteralPath $manRel -Raw -Encoding UTF8 | ConvertFrom-Json
        $manFiles = @($man.files)
        Write-Output ('== deliverables: ' + $manFiles.Count + ' Office file(s) declared in ' + $manRel)
        foreach ($f in $manFiles) {
            $rel = [string]$f.path
            $p = $rel -replace '/', '\'
            $kind = [string]$f.kind
            if (-not (Test-Path -LiteralPath $p)) {
                Write-Output ('   FAIL MISSING deliverable ' + $rel)
                $fail = 1
                continue
            }
            # 3a integrity: the file that came through git is the generated one
            $sz = [int64](Get-Item -LiteralPath $p).Length
            if ($sz -ne [int64]$f.bytes) {
                Write-Output ('   FAIL SIZE ' + $rel + ' expected ' + [int64]$f.bytes + ' got ' + $sz)
                $fail = 1
                continue
            }
            $h = (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($h -ne ([string]$f.sha256).ToLowerInvariant()) {
                Write-Output ('   FAIL SHA256 ' + $rel + ' does not match the generated copy')
                Write-Output ('        local  ' + $h)
                Write-Output ('        wanted ' + [string]$f.sha256)
                $fail = 1
                continue
            }
            Write-Output ('   OK   3a sha256 + bytes match: ' + $rel + ' (' + $sz + ' B, ' + $kind + ')')

            $full = (Resolve-Path -LiteralPath $p).Path
            $zip = $null
            try { $zip = [System.IO.Compression.ZipFile]::OpenRead($full) } catch { $zip = $null }
            if (-not $zip) {
                Write-Output ('   FAIL 3b not a readable OOXML zip package: ' + $rel)
                $fail = 1
                continue
            }
            try {
                $names = @{}
                foreach ($ze in $zip.Entries) { $names[$ze.FullName] = $true }
                if ($names.Count -ne $zip.Entries.Count) {
                    Write-Output ('   FAIL 3b duplicate zip entries in ' + $rel)
                    $fail = 1
                }

                # 3b required parts
                $miss = @()
                foreach ($rp in @($f.required_parts)) {
                    if (-not $names.ContainsKey([string]$rp)) { $miss += [string]$rp }
                }
                if ($miss.Count -gt 0) {
                    Write-Output ('   FAIL 3b missing parts in ' + $rel + ' : ' + ($miss -join ', '))
                    $fail = 1
                } else {
                    Write-Output ('   OK   3b all ' + @($f.required_parts).Count + ' required parts present in ' + $rel)
                }

                # 3c every xml part parses; also collect the text for 3f
                $badXml = @()
                $allText = New-Object System.Text.StringBuilder
                foreach ($ze in $zip.Entries) {
                    if ($ze.FullName -notmatch '\.(xml|rels)$') { continue }
                    $t = Read-ZipText $zip $ze.FullName
                    if ($null -eq $t) { $badXml += ($ze.FullName + ' (unreadable)'); continue }
                    try { $null = [xml]$t } catch { $badXml += $ze.FullName }
                    [void]$allText.Append($t)
                }
                if ($badXml.Count -gt 0) {
                    Write-Output ('   FAIL 3c unparseable XML in ' + $rel + ' : ' + ($badXml -join ', '))
                    $fail = 1
                } else {
                    Write-Output ('   OK   3c every XML part parses in ' + $rel + ' (' + $names.Count + ' parts)')
                }

                # 3d relationships resolve
                $dangling = @()
                foreach ($ze in $zip.Entries) {
                    if ($ze.FullName -notmatch '\.rels$') { continue }
                    $segs = $ze.FullName -split '/'
                    $dirSegs = @()
                    if ($segs.Count -gt 2) { $dirSegs = $segs[0..($segs.Count - 3)] }
                    $base = ($dirSegs -join '/')
                    $rx = [xml](Read-ZipText $zip $ze.FullName)
                    foreach ($r in @($rx.Relationships.Relationship)) {
                        $tgt = [string]$r.Target
                        if (-not $tgt -or $tgt.StartsWith('http')) { continue }
                        $resolved = Resolve-ZipPath $base $tgt
                        if (-not $names.ContainsKey($resolved)) {
                            $dangling += ($ze.FullName + ' -> ' + $tgt)
                        }
                    }
                }
                if ($dangling.Count -gt 0) {
                    Write-Output ('   FAIL 3d dangling relationships in ' + $rel + ' : ' + ($dangling -join '; '))
                    $fail = 1
                } else {
                    Write-Output ('   OK   3d every relationship target resolves in ' + $rel)
                }

                # 3e content types cover every part
                $ctx = [xml](Read-ZipText $zip '[Content_Types].xml')
                $defs = @()
                foreach ($d in @($ctx.Types.Default)) { $defs += ([string]$d.Extension).ToLowerInvariant() }
                $ovrs = @()
                foreach ($o in @($ctx.Types.Override)) { $ovrs += [string]$o.PartName }
                $noCt = @()
                foreach ($ze in $zip.Entries) {
                    if ($ze.FullName -eq '[Content_Types].xml') { continue }
                    $ext = ''
                    if ($ze.FullName.Contains('.')) { $ext = ($ze.FullName.Split('.')[-1]).ToLowerInvariant() }
                    if (($ovrs -notcontains ('/' + $ze.FullName)) -and ($defs -notcontains $ext)) {
                        $noCt += $ze.FullName
                    }
                }
                if ($noCt.Count -gt 0) {
                    Write-Output ('   FAIL 3e parts without a content type in ' + $rel + ' : ' + ($noCt -join ', '))
                    $fail = 1
                } else {
                    Write-Output ('   OK   3e content types cover every part of ' + $rel)
                }

                # 3f text markers (searched across all xml parts of the package)
                $body = $allText.ToString()
                $noMark = @()
                foreach ($m in @($f.must_contain)) {
                    if (-not $body.Contains([string]$m)) { $noMark += [string]$m }
                }
                if ($noMark.Count -gt 0) {
                    Write-Output ('   FAIL 3f markers not found in ' + $rel + ' : ' + ($noMark -join ', '))
                    $fail = 1
                } else {
                    Write-Output ('   OK   3f all ' + @($f.must_contain).Count + ' text markers present in ' + $rel)
                }

                # 3g slide count for decks
                if ($f.min_slides) {
                    $nSlides = @($zip.Entries | Where-Object { $_.FullName -match '^ppt/slides/slide[0-9]+\.xml$' }).Count
                    if ($nSlides -lt [int]$f.min_slides) {
                        Write-Output ('   FAIL 3g slides in ' + $rel + ' : ' + $nSlides + ' < ' + [int]$f.min_slides)
                        $fail = 1
                    } else {
                        Write-Output ('   OK   3g slides in ' + $rel + ' : ' + $nSlides + ' >= ' + [int]$f.min_slides)
                    }
                }
            } finally {
                $zip.Dispose()
            }
        }
    } catch {
        Write-Output ('[FAIL] deliverable check threw: ' + $_.Exception.Message)
        $fail = 1
    }
} else {
    Write-Output ('== deliverables: (no ' + $manRel + ' - package checks skipped)')
}

#    3h. application-level open test, auto-detected and time-boxed.
#        The registry is probed for a registered COM server (MS Word / PowerPoint,
#        or WPS Writer / Presentation). Nothing is launched when no suite is
#        installed, so an Office-less or WPS-only machine gets SKIP instead of a
#        false FAIL. The launch runs in a job with a hard timeout, so a hung COM
#        server can never burn the round (check_timeout_min). Force off:
#            setx GIT_SYNC_OFFICE_COM 0
$comTargets = @()
try {
    if (Test-Path -LiteralPath $manRel) {
        $mh = Get-Content -LiteralPath $manRel -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($mh.files) {
            foreach ($mf in @($mh.files)) {
                $p = [string]$mf.path
                if (-not $p) { continue }
                $k = [string]$mf.kind
                if (-not $k) { $k = [System.IO.Path]::GetExtension($p).TrimStart('.') }
                if ($k -eq 'docx' -or $k -eq 'doc') {
                    $comTargets += , @($p.Replace('/', '\'), @('Word.Application', 'KWPS.Application'), 'word')
                } elseif ($k -eq 'pptx' -or $k -eq 'ppt') {
                    $comTargets += , @($p.Replace('/', '\'), @('PowerPoint.Application', 'KWPP.Application'), 'deck')
                }
            }
        }
    }
} catch {
    Write-Output ('   WARN 3h could not read ' + $manRel + ' (' + $_.Exception.Message + ') - open test skipped')
}
if ($comTargets.Count -eq 0) {
    Write-Output ('   SKIP 3h no Office deliverable declared in ' + $manRel + ' - nothing to open')
}
foreach ($ct in $comTargets) {
    $target = [string]$ct[0]
    $kind = [string]$ct[2]
    if (-not (Test-Path -LiteralPath $target)) { continue }
    if ([string]$env:GIT_SYNC_OFFICE_COM -eq '0') {
        Write-Output ('   SKIP 3h ' + $kind + ' open test disabled by GIT_SYNC_OFFICE_COM')
        continue
    }
    $progId = ''
    foreach ($cand in @($ct[1])) {
        if (Test-Path -LiteralPath ('Registry::HKEY_CLASSES_ROOT\' + [string]$cand)) {
            $progId = [string]$cand
            break
        }
    }
    if (-not $progId) {
        Write-Output ('   SKIP 3h no registered COM server for ' + $kind + ' (Word/WPS) - the structural checks above stand')
        continue
    }
    $abs = (Resolve-Path -LiteralPath $target).Path
    $job = $null
    try {
        # $PID is a PowerShell automatic variable, hence $srv for the prog id
        $job = Start-Job -ArgumentList $progId, $abs, $kind -ScriptBlock {
            param($srv, $path, $k)
            $app = New-Object -ComObject $srv
            try {
                if ($k -eq 'word') {
                    $doc = $app.Documents.Open($path, $false, $true)
                    $name = [string]$doc.Name
                    $doc.Close($false)
                    return ('opened read-only, name=' + $name)
                }
                $pres = $app.Presentations.Open($path, $true, $false, $false)
                $n = [int]$pres.Slides.Count
                $pres.Close()
                return ('opened read-only, slides=' + $n)
            } finally {
                try { $app.Quit() } catch { }
            }
        }
        $done = Wait-Job $job -Timeout 120
        if (-not $done) {
            Write-Output ('   WARN 3h ' + $progId + ' did not answer in 120s - counted as SKIP, not as a failure')
            Stop-Job $job -ErrorAction SilentlyContinue
        } elseif ($job.State -eq 'Completed') {
            $msg = ((Receive-Job $job | Out-String) -replace '\s+$', '')
            Write-Output ('   OK   3h ' + $progId + ' ' + $msg + ' : ' + $target)
        } else {
            $err = ((Receive-Job $job 2>&1 | Out-String) -replace '\s+$', '')
            Write-Output ('   FAIL 3h ' + $progId + ' refused to open ' + $target)
            Write-Output ('        ' + $err)
            $fail = 1
        }
    } catch {
        Write-Output ('   WARN 3h open test could not run (' + $_.Exception.Message + ') - counted as SKIP')
    } finally {
        if ($job) { Remove-Job $job -Force -ErrorAction SilentlyContinue }
    }
}

# 4. repo tasks - scripts in code\tasks\ that run ON THIS MACHINE when their
#    round comes up. code\tasks\manifest.json maps round numbers to task
#    scripts; only the CURRENT round's tasks run (the handshake file carries
#    the round number). Each task runs as its own powershell.exe child so a
#    crashing task cannot take this check down with it; the task's stdout
#    lands in this round's receipt and a non-zero task exit fails the round.
#    Task scripts follow the same rules as this file: ASCII-only, Write-Output.
$taskRoot = '.\code\tasks'
$taskManifest = Join-Path $taskRoot 'manifest.json'
if (Test-Path -LiteralPath $taskManifest) {
    $curRound = -1
    try {
        $hsTask = Get-Content -LiteralPath '.\results\status\handshake.json' -Raw -Encoding UTF8 | ConvertFrom-Json
        $curRound = [int]$hsTask.round
    } catch { $curRound = -1 }
    try {
        $tman = Get-Content -LiteralPath $taskManifest -Raw -Encoding UTF8 | ConvertFrom-Json
        $ranAny = $false
        foreach ($rProp in @($tman.rounds.PSObject.Properties)) {
            $rNo = [int]$rProp.Name
            if ($curRound -lt 0 -or $rNo -ne $curRound) { continue }
            foreach ($tName in @($rProp.Value)) {
                $ranAny = $true
                $tPath = Join-Path $taskRoot ([string]$tName)
                Write-Output ''
                Write-Output ('== task r' + $rNo + ': ' + [string]$tName)
                if (-not (Test-Path -LiteralPath $tPath)) {
                    Write-Output ('   [FAIL] task script missing: ' + $tPath)
                    $fail = 1
                    continue
                }
                $tAbs = (Resolve-Path -LiteralPath $tPath).Path
                $psExe = Join-Path $PSHOME 'powershell.exe'
                $t0 = Get-Date
                $tCode = 1
                try {
                    & $psExe -NoProfile -ExecutionPolicy Bypass -File $tAbs
                    $tCode = $LASTEXITCODE
                } catch {
                    Write-Output ('   [FAIL] task launcher threw: ' + $_.Exception.Message)
                    $tCode = 1
                }
                $tSec = [int]((Get-Date) - $t0).TotalSeconds
                if ($tCode -eq 0) {
                    Write-Output ('== task r' + $rNo + ' ' + [string]$tName + ' ok (' + $tSec + 's)')
                } else {
                    Write-Output ('   [FAIL] task exited ' + $tCode + ' (' + $tSec + 's)')
                    $fail = 1
                }
            }
        }
        if (-not $ranAny) { Write-Output ('== tasks: none scheduled for round ' + $curRound) }
    } catch {
        Write-Output ('   [WARN] task manifest unreadable: ' + $_.Exception.Message)
    }
} else {
    Write-Output '== tasks: no manifest at code\tasks\manifest.json - nothing to run'
}


#    2d. v2.7.0 hands-free helpers must be in watch.ps1 (on disk after sync;
#        the running loop still needs a re-register to USE them).
$watchSrc = '.\watch.ps1'
if (Test-Path -LiteralPath $watchSrc) {
    $wt = Get-Content -LiteralPath $watchSrc -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
    if ($wt -and $wt.Contains('function Invoke-AutoPull') -and $wt.Contains('function Invoke-AutoPush')) {
        Write-Output '== accept 2d: hands-free auto_pull/auto_push present in watch.ps1'
    } else {
        Write-Output '[FAIL] accept 2d: watch.ps1 is missing Invoke-AutoPull / Invoke-AutoPush (upgrade the skill)'
        $fail = 1
    }
} else {
    Write-Output '[FAIL] accept 2d: watch.ps1 missing'
    $fail = 1
}

# ------------------------------------------------------------------------
# hands-free success criteria (v2.7.0)
# If results/status/success_criteria.json (or config.success_criteria) exists,
# require every listed file / substring / size / regex. Missing file = skip.
$critRel = 'results/status/success_criteria.json'
if (Test-Path -LiteralPath '.\skills\git-sync\sync.config.json') {
    try {
        $cfgObj = Get-Content -LiteralPath '.\skills\git-sync\sync.config.json' -Encoding UTF8 -Raw | ConvertFrom-Json
        if ($cfgObj.success_criteria) { $critRel = [string]$cfgObj.success_criteria }
    } catch { }
}
$critRel = $critRel -replace '\\', '/'
$critAbs = Join-Path (Get-Location) ($critRel -replace '/', '\')
if (Test-Path -LiteralPath $critAbs) {
    Write-Output ('== success criteria: ' + $critRel)
    try {
        $crit = Get-Content -LiteralPath $critAbs -Encoding UTF8 -Raw | ConvertFrom-Json
        if ($crit.description) { Write-Output ('   ' + $crit.description) }
        foreach ($f in @($crit.require_files)) {
            if (-not $f) { continue }
            $fp = Join-Path (Get-Location) ($f -replace '/', '\')
            if (Test-Path -LiteralPath $fp) {
                $sz = (Get-Item -LiteralPath $fp).Length
                Write-Output ('   OK   exists: ' + $f + ' (' + $sz + ' B)')
            } else {
                Write-Output ('   FAIL MISSING file: ' + $f)
                $fail = 1
            }
        }
        foreach ($f in @($crit.forbid_files)) {
            if (-not $f) { continue }
            $fp = Join-Path (Get-Location) ($f -replace '/', '\')
            if (Test-Path -LiteralPath $fp) {
                Write-Output ('   FAIL FORBIDDEN still present: ' + $f)
                $fail = 1
            } else {
                Write-Output ('   OK   absent: ' + $f)
            }
        }
        if ($crit.require_contains) {
            foreach ($prop in $crit.require_contains.PSObject.Properties) {
                $f = [string]$prop.Name
                $sub = [string]$prop.Value
                $fp = Join-Path (Get-Location) ($f -replace '/', '\')
                if (-not (Test-Path -LiteralPath $fp)) {
                    Write-Output ('   FAIL MISSING for contains: ' + $f)
                    $fail = 1
                    continue
                }
                $txt = Get-Content -LiteralPath $fp -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
                if ($null -eq $txt) { $txt = '' }
                if ($txt.Contains($sub)) {
                    Write-Output ('   OK   contains ' + $f + ' <- ' + $sub)
                } else {
                    Write-Output ('   FAIL DOES NOT contain in ' + $f + ': ' + $sub)
                    $fail = 1
                }
            }
        }
        if ($crit.require_regex) {
            foreach ($prop in $crit.require_regex.PSObject.Properties) {
                $f = [string]$prop.Name
                $rx = [string]$prop.Value
                $fp = Join-Path (Get-Location) ($f -replace '/', '\')
                if (-not (Test-Path -LiteralPath $fp)) {
                    Write-Output ('   FAIL MISSING for regex: ' + $f)
                    $fail = 1
                    continue
                }
                $txt = Get-Content -LiteralPath $fp -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
                if ($null -eq $txt) { $txt = '' }
                if ($txt -match $rx) {
                    Write-Output ('   OK   regex ' + $f)
                } else {
                    Write-Output ('   FAIL regex in ' + $f + ': ' + $rx)
                    $fail = 1
                }
            }
        }
        if ($crit.min_bytes) {
            foreach ($prop in $crit.min_bytes.PSObject.Properties) {
                $f = [string]$prop.Name
                $need = [int64]$prop.Value
                $fp = Join-Path (Get-Location) ($f -replace '/', '\')
                if (-not (Test-Path -LiteralPath $fp)) {
                    Write-Output ('   FAIL MISSING for min_bytes: ' + $f)
                    $fail = 1
                    continue
                }
                $sz = [int64](Get-Item -LiteralPath $fp).Length
                if ($sz -ge $need) {
                    Write-Output ('   OK   size ' + $f + ': ' + $sz + ' >= ' + $need)
                } else {
                    Write-Output ('   FAIL TOO SMALL ' + $f + ': ' + $sz + ' < ' + $need)
                    $fail = 1
                }
            }
        }
        if ($crit.max_bytes) {
            foreach ($prop in $crit.max_bytes.PSObject.Properties) {
                $f = [string]$prop.Name
                $need = [int64]$prop.Value
                $fp = Join-Path (Get-Location) ($f -replace '/', '\')
                if (-not (Test-Path -LiteralPath $fp)) {
                    Write-Output ('   FAIL MISSING for max_bytes: ' + $f)
                    $fail = 1
                    continue
                }
                $sz = [int64](Get-Item -LiteralPath $fp).Length
                if ($sz -le $need) {
                    Write-Output ('   OK   size ' + $f + ': ' + $sz + ' <= ' + $need)
                } else {
                    Write-Output ('   FAIL TOO BIG ' + $f + ': ' + $sz + ' > ' + $need)
                    $fail = 1
                }
            }
        }
    } catch {
        Write-Output ('   FAIL criteria parse: ' + $_.Exception.Message)
        $fail = 1
    }
} else {
    Write-Output ('== success criteria: (none at ' + $critRel + ' - skipped)')
}

if ($fail -eq 0) { Write-Output '== local checks passed' }
exit $fail
