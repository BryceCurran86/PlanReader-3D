# Non-destructive GitHub Windows runner installer lifecycle test.
# The target MUST remain beneath RUNNER_TEMP. Never execute on a customer PC.
[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$InstallerPath)
$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) {
    throw "This test may only run inside an ephemeral GitHub Actions Windows runner"
}
$runnerTemp = [IO.Path]::GetFullPath($env:RUNNER_TEMP)
$installer = [IO.Path]::GetFullPath($InstallerPath)
if (!(Test-Path -LiteralPath $installer)) { throw "Installer not found" }
$target = Join-Path $runnerTemp ("PlanReaderVRDesktopCi-" + [guid]::NewGuid().ToString("N"))
$target = [IO.Path]::GetFullPath($target)
if (!$target.StartsWith(($runnerTemp.TrimEnd('\') + '\'), [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing a non-temporary install directory"
}
$uninstaller = Join-Path $target "unins000.exe"
try {
    $install = Start-Process -FilePath $installer -ArgumentList @(
        "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/DIR=$target"
    ) -Wait -PassThru
    if ($install.ExitCode -ne 0) { throw "Inno install returned $($install.ExitCode)" }
    $exe = Join-Path $target "PlanReaderDesktop.exe"
    $index = Join-Path $target "web\index.html"
    if (!(Test-Path -LiteralPath $exe)) { throw "Installed executable is missing" }
    if (!(Test-Path -LiteralPath $index)) { throw "Installed viewer index is missing" }
    $bundle = @(Get-ChildItem -LiteralPath (Join-Path $target "web\assets") -Filter "*.js" -File)
    if ($bundle.Count -lt 1) { throw "No compiled JavaScript bundle installed" }
    $privateDocuments = @(Get-ChildItem -LiteralPath $target -Filter "*.pdf" -Recurse -File)
    if ($privateDocuments.Count -gt 0) { throw "Refusing package containing PDF documents" }
    if (!(Test-Path -LiteralPath $uninstaller)) { throw "Inno uninstaller missing" }
    Write-Host "Installed exe, static viewer and JS bundle; no PDF files detected."
    $uninstall = Start-Process -FilePath $uninstaller -ArgumentList @(
        "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"
    ) -Wait -PassThru
    if ($uninstall.ExitCode -ne 0) { throw "Inno uninstall returned $($uninstall.ExitCode)" }
    if (Test-Path -LiteralPath $exe) { throw "Executable remains after uninstall" }
    Write-Host "Inno uninstall removed the executable."
}
finally {
    # Test-generated disposable path only; do not delete any caller-owned directory.
    if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Force -Recurse }
}
