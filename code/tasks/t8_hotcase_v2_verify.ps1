<#
  t8: Verify the V2 visual special deck (PPTX + PDF) landed on the laptop via
  git download and write results/hotcase/HOTCASE_V2_VERIFY.md.
  Receipt markers: HOTCASE_V2_OK, HOTCASE_V2_PPTX_SHA256, HOTCASE_V2_PDF_SHA256,
  *_BYTES, HOTCASE_V2_ROUND. ASCII only.
#>
[CmdletBinding()] param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..\..')
$repoRoot = (Get-Location).Path
$outDir = Join-Path $repoRoot 'results\hotcase'
$expectedPath = Join-Path $repoRoot 'results\status\expected_hotcase_v2.json'
$now = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz')
$envName = $env:COMPUTERNAME
$targets = @('deliverable/hotcase/HOTCASE_VISUAL_V2.pptx', 'deliverable/hotcase/HOTCASE_VISUAL_V2.pdf')
function Write-V2Fail([string]$why, [hashtable]$got) {
  if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Force -Path $outDir | Out-Null }
  $lines = @()
  $lines += '# Hotcase V2 Verify (Laptop)'
  $lines += ''
  $lines += '- when: ' + $now + ' (' + $envName + ')'
  $lines += '- repo: ' + $repoRoot
  $lines += '- why_failed: ' + $why
  foreach ($k in $got.Keys) { $lines += ('- ' + $k + ': ' + $got[$k]) }
  $lines += 'HOTCASE_V2_OK=False'
  $lines += 'HOTCASE_V2_ROUND=2'
  Set-Content -Path (Join-Path $outDir 'HOTCASE_V2_VERIFY.md') -Value $lines -Encoding UTF8
}
Write-Output ('COMPUTERNAME=' + $envName)
Write-Output ('repoRoot=' + $repoRoot)
Write-Output 'phase=t8-hotcase-v2-verify'
if (-not (Test-Path $expectedPath)) { Write-Output 'FAIL: expected json missing'; Write-V2Fail 'expected json missing' @{}; exit 1 }
$expected = Get-Content -Raw -Path $expectedPath | ConvertFrom-Json
$expMap = @{}
foreach ($prop in $expected.files.PSObject.Properties) { $expMap[$prop.Name] = ([string]$prop.Value).ToUpperInvariant() }
$ok = $true
$got = @{}
$pptxSha = ''; $pdfSha = ''; $pptxLen = 0; $pdfLen = 0
foreach ($t in $targets) {
  $p = Join-Path $repoRoot ($t -replace '/', [IO.Path]::DirectorySeparatorChar)
  if (-not (Test-Path $p)) { $ok = $false; $got[$t] = 'MISSING'; continue }
  $sha = (Get-FileHash -Path $p -Algorithm SHA256).Hash.ToUpperInvariant()
  $len = (Get-Item $p).Length
  $got[$t] = $sha + ' bytes=' + $len
  $expSha = '<none>'
  if ($expMap.ContainsKey($t)) { $expSha = $expMap[$t] }
  if ($sha -ne $expSha) { $ok = $false }
  if ($t -like '*.pptx') { $pptxSha = $sha; $pptxLen = $len } else { $pdfSha = $sha; $pdfLen = $len }
  Write-Output ($t + ' match=' + ($sha -eq $expSha))
}
if (-not $ok) { Write-Output 'FAIL: hash mismatch or missing'; Write-V2Fail 'hash mismatch or missing' $got; exit 1 }
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Force -Path $outDir | Out-Null }
$body = @()
$body += '# Hotcase V2 Verify (Laptop)'
$body += ''
$body += '- when: ' + $now + ' (' + $envName + ')'
$body += '- host: ' + $envName
$body += '- repo: ' + $repoRoot
$body += '- targets: ' + ($targets -join ', ')
$body += '- sha256_match: True (both)'
$body += 'HOTCASE_V2_OK=True'
$body += ('HOTCASE_V2_PPTX_SHA256=' + $pptxSha)
$body += ('HOTCASE_V2_PDF_SHA256=' + $pdfSha)
$body += ('HOTCASE_V2_PPTX_BYTES=' + $pptxLen)
$body += ('HOTCASE_V2_PDF_BYTES=' + $pdfLen)
$body += 'HOTCASE_V2_ROUND=2'
Set-Content -Path (Join-Path $outDir 'HOTCASE_V2_VERIFY.md') -Value $body -Encoding UTF8
Write-Output 'HOTCASE_V2_OK=True'
Write-Output 'HOTCASE_V2_ROUND=2'
