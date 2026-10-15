# t4_accio_asar_inventory.ps1 - Accio replication, stage 1: parse the Electron
# app.asar of E:\AccioWork ON THE LOCAL MACHINE and build a full index plus a
# targeted small-text extraction, all read-only against E:\.
#
# Background: E:\AccioWork is an installed Electron app (Accio.exe + resources\
# app.asar 118 MB + accio-mcp-cli + chrome relay extension + workflow DSLs +
# wiki-skills + pre-install bundles). The replication work needs the asar's
# content model. The asar header is pure JSON: [u32 headerBufLen][u32 jsonLen]
# [json][file blobs at 4+headerBufLen], so NO node runtime is required -
# Windows PowerShell 5.1 alone can index and range-read it.
#
# Outputs (all under results\accio\ - lesson of round 8: children cannot
# reliably write to %TEMP%; only this directory is proven writable+pushable):
#   ASAR_TREE.md     - human summary + ACCIO_ASAR_OK marker
#   asar_index.json  - full path/size index (capped)
#   ASAR_EXTRACT_INDEX.md + extract\... - package.json + main/preload entry
#     points (per-file <=256 KB, total <=3 MB, secret-shape redaction)
#   RESOURCES_CAPTURE.md + resources_capture\... - the small text files next
#     to the asar (relay extension js/json, workflow DSLs, wiki skill,
#     remote-tools.json, app-update.yml, install-monitor-manifest.json,
#     install-channel.json) that define much of the replication surface
# Exit 0 = inventory produced (ACCIO_ASAR_OK=True), exit 1 = real failure.
# ASCII-only; Write-Output only (watcher captures stdout into the receipt).

$ErrorActionPreference = 'Continue'
Set-Location (Join-Path $PSScriptRoot '..\..')
$repoRoot = (Get-Location).Path
$accioDir = 'E:\AccioWork'
$asarPath = Join-Path $accioDir 'resources\app.asar'
$resDir = Join-Path $accioDir 'resources'
$outDir = Join-Path $repoRoot 'results\accio'
$extractDir = Join-Path $outDir 'extract'
$resCapDir = Join-Path $outDir 'resources_capture'
New-Item -ItemType Directory -Force -Path $outDir,$extractDir,$resCapDir | Out-Null
$treeMd = Join-Path $outDir 'ASAR_TREE.md'
$indexJson = Join-Path $outDir 'asar_index.json'
$extractMd = Join-Path $outDir 'ASAR_EXTRACT_INDEX.md'
$resMd = Join-Path $outDir 'RESOURCES_CAPTURE.md'

$report = New-Object System.Collections.Generic.List[string]
function Add-ReportLine([string]$Text) { [void]$script:report.Add($Text); Write-Output $Text }
function Protect-Text([string]$s) {
    if ($null -eq $s) { return '' }
    foreach ($pat in @('ya29\.[A-Za-z0-9_\.\-]+','1//[A-Za-z0-9_\.\-]+','sk-[A-Za-z0-9]{16,}',
                       'xox[baprs]-[A-Za-z0-9\-]{8,}','AKIA[0-9A-Z]{16}','ghp_[A-Za-z0-9]{20,}',
                       'glpat-[A-Za-z0-9_\-]{12,}','eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{8,}',
                       '-----BEGIN[^\-]*-----')) {
        try { $s = [regex]::Replace($s, $pat, '[REDACTED]') } catch { }
    }
    return $s
}

