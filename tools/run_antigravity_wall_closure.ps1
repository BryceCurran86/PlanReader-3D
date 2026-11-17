#requires -Version 5.1
<#
.SYNOPSIS
Run AntiGravity's read-only PlanReader wall/opening/footprint diagnostics.
.DESCRIPTION
Executes focused public regressions and local source-bound tracing against one
PRIVATE original PDF. No PDF is uploaded, copied into Git or used as benchmark
truth. Diagnostics are noncommercial and never issue measured quantities.
.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\run_antigravity_wall_closure.ps1 -Pdf "C:\private\Acacia.pdf" -PageIndex 1 -OutDir "C:\private\wall-closure-replays" -ExpectedSha256 "<64 hex SHA>"
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Pdf,
  [Parameter(Mandatory=$true)][ValidateRange(0,2147483646)][int]$PageIndex,
  [Parameter(Mandatory=$true)][string]$OutDir,
  [string]$ExpectedSha256,
  [string]$Python = 'py',
  [switch]$PrivateDetail
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$source = (Resolve-Path -LiteralPath $Pdf -ErrorAction Stop).Path
$dest = [System.IO.Path]::GetFullPath($OutDir)
$repoRoot = $repo.TrimEnd([char[]]'\/') + [System.IO.Path]::DirectorySeparatorChar
if ($source.StartsWith($repoRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
    $dest.StartsWith($repoRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
    $dest.TrimEnd([char[]]'\/').Equals($repo, [System.StringComparison]::OrdinalIgnoreCase)) {
  throw 'Private PDF and diagnostic output must be OUTSIDE the public repository checkout.'
}
if ($ExpectedSha256 -and $ExpectedSha256 -notmatch '^[0-9a-fA-F]{64}$') {
  throw 'ExpectedSha256 must be 64 hexadecimal characters.'
}
$sha = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ExpectedSha256 -and $sha -ne $ExpectedSha256.ToLowerInvariant()) {
  throw "Original PDF SHA mismatch. Expected $ExpectedSha256, found $sha. No replay run."
}
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMdd_HHmmss_fff')
$runDir = Join-Path $dest "antigravity_wall_closure_$stamp"
New-Item -ItemType Directory -Path $runDir -Force | Out-Null

function Invoke-Step([string]$label, [string[]]$argsList) {
  Write-Host "==> $label"
  & $Python @argsList
  if ($LASTEXITCODE -ne 0) { throw "$label failed (exit $LASTEXITCODE)." }
}
Push-Location $repo
try {
  # Run focused source-neutral regressions before private replay.
  $testArgs = @('-3.13','-m','pytest','-q',
    'tests/test_structural_room_region_shadow.py',
    'tests/test_source_room_boundary_repair_shadow.py',
    'tests/test_external_footprint_first_trace.py',
    'tests/test_source_native_exterior_edge_path_ownership.py')
  # #4445 may still be in review and therefore absent from a main checkout.
  # Run the regression whenever it is present; report this explicitly.
  $newRegression = 'tests/test_source_wall_gap_arbitration_4443.py'
  $hasNewRegression = Test-Path -LiteralPath $newRegression
  if ($hasNewRegression) { $testArgs += $newRegression }
  else { Write-Warning 'PR #4445 regression file not present: checkout its branch or merge it before final acceptance.' }
  Invoke-Step 'Focused regression tests' $testArgs
  $footDir = Join-Path $runDir 'footprint'
  $ownerDir = Join-Path $runDir 'native_ownership'
  New-Item -ItemType Directory -Path $footDir,$ownerDir | Out-Null
  Invoke-Step 'Source-first footprint and doorway topology (0-based page)' @(
    '-3.13','tools/run_original_footprint_first.py',
    '--pdf',$source,'--page',"$PageIndex",'--out-dir',$footDir)
  Invoke-Step 'Native exterior path owners (0-based page)' @(
    '-3.13','tools/run_native_exterior_path_ownership.py',
    '--pdf',$source,'--page',"$PageIndex",'--out-dir',$ownerDir)
  $overlayArgs = @('-3.13','-m','tools.diag_structural_room_region_overlay',
    '--pdf',$source,'--page',"$($PageIndex+1)",
    '--png',(Join-Path $runDir 'room_regions.png'),
    '--json',(Join-Path $runDir 'room_regions.json'))
  if ($PrivateDetail) { $overlayArgs += '--private-detail' }
  Invoke-Step 'Structural wall/opening/room overlay (1-based page)' $overlayArgs
  $manifest = [ordered]@{
    source_sha256=$sha
    page_index_0based=$PageIndex
    run_folder=$runDir
    focused_tests='passed'
    pr_4445_regressions_executed=$hasNewRegression
    diagnostics='completed; candidates only, no commercial authority'
    original_pdf_copied=$false
    public_repo_modified=$false
    full_ci_required=$true
    manual_original_overlay_validation_required=$true
  }
  $manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $runDir 'manifest.json') -Encoding UTF8
  Write-Host "Private replay diagnostics: $runDir"
  Write-Host 'Review false exterior protrusions, source wall ids, genuine doorway chord hosts, and each room ring. This runner does not certify customer measurement.'
} finally {
  Pop-Location
}
