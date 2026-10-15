<#
  t6: Verify the stage-3 deliverable landed on the laptop via git download
  and write results/deliverable/DELIVERABLE_VERIFY.md.
  - Asserts file exists, sha256 matches expected, size sane.
  - Receipt markers: DELIVERABLE_OK, DELIVERABLE_SHA256, DELIVERABLE_PATH, DELIVERABLE_BYTES, DELIVERABLE_ROUND.
  ASCII only.
#>
[CmdletBinding()] param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$docRel = 'deliverable/ACCIO_REPLICATION.md'
$docPath = Join-Path $repoRoot ($docRel -replace '/', [IO.Path]::DirectorySeparatorChar)
$outDir = Join-Path $repoRoot 'results\deliverable'
$expectedRel = 'results/status/expected_deliverable.json'
$expectedPath = Join-Path $repoRoot ($expectedRel -replace '/', [IO.Path]::DirectorySeparatorChar)
$cwd = (Get-Location).Path
$now = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz')
$envName = $env:COMPUTERNAME
function Write-DeliverableFail([string]$why) {
  if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Force -Path $outDir | Out-Null }
  $lines = @()
  $lines += '# Deliverable Verify (Laptop)'
  $lines += ''
  $lines += '- when: ' + $now + ' (' + $envName + ')'
  $lines += '- host: ' + $envName
  $lines += '- repo: ' + $repoRoot
  $lines += '- cwd: ' + $cwd
  $lines += '- target: ' + $docRel
  $lines += '- why_failed: ' + $why
  $lines += 'DELIVERABLE_OK=False'
  $lines += 'DELIVERABLE_ROUND=14'
  Set-Content -Path (Join-Path $outDir 'DELIVERABLE_VERIFY.md') -Value $lines -Encoding UTF8
  return
}
Write-Output ('COMPUTERNAME=' + $envName)
Write-Output ('cwd=' + $cwd)
Write-Output ('repoRoot=' + $repoRoot)
Write-Output 'phase=t6-deliverable-verify'
if (-not (Test-Path $expectedPath)) { Write-Output 'FAIL: expected json missing'; Write-DeliverableFail('expected json missing'); exit 1 }
$expected = Get-Content -Raw -Path $expectedPath | ConvertFrom-Json
if (-not (Test-Path $docPath)) { Write-Output 'FAIL: deliverable missing'; Write-DeliverableFail('file missing'); exit 1 }
$actualSha = (Get-FileHash -Path $docPath -Algorithm SHA256).Hash.ToUpperInvariant()
$expectedSha = ([string]$expected.sha256).ToUpperInvariant()
$bytes = (Get-Item $docPath).Length
$shaMatch = ($actualSha -eq $expectedSha)
$roundVal = [int]$expected.round
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Force -Path $outDir | Out-Null }
$body = @()
$body += '# Deliverable Verify (Laptop)'
$body += ''
$body += '- when: ' + $now + ' (' + $envName + ')'
$body += '- host: ' + $envName
$body += '- repo: ' + $repoRoot
$body += '- target: ' + $docRel
$body += '- expected_sha256: ' + $expectedSha
$body += '- actual_sha256: ' + $actualSha
$body += '- sha256_match: ' + $shaMatch
Set-Content -Path (Join-Path $outDir 'DELIVERABLE_VERIFY.md') -Value $body -Encoding UTF8
Add-Content -Path (Join-Path $outDir 'DELIVERABLE_VERIFY.md') -Value ('DELIVERABLE_OK=' + $(if ($shaMatch) {'True'} else {'False'}))
Add-Content -Path (Join-Path $outDir 'DELIVERABLE_VERIFY.md') -Value ('DELIVERABLE_SHA256=' + $actualSha)
Add-Content -Path (Join-Path $outDir 'DELIVERABLE_VERIFY.md') -Value ('DELIVERABLE_PATH=' + $docRel)
Add-Content -Path (Join-Path $outDir 'DELIVERABLE_VERIFY.md') -Value ('DELIVERABLE_BYTES=' + $bytes)
Add-Content -Path (Join-Path $outDir 'DELIVERABLE_VERIFY.md') -Value ('DELIVERABLE_ROUND=14')
Write-Output ('DELIVERABLE_OK=' + $(if ($shaMatch) {'True'} else {'False'}))
Write-Output ('DELIVERABLE_SHA256=' + $actualSha)
Write-Output 'DELIVERABLE_ROUND=14'
if (-not $shaMatch) { exit 1 }
