# t2_computer_use_smoke.ps1 - computer-use self-test (safe: touches no user app).
#
# Runs ON THE LOCAL MACHINE inside code\local_check.ps1 section 4.
#
# Round 5 approach - based on the PROVEN round-249 recipe from
# mqgg5630-cyber/git-pull-arena (WCU_UIA_INVOKE_OK=True on this same laptop),
# plus three root causes found by reading the backend source
# (cgissing/windows-computer-use -> plugins/.../scripts/windows-uia.ps1):
#   1. round 4 passed the window title/marker through Start-Process
#      -ArgumentList (string ARRAY space-joined without quoting), so the
#      multi-word title shattered on the command line and the backend's
#      substring title match could never hit. Now the title and marker are
#      BAKED INTO the generated app script - zero command-line quoting surface.
#   2. the backend's find (windowTitle + activate) resolves and foregrounds
#      the target window itself, so a separate activate_window is not needed;
#      the find ladder retries for ~22 s to outlast slow WinForms cold starts
#      under the scheduler (round 4 allowed one shot at t+2s).
#   3. a human (or a local agent) keeps clicking the test window before the
#      backend does and the free-form marker arrived "for free". The button is
#      now armed only when the text box holds the per-attempt challenge marker
#      (set via the backend's set_value action) - humans are welcome to click,
#      only a backend-carried marker writes the file; and any marker that
#      exists before we invoke is discarded as tainted.
# Pass = backend health + find('Write Marker' Button) + set_value(challenge)
#        + invoke(fallbackClick) + marker file equals the challenge.
# Raw .NET UIA (with a descendant tree dump) remains only as diagnostics when
# the backend script is absent from the E-drive lab path.
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
function ConvertTo-PsLiteral([string]$Text) {
    return "'" + ($Text -replace "'", "''") + "'"
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
$typeOk = $false
$invokeOk = $false
$markerOk = $false
$tainted = $false
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

    # the private test window, written fresh per attempt with the title and
    # the challenge marker BAKED IN (no command-line arguments at all).
    # The click handler ALWAYS writes (marker + "|" + current box text), so
    # the file content is itself the diagnostic: an outside click yields
    # "marker|<whatever the box holds>" and never counts, while the backend's
    # challenge-armed click must yield exactly "marker|marker".
    function New-TestAppScript([string]$Path, [string]$Title, [string]$Marker, [string]$OutFile, [string]$LogFile) {
        $lines = @(
            '$ErrorActionPreference = ''Continue''',
            'Add-Type -AssemblyName System.Windows.Forms',
            ('$logFile = ' + (ConvertTo-PsLiteral $LogFile)),
            'function AppLog([string]$m) { try { [System.IO.File]::AppendAllText($logFile, ($m + [Environment]::NewLine), (New-Object System.Text.UTF8Encoding($false))) } catch { } }',
            'AppLog ''start''',
            '$form = New-Object System.Windows.Forms.Form',
            ('$form.Text = ' + (ConvertTo-PsLiteral $Title)),
            '$form.Width = 380',
            '$form.Height = 200',
            '$form.StartPosition = ''Manual''',
            '$form.Left = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea.Right - 400',
            '$form.Top = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea.Bottom - 220',
            '$form.TopMost = $false',
            '$form.ShowInTaskbar = $false',
            '$form.Add_Shown({ AppLog ''shown'' })',
            '$label = New-Object System.Windows.Forms.Label',
            '$label.Left = 20',
            '$label.Top = 16',
            '$label.Width = 340',
            '$label.Text = ''Automated test window - self-closing.''',
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
            ('$marker = ' + (ConvertTo-PsLiteral $Marker)),
            ('$outFile = ' + (ConvertTo-PsLiteral $OutFile)),
            '$btn.Add_Click({',
            '    AppLog (''click box_len='' + $box.Text.Length)',
            '    try {',
            '        [System.IO.File]::WriteAllText($outFile, ($marker + ''|'' + $box.Text), (New-Object System.Text.UTF8Encoding($false)))',
            '        AppLog ''wrote''',
            '    } catch {',
            '        AppLog (''write_error '' + $_.Exception.Message)',
            '    }',
            '    $form.Close()',
            '})',
            '$timer = New-Object System.Windows.Forms.Timer',
            '$timer.Interval = 50000',
            '$timer.Add_Tick({ $timer.Stop(); AppLog ''timeout''; $form.Close() })',
            '$timer.Start()',
            '$form.Controls.Add($label)',
            '$form.Controls.Add($box)',
            '$form.Controls.Add($btn)',
            '[void]$form.ShowDialog()',
            'AppLog ''exit'''
        )
        Set-Content -LiteralPath $Path -Value $lines -Encoding ASCII
    }

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

    $healthOk = $false
    if ($backendPresent) {
        $backend = 'windows-computer-use-uia'
        $health = Invoke-Wcu 'health' ([pscustomobject]@{})
        $healthOk = [bool]$health.ok
        Add-ReportLine ('CU_HEALTH=' + $healthOk)
        if (-not $healthOk) { $detail = 'wcu backend health check failed' }
    }

    $attemptsCap = 1
    if ($backendPresent) { $attemptsCap = 2 }
    for ($attempt = 1; $attempt -le $attemptsCap; $attempt++) {
        if ($verdict -eq 'True') { break }
        if ($backendPresent -and (-not $healthOk)) { break }
        $attemptsUsed = $attempt
        $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
        $title = 'REA UIA self test ' + $stamp
        $marker = 'REACU' + ($stamp -replace '[^0-9]', '') + (Get-Random -Minimum 1000 -Maximum 9999)
        $workDir = Join-Path ([System.IO.Path]::GetTempPath()) ('rea-cu-' + $stamp + '-a' + $attempt)
        New-Item -ItemType Directory -Force -Path $workDir | Out-Null
        $appScript = Join-Path $workDir 'cu_test_window.ps1'
        $markerFile = Join-Path $workDir 'marker.txt'
        $logFile = Join-Path $workDir 'app.log'
        New-TestAppScript -Path $appScript -Title $title -Marker $marker -OutFile $markerFile -LogFile $logFile

        $proc = $null
        try {
            $proc = Start-Process -FilePath $psExe -ArgumentList ('-STA -NoProfile -ExecutionPolicy Bypass -File "' + $appScript + '"') -PassThru
        } catch {
            $detail = 'could not start the test window: ' + $_.Exception.Message
            continue
        }

        if ($backendPresent) {
            # find ladder for the button: the backend resolves + foregrounds
            # the window itself; retry to outlast slow window creation
            $findOk = $false
            $btnId = ''
            $findDeadline = (Get-Date).AddSeconds(22)
            while ((-not $findOk) -and ((Get-Date) -lt $findDeadline) -and (-not $proc.HasExited)) {
                $find = Invoke-Wcu 'find' ([pscustomobject]@{ scope = 'active_window'; windowTitle = $title; activate = $true; query = 'Write Marker'; controlType = 'Button'; maxDepth = 6; maxResults = 5 })
                try { if ($find.ok -and $find.results.Count -gt 0) { $findOk = $true; $btnId = [string]$find.results[0].id } } catch { }
                if (-not $findOk) { Start-Sleep -Milliseconds 1200 }
            }
            $windowFound = $findOk
            $thisTainted = $false
            if (Test-Path -LiteralPath $markerFile) { $thisTainted = $true; $tainted = $true }
            if (-not $findOk -and $proc.HasExited -and -not $thisTainted) {
                $detail = 'test window closed before the backend found the button (human interference?)'
            }

            # arm the button by typing the challenge into the box via set_value
            # (ValuePattern only - no keyboard fallback), then READ IT BACK
            # through the backend so the receipt shows exactly what the box holds
            $thisTypeOk = $false
            $readbackOk = $false
            $svMethod = ''
            $editId = ''
            if ($findOk) {
                $findEdit = Invoke-Wcu 'find' ([pscustomobject]@{ scope = 'active_window'; windowTitle = $title; activate = $true; query = ''; controlType = 'Edit'; maxDepth = 6; maxResults = 5 })
                try { if ($findEdit.ok -and $findEdit.results.Count -gt 0) { $editId = [string]$findEdit.results[0].id } } catch { }
                if ($editId) {
                    $sv = Invoke-Wcu 'set_value' ([pscustomobject]@{ elementId = $editId; value = $marker; fallbackType = $false; windowTitle = $title; activate = $true })
                    $thisTypeOk = [bool]$sv.ok
                    try { $svMethod = [string]$sv.method } catch { }
                    if (-not $thisTypeOk) { $detail = 'set_value(challenge) returned not-ok' }
                    # read-back: the same find carries the current value
                    $rb = Invoke-Wcu 'find' ([pscustomobject]@{ scope = 'active_window'; windowTitle = $title; activate = $true; query = ''; controlType = 'Edit'; maxDepth = 6; maxResults = 5 })
                    $rbValue = ''
                    try { if ($rb.ok -and $rb.results.Count -gt 0) { $rbValue = [string]$rb.results[0].value } } catch { }
                    $readbackOk = ($rbValue -eq $marker)
                    Add-ReportLine ('CU_ATTEMPT' + $attempt + ' readback ok=' + $readbackOk + ' box_len=' + $rbValue.Length + ' marker_len=' + $marker.Length)
                } else {
                    $detail = 'no Edit control found via the backend'
                }
            } elseif (-not $detail) { $detail = 'backend could not find the Write Marker button in the test window' }
            $typeOk = $thisTypeOk -and $readbackOk

            # invoke only when armed; escalate to a real mouse click when the
            # InvokePattern is a no-op on this app; expect exactly "marker|marker"
            $thisInvokeOk = $false
            $thisMarkerOk = $false
            $invMethod = ''
            $markerContent = ''
            if ($findOk -and $typeOk -and (-not (Test-Path -LiteralPath $markerFile))) {
                $inv = Invoke-Wcu 'invoke' ([pscustomobject]@{ elementId = $btnId; fallbackClick = $false; windowTitle = $title; activate = $true })
                $thisInvokeOk = [bool]($inv -and $inv.ok)
                try { $invMethod = [string]$inv.method } catch { }
                if ($thisInvokeOk) {
                    $waitUntil = (Get-Date).AddSeconds(5)
                    while ((-not (Test-Path -LiteralPath $markerFile)) -and ((Get-Date) -lt $waitUntil)) {
                        Start-Sleep -Milliseconds 250
                    }
                } else { $invMethod = 'not-ok' }
                if (-not (Test-Path -LiteralPath $markerFile)) {
                    # InvokePattern was a no-op on this app -> REAL mouse click
                    $clk = Invoke-Wcu 'click' ([pscustomobject]@{ elementId = $btnId; windowTitle = $title; activate = $true })
                    $clkOk = [bool]($clk -and $clk.ok)
                    $invMethod = $invMethod + '+click(' + $clkOk + ')'
                    $waitUntil = (Get-Date).AddSeconds(8)
                    while ((-not (Test-Path -LiteralPath $markerFile)) -and ((Get-Date) -lt $waitUntil)) {
                        Start-Sleep -Milliseconds 250
                    }
                }
                if (Test-Path -LiteralPath $markerFile) {
                    $markerContent = [System.IO.File]::ReadAllText($markerFile)
                    $thisMarkerOk = ($markerContent -eq ($marker + '|' + $marker))
                    if (-not $thisMarkerOk) {
                        $boxSide = ''
                        if ($markerContent.StartsWith($marker + '|')) { $boxSide = $markerContent.Substring($marker.Length + 1) }
                        Add-ReportLine ('CU_ATTEMPT' + $attempt + ' marker_content_box_side_len=' + $boxSide.Length + ' equals_marker=' + ($boxSide -eq $marker))
                        if (-not $detail) { $detail = 'click happened but the box did not hold the challenge (see box_side)' }
                    }
                } elseif (-not $detail) { $detail = 'neither InvokePattern nor a real mouse click produced the marker' }
            } elseif ($findOk -and $typeOk -and (Test-Path -LiteralPath $markerFile)) {
                $detail = 'marker existed before the backend invoked (tainted by an outside click)'
            }
            if ($thisInvokeOk) { $invokeOk = $true }
            # the app's own lifecycle log is the ground truth about the handler
            if (Test-Path -LiteralPath $logFile) {
                foreach ($ll in @(Get-Content -LiteralPath $logFile -Encoding UTF8 -ErrorAction SilentlyContinue)) {
                    if ($ll.Trim()) { Add-ReportLine ('  app_log| ' + $ll.Trim()) }
                }
            }
            Add-ReportLine ('CU_ATTEMPT' + $attempt + ' find=' + $findOk + ' button_id=' + $btnId + ' edit_id=' + $editId + ' set_value=' + $thisTypeOk + '(' + $svMethod + ') invoke=' + $thisInvokeOk + '(' + $invMethod + ') marker=' + $thisMarkerOk + ' tainted=' + $thisTainted)
            if ($findOk -and $typeOk -and $thisInvokeOk -and $thisMarkerOk -and (-not $thisTainted)) {
                $verdict = 'True'
                $markerOk = $true
            }
        } else {
            # raw .NET UIA fallback (diagnostics only; backend absent)
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
                    $editC = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Edit)
                    $edit = $win.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $editC)
                    if ($null -ne $edit) {
                        $edit.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).SetValue($marker)
                        $typeOk = $true
                    }
                    $btnC = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Button)
                    $button = $win.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $btnC)
                    if ($null -ne $button -and $typeOk) {
                        $button.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
                        $invokeOk = $true
                    } elseif ($null -eq $button) {
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
                        $detail = 'button not found via raw UIA (tree dumped); the wcu backend is missing'
                    }
                } else { $detail = 'test window not visible to raw UIA and the wcu backend is missing' }
                if ($invokeOk) {
                    $waitUntil = (Get-Date).AddSeconds(12)
                    while ((-not (Test-Path -LiteralPath $markerFile)) -and ((Get-Date) -lt $waitUntil)) { Start-Sleep -Milliseconds 300 }
                    if ((Test-Path -LiteralPath $markerFile) -and (([System.IO.File]::ReadAllText($markerFile)) -eq ($marker + '|' + $marker))) {
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
    Add-ReportLine ('CU_UIA_TYPE_OK=' + $typeOk)
    Add-ReportLine ('CU_UIA_INVOKE_OK=' + $invokeOk)
    Add-ReportLine ('CU_MARKER_OK=' + $markerOk)
    Add-ReportLine ('CU_TAINTED_MARKER=' + $tainted)
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
        uia_type_ok = $typeOk
        uia_invoke_ok = $invokeOk
        marker_ok = $markerOk
        tainted_marker = $tainted
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
    Write-Output '[FAIL] computer-use smoke: the find/set_value/invoke/marker chain did not complete - see CU_DETAIL'
    exit 1
}
exit 0
