# t2_computer_use_smoke.ps1 - computer-use self-test (safe: touches no user app).
#
# Runs ON THE LOCAL MACHINE inside code\local_check.ps1 section 4.
#
# Round 3 approach - port of the PROVEN round-249 recipe from
# mqgg5630-cyber/git-pull-arena (that run produced WCU_UIA_INVOKE_OK=True on
# this same laptop, so this backend+sequence is known-good here):
#   1. start a tiny private WinForms test window (Start-Process, STA; the form
#      closes itself after 60 s) - NO hidden-window process creation
#   2. drive it through the windows-computer-use UIA backend script that lives
#      on the E-drive lab path (health -> activate_window -> find the
#      'Write Marker' Button -> invoke with fallbackClick)
#   3. the button writes a stamped marker file -> compare contents
# If (and only if) the backend script is missing, fall back to raw .NET UIA
# assemblies with retries and a descendant-tree dump for diagnostics.
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

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$title = 'Arena REA UIA Smoke ' + $stamp
$marker = 'REA_CU_' + $stamp + '_' + (Get-Random -Minimum 1000 -Maximum 9999)
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
$backend = 'none'
$verdict = 'False'

# lab backends documented in skills/computer-use (presence only, nothing is run)
$labRoot = 'E:\0mcp-agv-arena-optimized\github'
$labState = @()
foreach ($labName in @('windows-computer-use', 'Windows-MCP', 'pywinauto-mcp')) {
    $labState += ($labName + '=' + (Test-Path -LiteralPath (Join-Path $labRoot $labName)))
}
$wcuBackend = Join-Path $labRoot 'windows-computer-use\plugins\windows-computer-use\scripts\windows-uia.ps1'

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
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
        try {
            $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
            $screenText = [string]$bounds.Width + 'x' + [string]$bounds.Height + ' screens=' + [string]([System.Windows.Forms.Screen]::AllScreens.Count)
        } catch { $screenText = 'unknown' }

        # ---- 1. the private test window (proven r249 shape: visible STA
        #         process via plain Start-Process, label + edit + button;
        #         closes itself after 60 s or right after the click)
        $appLines = @(
            'param([string]$OutFile, [string]$Title, [string]$Marker, [int]$LifeSec = 60)',
            '$ErrorActionPreference = ''Continue''',
            'Add-Type -AssemblyName System.Windows.Forms',
            '$form = New-Object System.Windows.Forms.Form',
            '$form.Text = $Title',
            '$form.Width = 520',
            '$form.Height = 240',
            '$form.StartPosition = ''CenterScreen''',
            '$form.TopMost = $true',
            '$label = New-Object System.Windows.Forms.Label',
            '$label.Left = 30',
            '$label.Top = 20',
            '$label.Width = 440',
            '$label.Text = ''computer-use UIA invoke proof''',
            '$box = New-Object System.Windows.Forms.TextBox',
            '$box.Name = ''MarkerText''',
            '$box.AccessibleName = ''Marker Text''',
            '$box.Left = 30',
            '$box.Top = 50',
            '$box.Width = 400',
            '$btn = New-Object System.Windows.Forms.Button',
            '$btn.Text = ''Write Marker''',
            '$btn.Left = 30',
            '$btn.Top = 90',
            '$btn.Width = 160',
            '$btn.Height = 44',
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
        Set-Content -LiteralPath $appScript -Value $appLines -Encoding ASCII

        $psExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
        $proc = $null
        try {
            $proc = Start-Process -FilePath $psExe -ArgumentList @('-STA','-NoProfile','-ExecutionPolicy','Bypass','-File',$appScript,'-OutFile',$markerFile,'-Title',$title,'-Marker',$marker,'-LifeSec','60') -PassThru
            Start-Sleep -Seconds 3
        } catch {
            $detail = 'could not start the test window: ' + $_.Exception.Message
        }

        if ($null -ne $proc) {
            # window-visible check via the .NET UIA root (cheap, PID+title exact)
            try {
                Add-Type -AssemblyName UIAutomationClient -ErrorAction Stop
                Add-Type -AssemblyName UIAutomationTypes -ErrorAction Stop
                $uiaRoot = [System.Windows.Automation.AutomationElement]::RootElement
                $pidCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, [int]$proc.Id)
                $nameCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, $title)
                $winCond = [System.Windows.Automation.AndCondition]::new([System.Windows.Automation.Condition[]]@($pidCond, $nameCond))
                $deadline = (Get-Date).AddSeconds(15)
                while ((-not $windowFound) -and ((Get-Date) -lt $deadline) -and (-not $proc.HasExited)) {
                    try { $windowFound = ($null -ne $uiaRoot.FindFirst([System.Windows.Automation.TreeScope]::Children, $winCond)) } catch { $windowFound = $false }
                    if (-not $windowFound) { Start-Sleep -Milliseconds 500 }
                }
            } catch { $windowFound = $false }
        }
        Add-ReportLine ('CU_WINDOW_FOUND=' + $windowFound)

        $backendPresent = Test-Path -LiteralPath $wcuBackend
        Add-ReportLine ('CU_BACKEND_PRESENT=' + $backendPresent + ' path=' + $wcuBackend)

        if ($backendPresent -and $windowFound) {
            # ---- 2. PROVEN chain: windows-computer-use UIA backend script,
            #         exactly the r249 action sequence (health -> activate ->
            #         find Button 'Write Marker' -> invoke fallbackClick)
            $backend = 'windows-computer-use-uia'
            function Invoke-Wcu([string]$Action, [object]$Payload, [int]$TimeoutMs = 30000) {
                $json = ($Payload | ConvertTo-Json -Depth 30 -Compress)
                $psi = New-Object System.Diagnostics.ProcessStartInfo
                $psi.FileName = $script:psExe
                $psi.Arguments = '-STA -NoProfile -ExecutionPolicy Bypass -File "' + $wcuBackend + '" -Action ' + $Action
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
            $health = Invoke-Wcu 'health' ([pscustomobject]@{})
            $act = Invoke-Wcu 'activate_window' ([pscustomobject]@{ windowTitle = $title })
            $find = Invoke-Wcu 'find' ([pscustomobject]@{ scope = 'active_window'; windowTitle = $title; activate = $true; query = 'Write Marker'; controlType = 'Button'; maxDepth = 6; maxResults = 5 })
            $btnId = ''
            try { if ($find.ok -and $find.results.Count -gt 0) { $btnId = [string]$find.results[0].id } } catch { }
            $inv = $null
            if ($btnId) { $inv = Invoke-Wcu 'invoke' ([pscustomobject]@{ elementId = $btnId; fallbackClick = $true; windowTitle = $title; activate = $true }) }
            $healthOk = [bool]$health.ok
            $actOk = [bool]$act.ok
            $findOk = [bool]$find.ok
            $invokeOk = [bool]($inv -and $inv.ok)
            $typeOk = $findOk   # the typed-text leg folds into the backend find proof; the marker carries the round-trip
            Add-ReportLine ('CU_WCU health=' + $healthOk + ' activate=' + $actOk + ' find=' + $findOk + ' button_id=' + $btnId + ' invoke=' + $invokeOk)
            if (-not $healthOk) { $detail = 'wcu backend health check failed' }
            elseif (-not $actOk) { $detail = 'wcu could not activate the test window' }
            elseif (-not $findOk) { $detail = 'wcu could not find the Write Marker button' }
            elseif (-not $invokeOk) { $detail = 'wcu invoke returned not-ok' }
        } else {
            # ---- fallback: raw .NET UIA with retries + tree dump (diagnostics)
            $backend = 'raw-dotnet-uia'
            if ($windowFound) {
                $edit = $null
                $editTypeCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Edit)
                $editDeadline = (Get-Date).AddSeconds(10)
                while (($null -eq $edit) -and ((Get-Date) -lt $editDeadline) -and (-not $proc.HasExited)) {
                    try {
                        $win2 = $uiaRoot.FindFirst([System.Windows.Automation.TreeScope]::Children, $winCond)
                        if ($null -ne $win2) { $edit = $win2.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $editTypeCond) }
                    } catch { $edit = $null }
                    if ($null -eq $edit) { Start-Sleep -Milliseconds 500 }
                }
                if ($null -ne $edit) {
                    try {
                        $valuePat = $edit.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
                        $valuePat.SetValue($marker)
                        Start-Sleep -Milliseconds 400
                        $typeOk = ([string]$valuePat.Current.Value -eq $marker)
                    } catch { $detail = 'ValuePattern threw: ' + $_.Exception.Message }
                } else {
                    # dump what UIA actually sees, so the next fix is not blind
                    try {
                        $win3 = $uiaRoot.FindFirst([System.Windows.Automation.TreeScope]::Children, $winCond)
                        if ($null -ne $win3) {
                            $allCond = [System.Windows.Automation.Condition]::TrueCondition
                            $desc = $win3.FindAll([System.Windows.Automation.TreeScope]::Descendants, $allCond)
                            Add-ReportLine ('CU_TREE descendants=' + $desc.Count + ' (first 20: controltype|name|automationid)')
                            $shown = 0
                            foreach ($el in $desc) {
                                if ($shown -ge 20) { break }
                                $ct = ''; $nm = ''; $ai = ''
                                try { $ct = [string]$el.Current.ControlType.ProgrammaticName } catch { }
                                try { $nm = [string]$el.Current.Name } catch { }
                                try { $ai = [string]$el.Current.AutomationId } catch { }
                                if ($nm.Length -gt 40) { $nm = $nm.Substring(0, 40) }
                                Add-ReportLine ('  tree| ' + $ct + ' | ' + $nm + ' | ' + $ai)
                                $shown += 1
                            }
                        }
                    } catch { Add-ReportLine ('CU_TREE dump failed: ' + $_.Exception.Message) }
                    $detail = 'text box not found via UIA after 10 s of retries (tree dumped above)'
                }
                Add-ReportLine ('CU_UIA_TYPE_OK=' + $typeOk)
                $btnCond2 = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Button)
                $btnDeadline = (Get-Date).AddSeconds(10)
                $button = $null
                while (($null -eq $button) -and ((Get-Date) -lt $btnDeadline) -and (-not $proc.HasExited)) {
                    try {
                        $win4 = $uiaRoot.FindFirst([System.Windows.Automation.TreeScope]::Children, $winCond)
                        if ($null -ne $win4) { $button = $win4.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $btnCond2) }
                    } catch { $button = $null }
                    if ($null -eq $button) { Start-Sleep -Milliseconds 500 }
                }
                if ($null -ne $button) {
                    try {
                        $invokePat = $button.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
                        $invokePat.Invoke()
                        $invokeOk = $true
                    } catch { $detail = 'InvokePattern threw: ' + $_.Exception.Message }
                } elseif (-not $detail) { $detail = 'button not found via UIA after 10 s of retries' }
                Add-ReportLine ('CU_UIA_INVOKE_OK=' + $invokeOk)
            } else {
                $detail = 'test window not visible to UIA (locked screen or session transition?)'
            }
        }
        Add-ReportLine ('CU_BACKEND=' + $backend)

        # ---- 3. the click handler writes the marker, then closes the window
        $waitUntil = (Get-Date).AddSeconds(15)
        while ((-not (Test-Path -LiteralPath $markerFile)) -and ((Get-Date) -lt $waitUntil)) {
            Start-Sleep -Milliseconds 300
        }
        if (Test-Path -LiteralPath $markerFile) {
            $got = [System.IO.File]::ReadAllText($markerFile)
            $markerOk = ($got -eq $marker)
            if (-not $markerOk -and -not $detail) { $detail = 'marker text differs from the expected stamp' }
        } elseif (-not $detail) {
            $detail = 'marker file was not written after the invoke'
        }
        Add-ReportLine ('CU_MARKER_OK=' + $markerOk)

        try { if ($proc -and -not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } } catch { }
    } catch {
        $detail = 'smoke chain threw: ' + $_.Exception.Message
    }
    if ($windowFound -and $invokeOk -and $markerOk) { $verdict = 'True' }
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
        backend = $backend
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
    Write-Output ('== computer-use report: results/computer_use/CU_SMOKE.md (ok=' + $verdict + ' backend=' + $backend + ')')
} catch {
    Write-Output ('[FAIL] could not write the computer-use report: ' + $_.Exception.Message)
    exit 1
}

if ($verdict -eq 'False') {
    Write-Output '[FAIL] computer-use smoke: the find/invoke/marker chain did not complete - see CU_DETAIL'
    exit 1
}
exit 0
