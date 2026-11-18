# Review-only Windows packaging; never includes PDFs or customer data.
[CmdletBinding()]
param([switch]$SkipInstaller)
$ErrorActionPreference = "Stop"
$editor = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$dist = Join-Path $editor "dist"
$out = Join-Path $PSScriptRoot "out"
$publish = Join-Path $out "publish"
Push-Location $editor
try {
    & npm ci --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }
    & npm test
    if ($LASTEXITCODE -ne 0) { throw "viewer tests failed" }
    & npm run build -- --base=./
    if ($LASTEXITCODE -ne 0) { throw "viewer build failed" }
}
finally { Pop-Location }
if (!(Test-Path (Join-Path $dist "index.html"))) { throw "Missing viewer dist/index.html" }
if (Test-Path $publish) { Remove-Item $publish -Recurse -Force }
& dotnet publish (Join-Path $PSScriptRoot "PlanReaderDesktop.csproj") -c Release -r win-x64 --self-contained true -o $publish /p:PublishSingleFile=false
if ($LASTEXITCODE -ne 0) { throw "Windows host publish failed" }
$web = Join-Path $publish "web"
New-Item $web -ItemType Directory -Force | Out-Null
Copy-Item (Join-Path $dist "*") $web -Recurse -Force
if (!(Test-Path (Join-Path $publish "PlanReaderDesktop.exe"))) { throw "Missing desktop executable" }
if (!(Test-Path (Join-Path $web "index.html"))) { throw "Missing embedded viewer" }
# Fail closed before packaging; the inventory stays outside the installed tree.
$integrity = Join-Path $PSScriptRoot "release_integrity.py"
$inventory = Join-Path $out "desktop-release-inventory.json"
& python $integrity create $publish $inventory
if ($LASTEXITCODE -ne 0) { throw "Desktop release inventory creation failed" }
& python $integrity verify $publish $inventory
if ($LASTEXITCODE -ne 0) { throw "Desktop release inventory verification failed" }
if (!$SkipInstaller) {
    $inno = Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::ProgramFilesX86)) "Inno Setup 6\ISCC.exe"
    if (!(Test-Path $inno)) { throw "Install Inno Setup 6 before building the installer" }
    & $inno (Join-Path $PSScriptRoot "PlanReaderDesktop.iss")
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
    $installer = Join-Path $out "installer\PlanReader-VR-Desktop-Preview-Setup.exe"
    if (!(Test-Path $installer)) { throw "Installer output missing" }
    Write-Host "Built Windows installer at $installer"
} else { Write-Host "Built Windows desktop executable at $publish" }
