# t2_computer_use_smoke.ps1 - computer-use self-test (safe: touches no user app).
#
# Runs ON THE LOCAL MACHINE inside code\local_check.ps1 section 4.
#
# Round 4 approach - based on the PROVEN round-249 recipe from
# mqgg5630-cyber/git-pull-arena (WCU_UIA_INVOKE_OK=True on this same laptop):
#   the windows-computer-use UIA backend script does its OWN window find by
#   title (health -> activate_window -> find Button 'Write Marker' -> invoke
#   with fallbackClick). Rounds 1-3 failed because this task gated the backend
#   on a raw .NET UIA window pre-check (WS visibility differs) and left the
#   centered TopMost test window sitting around long enough for a human at
#   the keyboard to close/click it (round 3: marker written while the raw UIA
#   never even saw the window - a human raced the script).
# So this version:
#   * never gates the backend on raw UIA - the backend IS the window finder
#   * window is small, corner-docked, not TopMost, labelled "automated test"
#   * up to 2 attempts with fresh titles (one human interference cannot burn
#     the whole round) and a tighter drive cadence (2 s settle, not 3)
#   * pass = backend health+activate+find+invoke AND the marker the click
#     handler writes; a marker that appears BEFORE we issue invoke is tainted
#     (human pre-click) and never counts
#   * raw .NET UIA (with descendant tree dump) is only a diagnostics fallback
#     when the backend script is absent from the E-drive lab path
# Writes results\computer_use\CU_SMOKE.md/.json. No screenshots are taken and
# no title of any other window is recorded (privacy rule of skills/computer-use).
#
# Exit 0 = passed, or SKIP when the watcher runs in session 0 (-Headless/S4U
# has no desktop to automate); exit 1 = the chain failed on a real desktop.
# ASCII-only on purpose (Windows PowerShell 5.1 decodes .ps1 as ANSI/GBK);
# Write-Output only (the watcher captures stdout into the round receipt).

$ErrorActionPreference = 'Continue'
Set-Location (Join-Path $PSScriptRoot '..\..')
$repoRoot = (Get-Location).Path
$outDir = Join-Path $repoRoot 'results\computer_use'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$reportMd = Join-Path $outDir 'CU_SMOKE.md'
$reportJson = Join-Path $outDir 'CU_SMOKE.json'

$report = New-Object System.Collections.Generic.List[string]
function Add-ReportLine([string]$Text) {
    [void]$script:report.Add($Text)
    Write-Output $Text
}

