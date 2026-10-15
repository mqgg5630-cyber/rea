# t5_accio_symbolscan.ps1 - Accio replication, stage 2: symbol-level scan of
# the big bundles INSIDE E:\AccioWork\resources\app.asar, read-only, ON THE
# LOCAL MACHINE. The bundles are minified (single-line), so this extracts
# TOKENS (deduped match lists) and short redacted context windows instead of
# matching lines - and never writes the megabyte bodies to the repo.
#
# Targets (range-read straight out of the asar via the round-12 layout):
#   out/main/index.js          (Electron main entry)
#   out/main/gateway-worker.js (the 13 MB AI gateway worker)
#   out/main/workflow-worker.js
#   out/renderer/assets/index-*.js + app-store-*.js (renderer core, <=1.6 MB)
# Categories: ipcMain channels, webContents.send channels, custom protocols,
# process.env keys, external URL hosts, MCP tool names, spawns/execFile,
# worker creation, webPreferences/userData contexts.
# Output: results\accio\SYMBOL_SCAN.md (+ SYMBOL_OK marker). Exit 0 = scanned.
# ASCII-only; Write-Output only.

$ErrorActionPreference = 'Continue'
Set-Location (Join-Path $PSScriptRoot '..\..')
$repoRoot = (Get-Location).Path
$asarPath = 'E:\AccioWork\resources\app.asar'
$outDir = Join-Path $repoRoot 'results\accio'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$scanMd = Join-Path $outDir 'SYMBOL_SCAN.md'

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
function Write-SymbolFail([string]$Stage, [string]$Message) {
    Add-ReportLine 'ACCIO_SYMBOL_OK=False'
    Add-ReportLine ('detail=stage ' + $Stage + ': ' + $Message)
    Set-Content -LiteralPath $scanMd -Value $report -Encoding UTF8
    exit 1
}