$round = -1
try {
    $hs = Get-Content -LiteralPath (Join-Path $repoRoot 'results\status\handshake.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $round = [int]$hs.round
} catch { $round = -1 }

Add-ReportLine '# Accio app.asar inventory (read-only, stage 1 of the replication)'
Add-ReportLine ''
Add-ReportLine ('ASAR_ROUND=' + $round)
Add-ReportLine ('time_local=' + (Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz'))
Add-ReportLine ('host=' + $env:COMPUTERNAME)
Add-ReportLine ('target=' + $asarPath)

if (-not (Test-Path -LiteralPath $asarPath)) {
    Add-ReportLine 'ACCIO_ASAR_OK=False'
    Add-ReportLine 'detail=app.asar missing under E:\AccioWork\resources'
    Set-Content -LiteralPath $treeMd -Value $report -Encoding UTF8
    exit 1
}

$asarLen = (Get-Item -LiteralPath $asarPath).Length
$sha = ''
try { $sha = (Get-FileHash -LiteralPath $asarPath -Algorithm SHA256).Hash } catch { }
Add-ReportLine ('asar_bytes=' + $asarLen)
Add-ReportLine ('asar_sha256=' + $sha)

# ---------------- parse the asar header ----------------
$fs = [System.IO.File]::OpenRead($asarPath)
try {
    $lenBuf = New-Object byte[] 4
    [void]$fs.Read($lenBuf, 0, 4)
    $headerBufLen = [System.BitConverter]::ToUInt32($lenBuf, 0)
    $jsonLen = [int]($headerBufLen - 4)
    [void]$fs.Read($lenBuf, 0, 4)   # jsonLen as stored inside the pickle
    $jsonLenStored = [System.BitConverter]::ToUInt32($lenBuf, 0)
    if ($jsonLenStored -ne $jsonLen) { throw ('header length mismatch: buf=' + $headerBufLen + ' json=' + $jsonLenStored) }
    if ($jsonLen -gt 67108864) { throw ('header json unreasonably large: ' + $jsonLen) }
    $jsonBuf = New-Object byte[] $jsonLen
    $readTotal = 0
    while ($readTotal -lt $jsonLen) {
        $n = $fs.Read($jsonBuf, $readTotal, ($jsonLen - $readTotal))
        if ($n -le 0) { throw 'short read on the asar header' }
        $readTotal += $n
    }
    $headerJson = [System.Text.Encoding]::UTF8.GetString($jsonBuf)
    $blobBase = [uint64](4 + $headerBufLen)
} finally {
    $fs.Dispose()
}
Add-ReportLine ('header_json_bytes=' + $jsonLen + ' blob_base=' + $blobBase)

$root = $null
try { $root = ($headerJson | ConvertFrom-Json) } catch {
    Add-ReportLine 'ACCIO_ASAR_OK=False'
    Add-ReportLine ('detail=header JSON parse failed: ' + $_.Exception.Message)
    Set-Content -LiteralPath $treeMd -Value $report -Encoding UTF8
    exit 1
}

# ---------------- walk the tree into a flat index ----------------
$entries = New-Object System.Collections.Generic.List[object]
function Walk-AsarNode([object]$Node, [string]$Prefix) {
    if ($null -eq $Node) { return }
    if ($Node.PSObject.Properties.Name -contains 'files') {
        foreach ($p in @($Node.files.PSObject.Properties)) {
            $childPrefix = $p.Name
            if ($Prefix) { $childPrefix = $Prefix + '/' + $p.Name }
            $v = $p.Value
            if ($null -ne $v -and ($v.PSObject.Properties.Name -contains 'size' -or $v.PSObject.Properties.Name -contains 'link')) {
                $size = 0; $off = '0'; $isLink = $false
                try { $size = [int64]$v.size } catch { }
                try { $off = [string]$v.offset } catch { }
                if ($v.PSObject.Properties.Name -contains 'link') { $isLink = $true }
                $script:entries.Add([pscustomobject]@{ path = $childPrefix; size = $size; offset = $off; link = $isLink })
            } else {
                Walk-AsarNode $v $childPrefix
            }
        }
    }
}
Walk-AsarNode $root ''
Add-ReportLine ('files_indexed=' + $entries.Count)

$extCounts = @{}
foreach ($e in $entries) {
    $ext = ([System.IO.Path]::GetExtension($e.path)).ToLowerInvariant()
    if (-not $ext) { $ext = '(none)' }
    if (-not $extCounts.Contains($ext)) { $extCounts[$ext] = 0 }
    $extCounts[$ext] += 1
}
$extText = (($extCounts.GetEnumerator() | Sort-Object Value -Descending | ForEach-Object { $_.Key + '=' + $_.Value }) -join ' ')
Add-ReportLine ('ext_counts=' + $extText)

Add-ReportLine ''
Add-ReportLine '## largest entries'
foreach ($e in @($entries | Sort-Object size -Descending | Select-Object -First 40)) {
    Add-ReportLine ('- ' + $e.path + ' | ' + [string][math]::Round($e.size / 1KB, 1) + ' KB')
}
Add-ReportLine ''
Add-ReportLine '## first paths (cap 400)'
$shown = 0
foreach ($e in @($entries | Sort-Object path)) {
    if ($shown -ge 400) { break }
    Add-ReportLine ('- ' + $e.path + ' | ' + [string][math]::Round($e.size / 1KB, 1) + ' KB')
    $shown += 1
}

# ---------------- targeted small-text extraction ----------------
$extractNotes = New-Object System.Collections.Generic.List[string]
$wantRx = [regex]'(^|/)(package\.json|app-update\.yml|(.*[\/\\])?(main|preload|index|app|server|cli)\.(js|cjs|mjs|ts|json))$'
$perFileCap = 262144
$totalCap = 3145728
$totalOut = 0
$extracted = 0
$fs2 = [System.IO.File]::OpenRead($asarPath)
try {
    foreach ($e in @($entries | Sort-Object size)) {
        if ($extracted -ge 24) { break }
        if ($totalOut -ge $totalCap) { break }
        if ($e.link) { continue }
        if (-not $wantRx.IsMatch($e.path)) { continue }
        if ($e.size -gt $perFileCap) {
            [void]$extractNotes.Add(('- SKIP ' + $e.path + ' (' + [math]::Round($e.size / 1KB, 1) + ' KB > 256 KB cap)'))
            continue
        }
        try {
            $off = [uint64]$e.offset + $blobBase
            $buf = New-Object byte[] $e.size
            [void]$fs2.Seek([int64]$off, [System.IO.SeekOrigin]::Begin)
            $rTot = 0
            while ($rTot -lt $e.size) {
                $n = $fs2.Read($buf, $rTot, ([int]($e.size - $rTot)))
                if ($n -le 0) { throw 'short read' }
                $rTot += $n
            }
            $text = [System.Text.Encoding]::UTF8.GetString($buf)
            $redLenBefore = $text.Length
            $text = Protect-Text $text
            $safeName = ($e.path -replace '[\\/:*?"<>|]', '_')
            $dest = Join-Path $extractDir $safeName
            [System.IO.File]::WriteAllText($dest, $text, (New-Object System.Text.UTF8Encoding($false)))
            $fsha = (Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.Substring(0, 12)
            $totalOut += $e.size
            $extracted += 1
            [void]$extractNotes.Add(('- OK ' + $e.path + ' | ' + [math]::Round($e.size / 1KB, 1) + ' KB | sha12=' + $fsha + ' | redacted=' + ($text.Length -ne $redLenBefore)))
        } catch {
            [void]$extractNotes.Add(('- FAIL ' + $e.path + ' - ' + $_.Exception.Message))
        }
    }
} finally {
    $fs2.Dispose()
}
Add-ReportLine ''
Add-ReportLine ('## extract (<=256 KB entry points, redacted; total ' + [math]::Round($totalOut / 1KB, 1) + ' KB in ' + $extracted + ' files)')

# ---------------- resources-side small-text capture ----------------
$resNotes = New-Object System.Collections.Generic.List[string]
$resWanted = @(
    'app-update.yml',
    'install-monitor-manifest.json',
    'remote-tools.json',
    '..\install-channel.json'
)
$resGlobs = @(
    'chrome-extension\accio-browser-relay\*.*',
    'iab-guard-extension\*.*',
    'global-memory-workflow\dsl\*.json',
    'wiki-skills\merchant-wiki-compiler\*.*',
    'accio-mcp-cli\accio-mcp.mjs'
)
$resCaptured = 0
foreach ($rel in $resWanted) {
    $src = Join-Path $resDir $rel
    if (Test-Path -LiteralPath $src) {
        try {
            $txt = Protect-Text ([System.IO.File]::ReadAllText($src))
            $dest = Join-Path $resCapDir (($rel -replace '[\\/:*?"<>|]', '_'))
            [System.IO.File]::WriteAllText($dest, $txt, (New-Object System.Text.UTF8Encoding($false)))
            $resCaptured += 1
            [void]$resNotes.Add('- OK ' + $rel + ' | ' + [math]::Round(((Get-Item -LiteralPath $src).Length) / 1KB, 1) + ' KB')
        } catch { [void]$resNotes.Add('- FAIL ' + $rel + ' - ' + $_.Exception.Message) }
    }
}
foreach ($g in $resGlobs) {
    $pat = Join-Path $resDir $g
    foreach ($f in @(Get-ChildItem -Path $pat -File -ErrorAction SilentlyContinue)) {
        if ($f.Length -gt 262144) { [void]$resNotes.Add('- SKIP ' + $f.Name + ' (over cap)'); continue }
        if ($f.Extension -notmatch '^\.(js|mjs|json|md|txt|yml|yaml|html)$') { continue }
        try {
            $rel = $f.FullName.Substring($resDir.Length).TrimStart('\')
            $txt = Protect-Text ([System.IO.File]::ReadAllText($f.FullName))
            $dest = Join-Path $resCapDir (($rel -replace '[\\/:*?"<>|]', '_'))
            [System.IO.File]::WriteAllText($dest, $txt, (New-Object System.Text.UTF8Encoding($false)))
            $resCaptured += 1
            [void]$resNotes.Add('- OK ' + $rel + ' | ' + [math]::Round($f.Length / 1KB, 1) + ' KB')
        } catch { [void]$resNotes.Add('- FAIL ' + $f.Name + ' - ' + $_.Exception.Message) }
    }
}
Add-ReportLine ''
Add-ReportLine ('## resources capture (' + $resCaptured + ' files)')

Add-ReportLine ''
Add-ReportLine 'ACCIO_ASAR_OK=True'

Set-Content -LiteralPath $treeMd -Value $report -Encoding UTF8
Set-Content -LiteralPath $extractMd -Value (@('# Extract index (round ' + $round + ')', '') + $extractNotes.ToArray()) -Encoding UTF8
Set-Content -LiteralPath $resMd -Value (@('# Resources capture (round ' + $round + ')', '') + $resNotes.ToArray()) -Encoding UTF8

$idxCap = 25000
$idx = @()
$idxTrunc = $false
foreach ($e in $entries) {
    if ($idx.Count -ge $idxCap) { $idxTrunc = $true; break }
    $idx += @{ path = $e.path; size = $e.size }
}
[ordered]@{
    round = $round
    asar = $asarPath
    asar_bytes = $asarLen
    sha256 = $sha
    header_json_bytes = $jsonLen
    file_count = $entries.Count
    index_truncated = $idxTrunc
    ext_counts = $extCounts
    files = $idx
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $indexJson -Encoding UTF8

Write-Output ('== asar inventory: results/accio/ASAR_TREE.md (files=' + $entries.Count + ', extract=' + $extracted + ', resources=' + $resCaptured + ')')
exit 0
