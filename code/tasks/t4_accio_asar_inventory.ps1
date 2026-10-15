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

# ---------------- parse the asar header (layout auto-probe) ----------------
# asar writers differ: chromium-pickle wraps the JSON string with its own
# length prefix ([u32 bufLen=jsonLen+4][u32 jsonLen][json]), bare writers just
# do [u32 jsonLen][json]. Probe the candidates and keep the one whose payload
# starts with '{' AND parses AND yields a .files tree.
function Write-AsarFail([string]$Stage, [string]$Message) {
    Add-ReportLine 'ACCIO_ASAR_OK=False'
    Add-ReportLine ('detail=stage ' + $Stage + ': ' + $Message)
    Set-Content -LiteralPath $treeMd -Value $report -Encoding UTF8
    exit 1
}
$headerJson = $null
$jsonLen = 0
$blobBase = [uint64]0
$fs = $null
try {
    $fs = [System.IO.File]::OpenRead($asarPath)
    $head = New-Object byte[] 64
    [void]$fs.Read($head, 0, 64)
    Add-ReportLine ('head_hex=' + ([System.BitConverter]::ToString($head)))
    $asciiHead = ''
    foreach ($hb in $head) {
        if ($hb -ge 32 -and $hb -lt 127) { $asciiHead += [char]$hb } else { $asciiHead += '.' }
    }
    Add-ReportLine ('head_ascii=' + $asciiHead)
    # read the first 8 u32 words; chromium-Pickle nests length words, so the
    # JSON can start at 4/8/12/16/20 with its length in the preceding word
    $words = @()
    for ($w = 0; $w -lt 8; $w++) { $words += [System.BitConverter]::ToUInt32($head, $w * 4) }
    Add-ReportLine ('u32words=' + ($words -join ','))
    $marker = [System.Text.Encoding]::UTF8.GetBytes('{"files"')
    $baseCands = New-Object System.Collections.Generic.List[uint64]
    $probeLog = @()
    foreach ($off in @(4, 8, 12, 16, 20)) {
        if ($headerJson) { break }
        $lenIdx = ($off - 4) / 4
        $cdLen = [int64]$words[$lenIdx]
        if ($cdLen -le 16 -or $cdLen -gt 67108864) { $probeLog += ('off' + $off + '=skip-len(' + $cdLen + ')'); continue }
        try {
            $probeBytes = New-Object byte[] 9
            [void]$fs.Seek([int64]$off, [System.IO.SeekOrigin]::Begin)
            [void]$fs.Read($probeBytes, 0, 9)
            $probeTxt = [System.Text.Encoding]::UTF8.GetString($probeBytes)
            if (-not $probeTxt.StartsWith('{"files"')) { $probeLog += ('off' + $off + '=no-marker[' + ($probeTxt -replace '[^\x20-\x7E]', '.') + ']'); continue }
            $jb = New-Object byte[] $cdLen
            [void]$fs.Seek([int64]$off, [System.IO.SeekOrigin]::Begin)
            $rTot = 0
            while ($rTot -lt $cdLen) {
                $n = $fs.Read($jb, $rTot, ([int]($cdLen - $rTot)))
                if ($n -le 0) { break }
                $rTot += $n
            }
            if ($rTot -ne $cdLen) { $probeLog += ('off' + $off + '=short-read'); continue }
            $txt = [System.Text.Encoding]::UTF8.GetString($jb)
            $probe = $null
            try { $probe = ($txt | ConvertFrom-Json) } catch { $probe = $null }
            if ($null -ne $probe -and ($probe.PSObject.Properties.Name -contains 'files')) {
                $headerJson = $txt
                $jsonLen = $cdLen
                $probeLog += ('off' + $off + '=ACCEPT(len=' + $cdLen + ')')
                foreach ($b in @([uint64]($off + $cdLen), [uint64](4 + $words[1]), [uint64](8 + $words[2]), [uint64](12 + $words[3]))) {
                    if (-not $baseCands.Contains($b)) { $baseCands.Add($b) }
                }
            } else {
                $probeLog += ('off' + $off + '=parse-failed')
            }
        } catch { $probeLog += ('off' + $off + '=threw') }
    }
    Add-ReportLine ('probe_log=' + ($probeLog -join ' '))
} catch {
    Write-AsarFail 'header-read' $_.Exception.Message
} finally {
    if ($fs) { $fs.Dispose() }
}
if (-not $headerJson) { Write-AsarFail 'header-probe' 'no header layout candidate parsed (see probe_log)' }
Add-ReportLine ('header_json_bytes=' + $jsonLen)

$root = $null
try { $root = ($headerJson | ConvertFrom-Json) } catch {
    Write-AsarFail 'header-json' $_.Exception.Message
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

# ---------------- resolve the blob base empirically ----------------
# the pickled header nests length words; rather than guess which word is the
# size prefix, decode the first small JSON entry under each candidate base
# and keep the one that yields clean UTF-8 starting with '{'
$pkgEntry = $null
foreach ($e in $entries) { if ($e.path -eq 'package.json') { $pkgEntry = $e; break } }
if (-not $pkgEntry) {
    foreach ($e in @($entries | Sort-Object size)) {
        if ($e.path -match '\.json$' -and (-not $e.link) -and $e.size -gt 10) { $pkgEntry = $e; break }
    }
}
$resolvedBase = $null
if ($pkgEntry -and $baseCands.Count -gt 0) {
    $fsb = $null
    try {
        $fsb = [System.IO.File]::OpenRead($asarPath)
        foreach ($b in $baseCands) {
            try {
                $n = [int][Math]::Min([int64]$pkgEntry.size, 2048)
                $bb = New-Object byte[] $n
                [void]$fsb.Seek([int64]([uint64]$pkgEntry.offset + $b), [System.IO.SeekOrigin]::Begin)
                $rr = $fsb.Read($bb, 0, $n)
                $t = [System.Text.Encoding]::UTF8.GetString($bb, 0, $rr).TrimStart()
                if ($t.StartsWith('{')) { $resolvedBase = $b; break }
            } catch { }
        }
    } finally { if ($fsb) { $fsb.Dispose() } }
}
if ($null -eq $resolvedBase) {
    if ($baseCands.Count -gt 0) { $resolvedBase = [uint64]$baseCands[0] } else { Write-AsarFail 'blob-base' 'no blob base candidates' }
}
Add-ReportLine ('blob_base=' + $resolvedBase + ' verified_with=' + $(if ($pkgEntry) { $pkgEntry.path } else { 'none' }))

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
            $off = [uint64]$e.offset + $resolvedBase
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

try {
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
} catch {
    Write-AsarFail 'write-reports' $_.Exception.Message
}

Write-Output ('== asar inventory: results/accio/ASAR_TREE.md (files=' + $entries.Count + ', extract=' + $extracted + ', resources=' + $resCaptured + ')')
exit 0