$round = -1
try {
    $hs = Get-Content -LiteralPath (Join-Path $repoRoot 'results\status\handshake.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $round = [int]$hs.round
} catch { $round = -1 }

$sessionId = -1
try { $sessionId = [int](Get-Process -Id $PID).SessionId } catch { $sessionId = -1 }
$interactive = [Environment]::UserInteractive

$screenText = ''
$detail = ''
$backend = 'none'
$verdict = 'False'
$windowFound = $false
$invokeOk = $false
$markerOk = $false
$preclick = $false
$attemptsUsed = 0

$labRoot = 'E:\0mcp-agv-arena-optimized\github'
$labState = @()
foreach ($labName in @('windows-computer-use', 'Windows-MCP', 'pywinauto-mcp')) {
    $labState += ($labName + '=' + (Test-Path -LiteralPath (Join-Path $labRoot $labName)))
}
$wcuBackend = Join-Path $labRoot 'windows-computer-use\plugins\windows-computer-use\scripts\windows-uia.ps1'
$psExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

Add-ReportLine '# rea computer-use smoke (Windows UI Automation)'
Add-ReportLine ''
Add-ReportLine ('CU_ROUND=' + $round)
Add-ReportLine ('time_local=' + (Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz'))
Add-ReportLine ('host=' + $env:COMPUTERNAME)
Add-ReportLine ('CU_SESSION_ID=' + $sessionId + ' interactive=' + $interactive)

if ($sessionId -eq 0) {
    $verdict = 'SKIP'
    $detail = 'session 0 (watcher registered with -Headless / S4U) has no desktop; re-register with .\watch.ps1 -Register for computer use'
    Add-ReportLine ('CU_DETAIL=' + $detail)
} else {
    try { Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
        $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
        $screenText = [string]$bounds.Width + 'x' + [string]$bounds.Height + ' screens=' + [string]([System.Windows.Forms.Screen]::AllScreens.Count)
    } catch { $screenText = 'unknown' }

    $backendPresent = Test-Path -LiteralPath $wcuBackend
    Add-ReportLine ('CU_BACKEND_PRESENT=' + $backendPresent + ' path=' + $wcuBackend)

    # the private test window template (per-attempt title/marker stamped in)
    $appLines = @(
        'param([string]$OutFile, [string]$Title, [string]$Marker, [int]$LifeSec = 50)',
        '$ErrorActionPreference = ''Continue''',
        'Add-Type -AssemblyName System.Windows.Forms',
        '$form = New-Object System.Windows.Forms.Form',
        '$form.Text = $Title',
        '$form.Width = 380',
        '$form.Height = 200',
        '$form.StartPosition = ''Manual''',
        '$form.Left = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea.Right - 400',
        '$form.Top = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea.Bottom - 220',
        '$form.TopMost = $false',
        '$label = New-Object System.Windows.Forms.Label',
        '$label.Left = 20',
        '$label.Top = 16',
        '$label.Width = 340',
        '$label.Text = ''Automated test window - closes by itself.''',
        '$box = New-Object System.Windows.Forms.TextBox',
        '$box.Name = ''MarkerText''',
        '$box.AccessibleName = ''Marker Text''',
        '$box.Left = 20',
        '$box.Top = 44',
        '$box.Width = 320',
        '$btn = New-Object System.Windows.Forms.Button',
        '$btn.Text = ''Write Marker''',
        '$btn.Left = 20',
        '$btn.Top = 80',
        '$btn.Width = 140',
        '$btn.Height = 40',
        '$btn.Add_Click({ [System.IO.File]::WriteAllText($OutFile, $Marker, (New-Object System.Text.UTF8Encoding($false))); $form.Close() })',
        '$timer = New-Object System.Windows.Forms.Timer',
        '$timer.Interval = [Math]::Max(5, $LifeSec) * 1000',
        '$timer.Add_Tick({ $timer.Stop(); $form.Close() })',
        '$timer.Start()',
        '$form.Controls.Add($label)',
        '$form.Controls.Add($box)',
        '$form.Controls.Add($btn)',
        '[void]$form.ShowDialog()'
    )

    function Invoke-Wcu([string]$Action, [object]$Payload, [int]$TimeoutMs = 30000) {
        $json = ($Payload | ConvertTo-Json -Depth 30 -Compress)
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $script:psExe
        $psi.Arguments = '-STA -NoProfile -ExecutionPolicy Bypass -File "' + $script:wcuBackend + '" -Action ' + $Action
        $psi.UseShellExecute = $false
        $psi.RedirectStandardInput = $true
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
        $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8
        $p = [System.Diagnostics.Process]::Start($psi)
        $p.StandardInput.Write($json)
        $p.StandardInput.Close()
        if (-not $p.WaitForExit($TimeoutMs)) { try { $p.Kill() } catch { }; return @{ ok = $false; error = 'TIMEOUT' } }
        $out = $p.StandardOutput.ReadToEnd().Trim()
        try { return ($out | ConvertFrom-Json) } catch { return @{ ok = $false; raw = $out; parseError = $_.Exception.Message } }
    }

    for ($attempt = 1; $attempt -le 2; $attempt++) {
        if ($verdict -eq 'True') { break }
        $attemptsUsed = $attempt
        $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
        $title = 'REA UIA self test ' + $stamp + ' (do not touch)'
        $marker = 'REA_CU_' + $stamp + '_' + (Get-Random -Minimum 1000 -Maximum 9999)
        $workDir = Join-Path ([System.IO.Path]::GetTempPath()) ('rea-cu-' + $stamp + '-a' + $attempt)
        New-Item -ItemType Directory -Force -Path $workDir | Out-Null
        $appScript = Join-Path $workDir 'cu_test_window.ps1'
        $markerFile = Join-Path $workDir 'marker.txt'
        Set-Content -LiteralPath $appScript -Value $appLines -Encoding ASCII

        $proc = $null
        try {
            $proc = Start-Process -FilePath $psExe -ArgumentList @('-STA','-NoProfile','-ExecutionPolicy','Bypass','-File',$appScript,'-OutFile',$markerFile,'-Title',$title,'-Marker',$marker,'-LifeSec','50') -PassThru
        } catch {
            $detail = 'could not start the test window: ' + $_.Exception.Message
            continue
        }
        Start-Sleep -Seconds 2
        # a marker that exists BEFORE we asked for a click means a human beat us
        if (Test-Path -LiteralPath $markerFile) { $preclick = $true }

        if ($backendPresent) {
            $backend = 'windows-computer-use-uia'
            $health = Invoke-Wcu 'health' ([pscustomobject]@{})
            $healthOk = [bool]$health.ok

            $actOk = $false
            $findOk = $false
            $btnId = ''
            $invokeOk = $false
            if ($healthOk) {
                $act = Invoke-Wcu 'activate_window' ([pscustomobject]@{ windowTitle = $title })
                $actOk = [bool]$act.ok
                # find with its own short retry ladder: the backend is the window finder
                $findDeadline = (Get-Date).AddSeconds(15)
                while ((-not $findOk) -and ((Get-Date) -lt $findDeadline) -and (-not $proc.HasExited)) {
                    $find = Invoke-Wcu 'find' ([pscustomobject]@{ scope = 'active_window'; windowTitle = $title; activate = $true; query = 'Write Marker'; controlType = 'Button'; maxDepth = 6; maxResults = 5 })
                    try { if ($find.ok -and $find.results.Count -gt 0) { $findOk = $true; $btnId = [string]$find.results[0].id } } catch { }
                    if (-not $findOk) { Start-Sleep -Milliseconds 1200 }
                }
                if ($findOk) {
                    $windowFound = $true
                    $inv = Invoke-Wcu 'invoke' ([pscustomobject]@{ elementId = $btnId; fallbackClick = $true; windowTitle = $title; activate = $true })
                    $invokeOk = [bool]($inv -and $inv.ok)
                }
            }
            Add-ReportLine ('CU_ATTEMPT' + $attempt + ' wcu health=' + $healthOk + ' activate=' + $actOk + ' find=' + $findOk + ' button_id=' + $btnId + ' invoke=' + $invokeOk)

            # the click handler writes the marker, then closes the window
            $waitUntil = (Get-Date).AddSeconds(12)
            while ((-not (Test-Path -LiteralPath $markerFile)) -and ((Get-Date) -lt $waitUntil)) {
                Start-Sleep -Milliseconds 300
            }
            if (Test-Path -LiteralPath $markerFile) {
                $got = [System.IO.File]::ReadAllText($markerFile)
                $thisMarkerOk = ($got -eq $marker)
            } else { $thisMarkerOk = $false }
            Add-ReportLine ('CU_ATTEMPT' + $attempt + ' marker=' + $thisMarkerOk + ($(if ($preclick) { ' (tainted: present before invoke)' } else { '' })))

            if ($healthOk -and $actOk -and $findOk -and $invokeOk -and $thisMarkerOk -and (-not $preclick)) {
                $verdict = 'True'
                $markerOk = $true
            } else {
                if ($preclick) { $detail = 'a human interacted with the test window before the backend invoked (marker pre-existing)' }
                elseif (-not $healthOk) { $detail = 'wcu backend health check failed' }
                elseif (-not $actOk) { $detail = 'wcu could not activate the test window' }
                elseif (-not $findOk) { $detail = 'wcu could not find the Write Marker button' }
                elseif (-not $invokeOk) { $detail = 'wcu invoke returned not-ok' }
                elseif (-not $thisMarkerOk) { $detail = 'invoke reported ok but the marker was not written correctly' }
            }
        } else {
            # raw .NET UIA fallback (diagnostics only branch; backend absent)
            $backend = 'raw-dotnet-uia'
            try {
                Add-Type -AssemblyName UIAutomationClient -ErrorAction Stop
                Add-Type -AssemblyName UIAutomationTypes -ErrorAction Stop
                $uiaRoot = [System.Windows.Automation.AutomationElement]::RootElement
                $pidCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, [int]$proc.Id)
                $nameCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, $title)
                $winCond = [System.Windows.Automation.AndCondition]::new([System.Windows.Automation.Condition[]]@($pidCond, $nameCond))
                $win = $null
                $deadline = (Get-Date).AddSeconds(15)
                while (($null -eq $win) -and ((Get-Date) -lt $deadline) -and (-not $proc.HasExited)) {
                    try { $win = $uiaRoot.FindFirst([System.Windows.Automation.TreeScope]::Children, $winCond) } catch { $win = $null }
                    if ($null -eq $win) { Start-Sleep -Milliseconds 500 }
                }
                $windowFound = ($null -ne $win)
                if ($windowFound) {
                    $btnCond2 = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Button)
                    $button = $win.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $btnCond2)
                    if ($null -ne $button) {
                        $button.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
                        $invokeOk = $true
                    } else {
                        $allC = [System.Windows.Automation.Condition]::TrueCondition
                        $desc = $win.FindAll([System.Windows.Automation.TreeScope]::Descendants, $allC)
                        Add-ReportLine ('CU_TREE descendants=' + $desc.Count)
                        $shown = 0
                        foreach ($el in $desc) {
                            if ($shown -ge 12) { break }
                            $ct = ''; $nm = ''
                            try { $ct = [string]$el.Current.ControlType.ProgrammaticName } catch { }
                            try { $nm = [string]$el.Current.Name } catch { }
                            if ($nm.Length -gt 32) { $nm = $nm.Substring(0, 32) }
                            Add-ReportLine ('  tree| ' + $ct + ' | ' + $nm)
                            $shown += 1
                        }
                        $detail = 'button not found via raw UIA (tree dumped); backend missing so no fallback'
                    }
                } else { $detail = 'test window not visible to raw UIA and the wcu backend is missing' }
                if ($invokeOk) {
                    $waitUntil = (Get-Date).AddSeconds(12)
                    while ((-not (Test-Path -LiteralPath $markerFile)) -and ((Get-Date) -lt $waitUntil)) { Start-Sleep -Milliseconds 300 }
                    if ((Test-Path -LiteralPath $markerFile) -and (([System.IO.File]::ReadAllText($markerFile)) -eq $marker) -and (-not $preclick)) {
                        $verdict = 'True'
                        $markerOk = $true
                    }
                }
            } catch { $detail = 'raw UIA fallback threw: ' + $_.Exception.Message }
        }
        try { if ($proc -and -not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } } catch { }
        try { Remove-Item -LiteralPath $workDir -Recurse -Force -ErrorAction SilentlyContinue } catch { }
    }
    Add-ReportLine ('CU_BACKEND=' + $backend)
    Add-ReportLine ('CU_WINDOW_FOUND=' + $windowFound)
    Add-ReportLine ('CU_UIA_INVOKE_OK=' + $invokeOk)
    Add-ReportLine ('CU_MARKER_OK=' + $markerOk)
    Add-ReportLine ('CU_PRECLICK=' + $preclick)
    Add-ReportLine ('CU_ATTEMPTS=' + $attemptsUsed)
    if ($detail) { Add-ReportLine ('CU_DETAIL=' + $detail) }
}

