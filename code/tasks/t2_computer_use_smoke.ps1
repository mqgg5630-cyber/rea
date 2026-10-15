# t2_computer_use_smoke.ps1 - round 1 computer-use self-test (safe: touches no user app).
#
# Runs ON THE LOCAL MACHINE inside code\local_check.ps1 section 4.
# 1. starts a tiny private WinForms test window in a child powershell
#    (-STA, CreateNoWindow: no console flash; it closes itself after 60 s)
# 2. drives that window ONLY through Windows UI Automation (UIAutomationClient,
#    built into Windows PowerShell 5.1 - nothing is downloaded or installed):
#      find window -> find the text box -> ValuePattern.SetValue  ("type")
#                  -> find the button   -> InvokePattern.Invoke   ("click")
# 3. the button writes the typed text to a marker file -> compare
# Writes results\computer_use\CU_SMOKE.md/.json. No screenshots are taken and no
# title of any other window is recorded (privacy rule of skills/computer-use).
#
# Exit 0 = passed, or SKIP when the watcher runs in session 0 (-Headless/S4U has
# no desktop to automate); exit 1 = the UIA chain failed on a real desktop.
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
} catch {
    $round = -1
}

$sessionId = -1
try { $sessionId = [int](Get-Process -Id $PID).SessionId } catch { $sessionId = -1 }
$interactive = [Environment]::UserInteractive

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$title = 'Arena REA UIA Smoke ' + $stamp
$typed = 'REA_CU_' + $stamp + '_' + (Get-Random -Minimum 1000 -Maximum 9999)
$workDir = Join-Path ([System.IO.Path]::GetTempPath()) ('rea-cu-' + $stamp)
New-Item -ItemType Directory -Force -Path $workDir | Out-Null
$appScript = Join-Path $workDir 'cu_test_window.ps1'
$markerFile = Join-Path $workDir 'marker.txt'

$windowFound = $false
$typeOk = $false
$invokeOk = $false
$markerOk = $false
$screenText = ''
$detail = ''
$verdict = 'False'

