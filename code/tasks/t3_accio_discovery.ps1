# t3_accio_discovery.ps1 - read-only inventory of E:\AccioWork, runs ON THE
# LOCAL MACHINE inside code\local_check.ps1 section 4 (round 2+).
#
# The user asked to "continue the unfinished replication task at E:\AccioWork".
# The sandbox agent cannot see the laptop's E: drive, so this task is the
# bridge's eyes: a NON-DESTRUCTIVE listing (directories first, then files with
# size and last-write time, depth-capped and count-capped) that lands in
# results\accio\ACCIO_TREE.md/.json and gets pushed back by the watcher.
# The agent then plans the actual replication work from that receipt.
#
# This probe always exits 0 once its report is written - a missing folder is a
# legitimate finding (ACCIO_FOUND=False), not a broken bridge. It exits 1 only
# when the report itself cannot be written.
# ASCII-only on purpose (Windows PowerShell 5.1 decodes .ps1 as ANSI/GBK);
# Write-Output only (the watcher captures stdout into the round receipt).

$ErrorActionPreference = 'Continue'
Set-Location (Join-Path $PSScriptRoot '..\..')
$repoRoot = (Get-Location).Path
$outDir = Join-Path $repoRoot 'results\accio'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$reportMd = Join-Path $outDir 'ACCIO_TREE.md'
$reportJson = Join-Path $outDir 'ACCIO_TREE.json'

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

$target = 'E:\AccioWork'
$maxEntries = 400

$found = $false
try { $found = [bool](Test-Path -LiteralPath $target) } catch { $found = $false }
$truncated = $false
$fileCount = 0
$dirCount = 0
$docKinds = [ordered]@{}
$topNames = @()

Add-ReportLine '# AccioWork discovery (read-only)'
Add-ReportLine ''
Add-ReportLine ('ACCIO_ROUND=' + $round)
Add-ReportLine ('time_local=' + (Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz'))
Add-ReportLine ('host=' + $env:COMPUTERNAME)
Add-ReportLine ('target=' + $target)
Add-ReportLine ('ACCIO_FOUND=' + $found)
Add-ReportLine ''

if ($found) {
    try {
        $top = @(Get-ChildItem -LiteralPath $target -Force -ErrorAction SilentlyContinue)
        Add-ReportLine ('## Top level (' + $top.Count + ' entries, directories first)')
        Add-ReportLine ''
        foreach ($e in @($top | Sort-Object { -not $_.PSIsContainer }, Name)) {
            $kind = 'file'
            if ($e.PSIsContainer) { $kind = 'dir ' }
            $sizeText = ''
            if (-not $e.PSIsContainer) { $sizeText = ' ' + [string][math]::Round($e.Length / 1KB, 1) + ' KB' }
            Add-ReportLine ('- [' + $kind + '] ' + $e.Name + $sizeText + ' (' + $e.LastWriteTime.ToString('yyyy-MM-dd HH:mm') + ')')
            if ($topNames.Count -lt 60) { $topNames += $e.Name }
        }
        Add-ReportLine ''

        Add-ReportLine ('## Files (recursive, depth<=4, cap ' + $maxEntries + ')')
        Add-ReportLine ''
        $all = @(Get-ChildItem -LiteralPath $target -Recurse -Depth 3 -Force -File -ErrorAction SilentlyContinue | Sort-Object FullName)
        foreach ($f in $all) {
            if ($fileCount -ge $maxEntries) { $truncated = $true; break }
            $rel = $f.FullName.Substring($target.Length).TrimStart('\')
            $ext = ([System.IO.Path]::GetExtension($f.Name)).ToLowerInvariant()
            if ($ext) {
                if (-not $docKinds.Contains($ext)) { $docKinds[$ext] = 0 }
                $docKinds[$ext] = [int]$docKinds[$ext] + 1
            }
            Add-ReportLine ('- ' + $rel + ' | ' + [string][math]::Round($f.Length / 1KB, 1) + ' KB | ' + $f.LastWriteTime.ToString('yyyy-MM-dd HH:mm'))
            $fileCount += 1
        }
        foreach ($e in @($top)) { if ($e.PSIsContainer) { $dirCount += 1 } }
        Add-ReportLine ''
        if ($truncated) { Add-ReportLine ('(list truncated at the ' + $maxEntries + '-file cap - there is more on disk)') }
    } catch {
        Add-ReportLine ('scan_error=' + $_.Exception.Message)
    }
} else {
    Add-ReportLine 'E:\AccioWork does not exist on this machine. Nothing was created or moved; this probe never writes outside results\.'
}

Add-ReportLine ''
$kindText = 'none'
if ($docKinds.Count -gt 0) {
    $kindParts = @()
    foreach ($k in $docKinds.Keys) { $kindParts += ($k + '=' + [string]$docKinds[$k]) }
    $kindText = ($kindParts -join ' ')
}
Add-ReportLine ('doc_kinds=' + $kindText)
Add-ReportLine ('files_listed=' + $fileCount + ' top_dirs=' + $dirCount + ' truncated=' + $truncated)
Add-ReportLine 'ACCIO_PROBE_OK=True'

try {
    Set-Content -LiteralPath $reportMd -Value $report -Encoding UTF8
    $obj = [ordered]@{
        round = $round
        target = $target
        found = $found
        probe_ok = $true
        top_level = $topNames
        top_dirs = $dirCount
        files_listed = $fileCount
        truncated = $truncated
        doc_kinds = $docKinds
        host = $env:COMPUTERNAME
        time_local = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz')
    }
    Set-Content -LiteralPath $reportJson -Value ($obj | ConvertTo-Json -Depth 4) -Encoding UTF8
    Write-Output ('== accio report: results/accio/ACCIO_TREE.md (found=' + $found + ')')
} catch {
    Write-Output ('[FAIL] could not write the accio report: ' + $_.Exception.Message)
    exit 1
}
exit 0
