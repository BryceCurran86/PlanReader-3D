#requires -Version 5.1
<#
.SYNOPSIS
Cursor launcher for original PlanReader wall/opening and room-closure replay.
.DESCRIPTION
Forwards to the established private-source diagnostic runner. Maintains one
test/geometry pipeline; does not copy original PDF files or publish quantities.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$Pdf,
  [Parameter(Mandatory = $true)][ValidateRange(0, 2147483646)][int]$PageIndex,
  [Parameter(Mandatory = $true)][string]$OutDir,
  [Parameter(Mandatory = $true)]
  [ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedSha256,
  [string]$Python = 'py',
  [switch]$PrivateDetail
)
$ErrorActionPreference = 'Stop'
$runner = Join-Path $PSScriptRoot 'run_antigravity_wall_closure.ps1'
if (-not (Test-Path -LiteralPath $runner)) {
  throw "Source replay runner not found at $runner"
}
$parameters = @{
  Pdf = $Pdf
  PageIndex = $PageIndex
  OutDir = $OutDir
  Python = $Python
  PrivateDetail = $PrivateDetail
  ExpectedSha256 = $ExpectedSha256
}
& $runner @parameters
if (-not $?) { throw 'Cursor wall closure diagnostic runner failed.' }