$round = -1
try {
    $hs = Get-Content -LiteralPath (Join-Path $repoRoot 'results\status\handshake.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $round = [int]$hs.round
} catch { $round = -1 }

Add-ReportLine '# Accio app.asar symbol scan (read-only, stage 2 of the replication)'
Add-ReportLine ''
Add-ReportLine ('SYMBOL_ROUND=' + $round)
Add-ReportLine ('time_local=' + (Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz'))
Add-ReportLine ('host=' + $env:COMPUTERNAME)

# ---- locate the target entries via the round-12 header probe ----
if (-not (Test-Path -LiteralPath $asarPath)) { Write-SymbolFail 'target' 'app.asar missing' }
$headerJson = $null
$jsonLen = 0
$baseCands = New-Object System.Collections.Generic.List[uint64]
$fs = $null
try {
    $fs = [System.IO.File]::OpenRead($asarPath)
    $head = New-Object byte[] 32
    [void]$fs.Read($head, 0, 32)
    $words = @()
    for ($w = 0; $w -lt 8; $w++) { $words += [System.BitConverter]::ToUInt32($head, $w * 4) }
    foreach ($off in @(4, 8, 12, 16, 20)) {
        if ($headerJson) { break }
        $cdLen = [int64]$words[($off - 4) / 4]
        if ($cdLen -le 16 -or $cdLen -gt 67108864) { continue }
        $pb = New-Object byte[] 9
        [void]$fs.Seek([int64]$off, [System.IO.SeekOrigin]::Begin)
        [void]$fs.Read($pb, 0, 9)
        if (-not ([System.Text.Encoding]::UTF8.GetString($pb)).StartsWith('{"files"')) { continue }
        $jb = New-Object byte[] $cdLen
        [void]$fs.Seek([int64]$off, [System.IO.SeekOrigin]::Begin)
        $rTot = 0
        while ($rTot -lt $cdLen) {
            $n = $fs.Read($jb, $rTot, ([int]($cdLen - $rTot)))
            if ($n -le 0) { break }
            $rTot += $n
        }
        if ($rTot -eq $cdLen) {
            $txt = [System.Text.Encoding]::UTF8.GetString($jb)
            $probe = $null
            try { $probe = ($txt | ConvertFrom-Json) } catch { $probe = $null }
            if ($null -ne $probe -and ($probe.PSObject.Properties.Name -contains 'files')) {
                $headerJson = $txt
                $jsonLen = $cdLen
                foreach ($b in @([uint64]($off + $cdLen), [uint64](4 + $words[1]), [uint64](8 + $words[2]), [uint64](12 + $words[3]))) {
                    if (-not $baseCands.Contains($b)) { $baseCands.Add($b) }
                }
            }
        }
    }
} catch { Write-SymbolFail 'header' $_.Exception.Message } finally { if ($fs) { $fs.Dispose() } }
if (-not $headerJson) { Write-SymbolFail 'header' 'no layout candidate parsed' }
$root = $null
try { $root = ($headerJson | ConvertFrom-Json) } catch { Write-SymbolFail 'header-json' $_.Exception.Message }

$entries = New-Object System.Collections.Generic.List[object]
function Walk-AsarNode([object]$Node, [string]$Prefix) {
    if ($null -eq $Node) { return }
    if ($Node.PSObject.Properties.Name -contains 'files') {
        foreach ($p in @($Node.files.PSObject.Properties)) {
            $childPrefix = $p.Name
            if ($Prefix) { $childPrefix = $Prefix + '/' + $p.Name }
            $v = $p.Value
            if ($null -ne $v -and ($v.PSObject.Properties.Name -contains 'size')) {
                $script:entries.Add([pscustomobject]@{ path = $childPrefix; size = [int64]$v.size; offset = [string]$v.offset })
            } else { Walk-AsarNode $v $childPrefix }
        }
    }
}
Walk-AsarNode $root ''

# ---- empirical blob base ----
$pkgEntry = $null
foreach ($e in $entries) { if ($e.path -eq 'package.json') { $pkgEntry = $e; break } }
if (-not $pkgEntry) { foreach ($e in @($entries | Sort-Object size)) { if ($e.path -match '\.json$' -and $e.size -gt 10) { $pkgEntry = $e; break } } }
$resolvedBase = $null
if ($pkgEntry) {
    $fsb = $null
    try {
        $fsb = [System.IO.File]::OpenRead($asarPath)
        foreach ($b in $baseCands) {
            try {
                $n = [int][Math]::Min([int64]$pkgEntry.size, 2048)
                $bb = New-Object byte[] $n
                [void]$fsb.Seek([int64]([uint64]$pkgEntry.offset + $b), [System.IO.SeekOrigin]::Begin)
                $rr = $fsb.Read($bb, 0, $n)
                if (([System.Text.Encoding]::UTF8.GetString($bb, 0, $rr)).TrimStart().StartsWith('{')) { $resolvedBase = $b; break }
            } catch { }
        }
    } finally { if ($fsb) { $fsb.Dispose() } }
}
if ($null -eq $resolvedBase) { Write-SymbolFail 'blob-base' 'no base decoded package.json' }
Add-ReportLine ('blob_base=' + $resolvedBase + ' header_json_bytes=' + $jsonLen + ' files_indexed=' + $entries.Count)

# ---- pick the scan targets ----
$targets = New-Object System.Collections.Generic.List[object]
foreach ($want in @('out/main/index.js', 'out/main/gateway-worker.js', 'out/main/workflow-worker.js')) {
    foreach ($e in $entries) { if ($e.path -eq $want) { $targets.Add($e); break } }
}
$rendererPicks = @($entries | Where-Object { $_.path -match '^out/renderer/assets/(index|app-store)-[^/]+\.js$' -and $_.size -le 1700000 } | Sort-Object size -Descending | Select-Object -First 2)
foreach ($e in $rendererPicks) { $targets.Add($e) }
Add-ReportLine ('scan_targets=' + (($targets | ForEach-Object { $_.path + '(' + [math]::Round($_.size / 1KB, 1) + 'KB)' }) -join ', '))

# ---- scanners ----
function Read-BlobText([object]$Entry) {
    $fsl = [System.IO.File]::OpenRead($asarPath)
    try {
        $buf = New-Object byte[] $Entry.size
        [void]$fsl.Seek([int64]([uint64]$Entry.offset + $resolvedBase), [System.IO.SeekOrigin]::Begin)
        $rTot = 0
        while ($rTot -lt $Entry.size) {
            $n = $fsl.Read($buf, $rTot, ([int]($Entry.size - $rTot)))
            if ($n -le 0) { break }
            $rTot += $n
        }
        if ($rTot -ne $Entry.size) { throw 'short read' }
        return [System.Text.Encoding]::UTF8.GetString($buf)
    } finally { $fsl.Dispose() }
}
function Get-DedupMatches([string]$Text, [string]$Pattern, [int]$Cap) {
    $seen = @{}
    $list = New-Object System.Collections.Generic.List[string]
    foreach ($mm in [regex]::Matches($Text, $Pattern)) {
        $val = [string]$mm.Groups[1].Value
        if ($val.Length -gt 90) { continue }
        if (-not $seen.Contains($val)) {
            $seen[$val] = $true
            if ($list.Count -lt $Cap) { $list.Add($val) }
        }
    }
    return ,($list.ToArray())
}
function Get-Contexts([string]$Text, [string]$Pattern, [int]$Cap, [int]$Each) {
    $out = New-Object System.Collections.Generic.List[string]
    $n = 0
    foreach ($mm in [regex]::Matches($Text, $Pattern)) {
        if ($n -ge $Cap) { break }
        $start = [Math]::Max(0, $mm.Index - 60)
        $len = [Math]::Min($Each, $Text.Length - $start)
        $ctx = $Text.Substring($start, $len) -replace '\s+', ' '
        $ctx = Protect-Text $ctx
        $out.Add($ctx)
        $n += 1
    }
    return ,($out.ToArray())
}

$cats = @(
    @{ key = 'ipc_main_channels'; pat = 'ipcMain\s*\.\s*(?:handle|on)\s*\(\s*[''"`]([^''"`]{3,90})'; kind = 'list' },
    @{ key = 'renderer_send_channels'; pat = 'webContents\.send\s*\(\s*[''"`]([^''"`]{3,90})'; kind = 'list' },
    @{ key = 'mcp_tool_names'; pat = '(?:registerTool|\.tool|tool:)\s*\(?\s*[''"`]([a-zA-Z0-9_\-\.]{3,60})[''"`]'; kind = 'list' },
    @{ key = 'process_env_keys'; pat = 'process\.env\.([A-Z0-9_]{3,45})'; kind = 'list' },
    @{ key = 'external_hosts'; pat = 'https?://([a-z0-9][a-z0-9\-\.]{2,60})'; kind = 'list' },
    @{ key = 'spawned_binaries'; pat = '(?:spawn|execFile|exec)\s*\(\s*[''"`]([^''"`]{2,90})'; kind = 'list' },
    @{ key = 'custom_protocols'; pat = '(?:registerSchemesAsPrivileged|protocol\.handle|registerFileProtocol|registerStringProtocol)\s*[\(\,]?\s*[''"`]?([a-z][a-z0-9\+\-\.]{1,30})'; kind = 'list' },
    @{ key = 'worker_creation'; pat = 'new Worker\s*\('; kind = 'context' },
    @{ key = 'webpreferences'; pat = 'webPreferences'; kind = 'context' },
    @{ key = 'userdata_paths'; pat = 'getPath\s*\(\s*[''"`]userData'; kind = 'context' },
    @{ key = 'db_and_memory'; pat = '(?:better_sqlite3|sqlite-vec|\.vec_|vectorIndex)'; kind = 'context' },
    @{ key = 'agent_runtime_signals'; pat = '(?:systemPrompt|system_prompt|toolCalls|tool_calls|stopSequences|maxTokens|modelProvider|model_provider)'; kind = 'context' }
)

foreach ($t in $targets) {
    Add-ReportLine ''
    Add-ReportLine ('## ' + $t.path + ' (' + [math]::Round($t.size / 1KB, 1) + ' KB)')
    $body = ''
    try { $body = Read-BlobText $t } catch {
        Add-ReportLine ('  read_error=' + $_.Exception.Message)
        continue
    }
    Add-ReportLine ('  chars=' + $body.Length)
    foreach ($cat in $cats) {
        if ($cat.kind -eq 'list') {
            $vals = @(Get-DedupMatches $body $cat.pat 150)
            Add-ReportLine ('  ' + $cat.key + ' (' + $vals.Count + '):')
            if ($vals.Count -gt 0) {
                $chunk = ''
                foreach ($v in @($vals | Sort-Object)) {
                    if (($chunk.Length + $v.Length) -gt 160) { Add-ReportLine ('    ' + $chunk.TrimEnd(', ')); $chunk = '' }
                    $chunk += $v + ', '
                }
                if ($chunk) { Add-ReportLine ('    ' + $chunk.TrimEnd(', ')) }
            }
        } else {
            $ctxs = @(Get-Contexts $body $cat.pat 6 240)
            Add-ReportLine ('  ' + $cat.key + ' contexts (' + $ctxs.Count + '):')
            foreach ($ctx in $ctxs) { Add-ReportLine ('    > ' + $ctx) }
        }
    }
}

Add-ReportLine ''
Add-ReportLine 'ACCIO_SYMBOL_OK=True'
Set-Content -LiteralPath $scanMd -Value $report -Encoding UTF8
Write-Output ('== symbol scan: results/accio/SYMBOL_SCAN.md (targets=' + $targets.Count + ')')
exit 0