# lab backends documented in skills/computer-use (presence only, nothing is run)
$labRoot = 'E:\0mcp-agv-arena-optimized\github'
$labState = @()
foreach ($labName in @('windows-computer-use', 'Windows-MCP', 'pywinauto-mcp')) {
    $labState += ($labName + '=' + (Test-Path -LiteralPath (Join-Path $labRoot $labName)))
}

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
    try {
        Add-Type -AssemblyName UIAutomationClient -ErrorAction Stop
        Add-Type -AssemblyName UIAutomationTypes -ErrorAction Stop
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
        try {
            $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
            $screenText = [string]$bounds.Width + 'x' + [string]$bounds.Height + ' screens=' + [string]([System.Windows.Forms.Screen]::AllScreens.Count)
        } catch {
            $screenText = 'unknown'
        }

        # the private test window (its own STA process, closes itself after 60 s)
        $appLines = @(
            'param([string]$OutFile, [string]$Title, [int]$LifeSec = 60)',
            '$ErrorActionPreference = ''Stop''',
            'Add-Type -AssemblyName System.Windows.Forms',
            '$form = New-Object System.Windows.Forms.Form',
            '$form.Text = $Title',
            '$form.Width = 460',
            '$form.Height = 200',
            '$form.StartPosition = ''CenterScreen''',
            '$form.TopMost = $true',
            '$box = New-Object System.Windows.Forms.TextBox',
            '$box.Name = ''MarkerText''',
            '$box.AccessibleName = ''Marker Text''',
            '$box.Left = 20',
            '$box.Top = 20',
            '$box.Width = 400',
            '$btn = New-Object System.Windows.Forms.Button',
            '$btn.Text = ''Write Marker''',
            '$btn.Left = 20',
            '$btn.Top = 60',
            '$btn.Width = 160',
            '$btn.Height = 40',
            '$btn.Add_Click({ [System.IO.File]::WriteAllText($OutFile, $box.Text, (New-Object System.Text.UTF8Encoding($false))); $form.Close() })',
            '$timer = New-Object System.Windows.Forms.Timer',
            '$timer.Interval = [Math]::Max(5, $LifeSec) * 1000',
            '$timer.Add_Tick({ $timer.Stop(); $form.Close() })',
            '$timer.Start()',
            '$form.Controls.Add($box)',
            '$form.Controls.Add($btn)',
            '[void]$form.ShowDialog()'
        )
        Set-Content -LiteralPath $appScript -Value $appLines -Encoding ASCII

        $psExe = Join-Path $PSHOME 'powershell.exe'
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $psExe
        $psi.Arguments = '-STA -NoProfile -ExecutionPolicy Bypass -File "' + $appScript + '" -OutFile "' + $markerFile + '" -Title "' + $title + '" -LifeSec 60'
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $proc = [System.Diagnostics.Process]::Start($psi)

        $uiaRoot = [System.Windows.Automation.AutomationElement]::RootElement
        $pidCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, [int]$proc.Id)
        $nameCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, $title)
        $winCond = [System.Windows.Automation.AndCondition]::new([System.Windows.Automation.Condition[]]@($pidCond, $nameCond))

        $win = $null
        $deadline = (Get-Date).AddSeconds(30)
        while (($null -eq $win) -and ((Get-Date) -lt $deadline) -and (-not $proc.HasExited)) {
            Start-Sleep -Milliseconds 500
            try { $win = $uiaRoot.FindFirst([System.Windows.Automation.TreeScope]::Children, $winCond) } catch { $win = $null }
        }
        $windowFound = ($null -ne $win)
        Add-ReportLine ('CU_WINDOW_FOUND=' + $windowFound)

        if ($windowFound) {
            # "type": ValuePattern on the text box, then read it back
            $editCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::AutomationIdProperty, 'MarkerText')
            $edit = $win.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $editCond)
            if ($null -ne $edit) {
                $valuePat = $edit.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
                $valuePat.SetValue($typed)
                Start-Sleep -Milliseconds 300
                $typeOk = ([string]$valuePat.Current.Value -eq $typed)
            } else {
                $detail = 'text box not found via UIA'
            }
            Add-ReportLine ('CU_UIA_TYPE_OK=' + $typeOk)

            # "click": InvokePattern on the button
            $typeCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Button)
            $labelCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, 'Write Marker')
            $btnCond = [System.Windows.Automation.AndCondition]::new([System.Windows.Automation.Condition[]]@($typeCond, $labelCond))
            $button = $win.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $btnCond)
            if ($null -ne $button) {
                $invokePat = $button.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
                $invokePat.Invoke()
                $invokeOk = $true
            } elseif (-not $detail) {
                $detail = 'button not found via UIA'
            }
            Add-ReportLine ('CU_UIA_INVOKE_OK=' + $invokeOk)

            # the click handler writes the typed text, then closes the window
            $waitUntil = (Get-Date).AddSeconds(15)
            while ((-not (Test-Path -LiteralPath $markerFile)) -and ((Get-Date) -lt $waitUntil)) {
                Start-Sleep -Milliseconds 300
            }
            if (Test-Path -LiteralPath $markerFile) {
                $got = [System.IO.File]::ReadAllText($markerFile)
                $markerOk = ($got -eq $typed)
                if (-not $markerOk -and -not $detail) { $detail = 'marker text differs from what UIA typed' }
            } elseif (-not $detail) {
                $detail = 'marker file was not written after the invoke'
            }
        } elseif ($proc.HasExited) {
            $detail = 'test window process exited early (exit ' + [string]$proc.ExitCode + ')'
        } else {
            $detail = 'test window not visible to UIA within 30 s (locked screen?)'
        }
        Add-ReportLine ('CU_MARKER_OK=' + $markerOk)

        try { if (-not $proc.WaitForExit(10000)) { $proc.Kill() } } catch { }
    } catch {
        $detail = 'UIA chain threw: ' + $_.Exception.Message
    }
    if ($windowFound -and $typeOk -and $invokeOk -and $markerOk) { $verdict = 'True' }
    if ($detail) { Add-ReportLine ('CU_DETAIL=' + $detail) }
}

Add-ReportLine ('screen=' + $screenText)
Add-ReportLine ('lab_backends=' + ($labState -join ' '))
Add-ReportLine ('COMPUTER_USE_SMOKE_OK=' + $verdict)

try { Remove-Item -LiteralPath $workDir -Recurse -Force -ErrorAction SilentlyContinue } catch { }

try {
    Set-Content -LiteralPath $reportMd -Value $report -Encoding UTF8
    $obj = [ordered]@{
        round = $round
        ok = $verdict
        session_id = $sessionId
        interactive = $interactive
        window_found = $windowFound
        uia_type_ok = $typeOk
        uia_invoke_ok = $invokeOk
        marker_ok = $markerOk
        screen = $screenText
        lab_backends = ($labState -join ' ')
        detail = $detail
    }
    Set-Content -LiteralPath $reportJson -Value ($obj | ConvertTo-Json -Depth 4) -Encoding UTF8
    Write-Output ('== computer-use report: results/computer_use/CU_SMOKE.md (ok=' + $verdict + ')')
} catch {
    Write-Output ('[FAIL] could not write the computer-use report: ' + $_.Exception.Message)
    exit 1
}

if ($verdict -eq 'False') {
    Write-Output '[FAIL] computer-use smoke: the UIA find/type/click chain did not complete - see CU_DETAIL'
    exit 1
}
exit 0
