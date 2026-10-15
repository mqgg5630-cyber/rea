# interop-health.ps1
# Non-secret health report for GitHub, Google Drive/rclone, Kaggle, Tailscale,
# and Muse request protocol. ASCII-only by design.

[CmdletBinding()]
param(
    [string]$GDriveRemote = 'gdrive_main',
    [string]$OutPath = 'results\cloud_interop\INTEROP_HEALTH.md',
    [switch]$ProbeWrite,
    [switch]$CleanupProbe
)

$ErrorActionPreference = 'Continue'
try { $RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path; Set-Location $RepoRoot } catch { }
$lines = New-Object System.Collections.Generic.List[string]
function L($m) { $script:lines.Add([string]$m) | Out-Null; Write-Output $m }
function Mask($s) {
    if (-not $s) { return '' }
    $s = [string]$s
    if ($s.Length -le 4) { return '***' }
    return ($s.Substring(0,2) + '***' + $s.Substring($s.Length-2))
}
function RunText($exe, $ArgList) {
    try { return (& $exe @ArgList 2>&1 | Out-String).Trim() } catch { return $_.Exception.Message }
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutPath) | Out-Null
L '# Cloud interop health report'
L ('time=' + (Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz'))
L ('host=' + $env:COMPUTERNAME)
L ''

L '## Git'
try {
    $branch = (git rev-parse --abbrev-ref HEAD 2>$null | Out-String).Trim()
    $head = (git log -1 --oneline 2>$null | Out-String).Trim()
    L ('branch=' + $branch)
    L ('head=' + $head)
} catch { L ('git_warn=' + $_.Exception.Message) }
L ''

L '## Google Drive / rclone'
$rcloneCmd = Get-Command rclone -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $rcloneCmd) {
    $local = Join-Path $env:LOCALAPPDATA 'Programs\rclone\rclone.exe'
    if (Test-Path -LiteralPath $local) { $rcloneCmd = Get-Item -LiteralPath $local }
}
if (-not $rcloneCmd) {
    L 'rclone_present=False'
} else {
    $rclone = [string]$rcloneCmd.Source
    if (-not $rclone) { $rclone = [string]$rcloneCmd.FullName }
    L ('rclone_present=True path=' + $rclone)
    $remoteWithColon = $GDriveRemote
    if (-not $remoteWithColon.EndsWith(':')) { $remoteWithColon = $remoteWithColon + ':' }
    $remotes = @(((RunText $rclone @('listremotes')) -split "`r?`n") | Where-Object { $_.Trim() })
    $has = $false
    foreach ($r in $remotes) { if ($r.Trim() -eq $remoteWithColon) { $has = $true } }
    L ('gdrive_remote=' + $remoteWithColon + ' present=' + $has)
    $about = RunText $rclone @('about', $remoteWithColon, '--json')
    $aboutOk = ($LASTEXITCODE -eq 0 -and $about)
    if ($aboutOk) {
        L 'gdrive_about_ok=True'
        try {
            $a = $about | ConvertFrom-Json
            if ($a.total) { L ('gdrive_total_bytes=' + $a.total) }
            if ($a.used) { L ('gdrive_used_bytes=' + $a.used) }
            if ($a.free) { L ('gdrive_free_bytes=' + $a.free) }
        } catch { L 'gdrive_about_parse_warn=True' }
    } else {
        L 'gdrive_about_ok=False'
        if ($about) { L ('gdrive_about_detail=' + ($about -replace "`r?`n", ' | ')) }
    }
    if ($ProbeWrite -and $aboutOk) {
        $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
        $tmp = Join-Path $env:TEMP ('arena-gdrive-probe-' + $stamp + '.txt')
        Set-Content -LiteralPath $tmp -Encoding UTF8 -Value ('arena interop probe ' + $stamp + ' host=' + $env:COMPUTERNAME)
        $dst = $remoteWithColon + 'Arena/interop/probe-' + $stamp + '.txt'
        $copy = RunText $rclone @('copyto', $tmp, $dst)
        if ($LASTEXITCODE -eq 0) {
            L ('gdrive_probe_write=True path=' + $dst)
            if ($CleanupProbe) {
                $del = RunText $rclone @('deletefile', $dst)
                L ('gdrive_probe_cleanup_exit=' + $LASTEXITCODE)
            }
        } else {
            L ('gdrive_probe_write=False detail=' + ($copy -replace "`r?`n", ' | '))
        }
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
    }
}
L ''

L '## Kaggle'
$kgCmd = Get-Command kaggle -ErrorAction SilentlyContinue | Select-Object -First 1
if ($kgCmd) {
    L ('kaggle_cli=True path=' + [string]$kgCmd.Source)
    $ver = RunText ([string]$kgCmd.Source) @('--version')
    if ($ver) { L ('kaggle_version=' + ($ver -replace "`r?`n", ' | ')) }
} else { L 'kaggle_cli=False' }
$kgPath = $env:KAGGLE_CONFIG_DIR
if ($kgPath) { $kgFile = Join-Path $kgPath 'kaggle.json' } else { $kgFile = Join-Path $env:USERPROFILE '.kaggle\kaggle.json' }
if (Test-Path -LiteralPath $kgFile) {
    L ('kaggle_json=True path=' + $kgFile)
    try {
        $kg = Get-Content -LiteralPath $kgFile -Raw -Encoding UTF8 | ConvertFrom-Json
        L ('kaggle_username_masked=' + (Mask $kg.username))
        L ('kaggle_key_present=' + [bool]$kg.key)
    } catch { L 'kaggle_json_parse_warn=True' }
} else { L ('kaggle_json=False path=' + $kgFile) }
L ''

L '## Tailscale / machines'
$ts = Get-Command tailscale -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $ts) {
    L 'tailscale_cli=False'
} else {
    L ('tailscale_cli=True path=' + [string]$ts.Source)
    $json = RunText ([string]$ts.Source) @('status','--json')
    if ($LASTEXITCODE -eq 0 -and $json) {
        try {
            $obj = $json | ConvertFrom-Json
            if ($obj.Self) { L ('tailscale_self=' + $obj.Self.HostName + ' online=' + $obj.Self.Online) }
            $n = 0
            foreach ($p in $obj.Peer.PSObject.Properties) {
                $peer = $p.Value
                if ($n -lt 12) { L ('tailscale_peer=' + $peer.HostName + ' online=' + $peer.Online) }
                $n++
            }
            L ('tailscale_peer_count=' + $n)
        } catch { L 'tailscale_status_parse_warn=True' }
    } else { L 'tailscale_status_ok=False' }
}
L ''

L '## Muse protocol'
$proto = 'results\muse\REQUEST_PROTOCOL.md'
$poller = 'code\muse\muse_poll_once.sh'
L ('muse_protocol_present=' + (Test-Path -LiteralPath $proto))
L ('muse_poller_present=' + (Test-Path -LiteralPath $poller))
$req = 'results\muse\requests\muse-smoke-20261003-1718.json'
if (Test-Path -LiteralPath $req) {
    try {
        $rq = Get-Content -LiteralPath $req -Raw -Encoding UTF8 | ConvertFrom-Json
        L ('muse_smoke_state=' + $rq.state)
        L ('muse_smoke_artifact=' + $rq.artifact)
    } catch { L 'muse_smoke_parse_warn=True' }
}
L ''
L 'CLOUD_INTEROP_HEALTH_DONE'
$lines | Set-Content -LiteralPath $OutPath -Encoding UTF8
exit 0