Add-ReportLine ('screen=' + $screenText)
Add-ReportLine ('lab_backends=' + ($labState -join ' '))
Add-ReportLine ('COMPUTER_USE_SMOKE_OK=' + $verdict)

try {
    Set-Content -LiteralPath $reportMd -Value $report -Encoding UTF8
    $obj = [ordered]@{
        round = $round
        ok = $verdict
        backend = $backend
        session_id = $sessionId
        interactive = $interactive
        window_found = $windowFound
        uia_invoke_ok = $invokeOk
        marker_ok = $markerOk
        preclick = $preclick
        attempts = $attemptsUsed
        screen = $screenText
        lab_backends = ($labState -join ' ')
        detail = $detail
    }
    Set-Content -LiteralPath $reportJson -Value ($obj | ConvertTo-Json -Depth 4) -Encoding UTF8
    Write-Output ('== computer-use report: results/computer_use/CU_SMOKE.md (ok=' + $verdict + ' backend=' + $backend + ')')
} catch {
    Write-Output ('[FAIL] could not write the computer-use report: ' + $_.Exception.Message)
    exit 1
}

if ($verdict -eq 'False') {
    Write-Output '[FAIL] computer-use smoke: the backend find/invoke/marker chain did not complete - see CU_DETAIL'
    exit 1
}
exit 0
