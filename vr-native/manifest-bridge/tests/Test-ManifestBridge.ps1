# Source-neutral Windows native bridge tests. Zero original PDFs.
$ErrorActionPreference = "Stop"
$project = (Resolve-Path (Join-Path $PSScriptRoot "..\PlanReader.ManifestBridge.csproj")).Path
$fixture = (Resolve-Path (Join-Path $PSScriptRoot "valid-review-scene.json")).Path
& dotnet build $project -c Release --nologo
if ($LASTEXITCODE -ne 0) { throw "Native bridge compilation failed" }
$assembly = Join-Path (Split-Path $project -Parent) "bin\Release\net8.0\PlanReader.ManifestBridge.dll"
function Invoke-Case([object]$scene, [bool]$expectedValid) {
    $temp = Join-Path $env:RUNNER_TEMP ("planreader-manifest-" + [Guid]::NewGuid().ToString("N") + ".json")
    try {
        $scene | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $temp -Encoding utf8
        $output = & dotnet $assembly $temp 2>$null
        $success = $LASTEXITCODE -eq 0
        if ($success -ne $expectedValid) { throw "Unexpected native bridge validation result" }
        if ($success) {
            $parsed = $output | ConvertFrom-Json
            if ($parsed.localEvidenceTrusted -ne $false -or $parsed.measurementAuthorized -ne $false -or $parsed.canEdit -ne $false) { throw "Unsafe authority promotion" }
            if ($parsed.walls[0].renderState -ne "review" -or $parsed.walls[0].locallyAuthenticated -ne $false) { throw "Unsafe local wall promotion" }
        }
    } finally { Remove-Item -LiteralPath $temp -ErrorAction SilentlyContinue }
}
$ok = Get-Content -LiteralPath $fixture -Raw | ConvertFrom-Json
Invoke-Case $ok $true
$wrongSha = Get-Content -LiteralPath $fixture -Raw | ConvertFrom-Json
$wrongSha.scope.sourceSha256 = "not-a-real-sha"
Invoke-Case $wrongSha $false
$wrongAuthority = Get-Content -LiteralPath $fixture -Raw | ConvertFrom-Json
$wrongAuthority.commercialQuantityPublicationAllowed = $true
Invoke-Case $wrongAuthority $false
$wrongRevision = Get-Content -LiteralPath $fixture -Raw | ConvertFrom-Json
$wrongRevision.scope.modelRevision = -1
Invoke-Case $wrongRevision $false
$wrongSurface = Get-Content -LiteralPath $fixture -Raw | ConvertFrom-Json
$wrongSurface | Add-Member -NotePropertyName sourceSurfaces -NotePropertyValue @(@{ surfaceId="forged" })
Invoke-Case $wrongSurface $false
$duplicate = Get-Content -LiteralPath $fixture -Raw | ConvertFrom-Json
$duplicate.objects = @($duplicate.objects[0], $duplicate.objects[0])
Invoke-Case $duplicate $false
Write-Host "Six bounded source-neutral native scene tests passed."
# The final negative fixture intentionally returns exit 2; reset process result.
exit 0
