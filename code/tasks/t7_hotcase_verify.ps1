<#
  t7: Verify the hotcase deliverables (PPTX + PDF) landed on the laptop via
  git download and write results/hotcase/HOTCASE_VERIFY.md.
  - Asserts files exist, sha256 matches expected_hotcase.json.
  - Receipt markers: HOTCASE_OK, HOTCASE_PPTX_SHA256, HOTCASE_PDF_SHA256,
    HOTCASE_PPTX_BYTES, HOTCASE_PDF_BYTES, HOTCASE_ROUND.
  ASCII only.
#>
[CmdletBinding()] param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$cwd = (Get-Location).Path
Set-Location (Join-Path $PSScriptRoot '..\..')
$repoRoot = (Get-Location).Path
$outDir = Join-Path $repoRoot 'results\hotcase'
$expectedPath = Join-Path $repoRoot 'results\status\expected_hotcase.json'
$now = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz')
$envName = $env:COMPUTERNAME
$targets = @('deliverable/hotcase/HOTCASE_REPLICA.pptx', 'deliverable/hotcase/HOTCASE_REPLICA.pdf')
function Write-HotcaseFail([string]$why, [hashtable]$got) {
  if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Force -Path $outDir | Out-Null }
  $lines = @()
  $lines += '# Hotcase Verify (Laptop)'
  $lines += ''
  $lines += '- when: ' + $now + ' (' + $envName + ')'
  $lines += '- host: ' + $envName
  $lines += '- repo: ' + $repoRoot
  $lines += '- why_failed: ' + $why
  foreach ($k in $got.Keys) { $lines += ('- ' + $k + ': ' + $got[$k]) }
  $lines += 'HOTCASE_OK=False'
  $lines += 'HOTCASE_ROUND=1'
  Set-Content -Path (Join-Path $outDir 'HOTCASE_VERIFY.md') -Value $lines -Encoding UTF8
  return
}
Write-Output ('COMPUTERNAME=' + $envName)
Write-Output ('repoRoot=' + $repoRoot)
Write-Output 'phase=t7-hotcase-verify'
if (-not (Test-Path $expectedPath)) { Write-Output 'FAIL: expected json missing'; Write-HotcaseFail 'expected json missing' @{}; exit 1 }
$expected = Get-Content -Raw -Path $expectedPath | ConvertFrom-Json
$expMap = @{}
foreach ($prop in $expected.files.PSObject.Properties) { $expMap[$prop.Name] = ([string]$prop.Value).ToUpperInvariant() }
$ok = $true
$got = @{}
foreach ($t in $targets) {
  $p = Join-Path $repoRoot ($t -replace '/', [IO.Path]::DirectorySeparatorChar)
  if (-not (Test-Path $p)) { $ok = $false; $got[$t] = 'MISSING'; continue }
  $sha = (Get-FileHash -Path $p -Algorithm SHA256).Hash.ToUpperInvariant()
  $len = (Get-Item $p).Length
  $got[$t] = $sha + ' bytes=' + $len
  $expSha = '<none>'
  if ($expMap.ContainsKey($t)) { $expSha = $expMap[$t] }
  if ($sha -ne $expSha) { $ok = $false }
  Write-Output ($t + ' sha256=' + $sha + ' match=' + ($sha -eq $expSha))
}
if (-not $ok) { Write-Output 'FAIL: hash mismatch or missing'; Write-HotcaseFail 'hash mismatch or missing' $got; exit 1 }
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Force -Path $outDir | Out-Null }
$pptxSha = (Get-FileHash -Path (Join-Path $repoRoot ($targets[0] -replace '/', [IO.Path]::DirectorySeparatorChar)) -Algorithm SHA256).Hash.ToUpperInvariant()
$pdfSha = (Get-FileHash -Path (Join-Path $repoRoot ($targets[1] -replace '/', [IO.Path]::DirectorySeparatorChar)) -Algorithm SHA256).Hash.ToUpperInvariant()
$body = @()
$body += '# Hotcase Verify (Laptop)'
$body += ''
$body += '- when: ' + $now + ' (' + $envName + ')'
$body += '- host: ' + $envName
$body += '- repo: ' + $repoRoot
$body += '- targets: ' + ($targets -join ', ')
$body += '- sha256_match: True (both)'
$body += 'HOTCASE_OK=True'
$body += ('HOTCASE_PPTX_SHA256=' + $pptxSha)
$body += ('HOTCASE_PDF_SHA256=' + $pdfSha)
$body += ('HOTCASE_PPTX_BYTES=' + (Get-Item (Join-Path $repoRoot ($targets[0] -replace '/', [IO.Path]::DirectorySeparatorChar))).Length)
$body += ('HOTCASE_PDF_BYTES=' + (Get-Item (Join-Path $repoRoot ($targets[1] -replace '/', [IO.Path]::DirectorySeparatorChar))).Length)
$body += 'HOTCASE_ROUND=1'
Set-Content -Path (Join-Path $outDir 'HOTCASE_VERIFY.md') -Value $body -Encoding UTF8
Write-Output 'HOTCASE_OK=True'
Write-Output 'HOTCASE_ROUND=1'
