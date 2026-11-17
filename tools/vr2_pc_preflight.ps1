# Local, read-only Windows PS VR2 PC readiness report.
# Does not probe connected device identity, send network requests or read customer PDFs.
[CmdletBinding()]
param([string]$OutputPath)
$ErrorActionPreference = "Stop"
$checks = [System.Collections.Generic.List[object]]::new()
function Add-Check([string]$name, [string]$status, [string]$detail) {
    $checks.Add([pscustomobject]@{ name = $name; status = $status; detail = $detail })
}
function Get-RegisteredValue([string[]]$paths, [string]$propertyName) {
    foreach ($path in $paths) {
        try {
            $item = Get-ItemProperty -LiteralPath $path -Name $propertyName -ErrorAction Stop
            $value = $item.$propertyName
            if ($value -is [string] -and ![string]::IsNullOrWhiteSpace($value)) {
                return $value
            }
        } catch { continue }
    }
    return $null
}
$runningOnWindows = [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform(
    [System.Runtime.InteropServices.OSPlatform]::Windows)
if (!$runningOnWindows) { throw "The PS VR2 PC preflight runs on Windows only." }
$os = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue
$build = [Environment]::OSVersion.Version.Build
$is64 = [Environment]::Is64BitOperatingSystem
$osLabel = if ($os -and $os.Caption) { [string]$os.Caption } else { "Windows (version unavailable)" }
Add-Check "windows_os" $(if ($build -ge 19041 -and $is64) { "check" } else { "needs-review" }) "$osLabel; build $build; 64-bit OS: $is64. Version alone does not prove driver support."

$webViewKeys = @(
    "HKCU:\Software\Microsoft\EdgeUpdate\Clients\{F1E7A18D-B819-490A-B1A7-2D52C733D4C5}",
    "HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F1E7A18D-B819-490A-B1A7-2D52C733D4C5}",
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F1E7A18D-B819-490A-B1A7-2D52C733D4C5}"
)
$webView = Get-RegisteredValue $webViewKeys "pv"
Add-Check "webview2_runtime" $(if ($webView) { "detected" } else { "needs-review" }) $(if ($webView) { "WebView2 runtime version $webView found" } else { "WebView2 runtime registration not found; desktop preview may require Microsoft Edge WebView2 Runtime" })

$openXrKeys = @(
    "HKCU:\SOFTWARE\Khronos\OpenXR\1",
    "HKLM:\SOFTWARE\Khronos\OpenXR\1",
    "HKLM:\SOFTWARE\WOW6432Node\Khronos\OpenXR\1"
)
$openXr = Get-RegisteredValue $openXrKeys "ActiveRuntime"
$openXrName = if ($openXr) { [IO.Path]::GetFileName($openXr) } else { "" }
Add-Check "openxr_runtime" $(if ($openXr) { "detected" } else { "not-yet-verified" }) $(if ($openXr) { "Registered runtime file: $openXrName (not a device/SteamVR approval)" } else { "No active OpenXR runtime detected; configure SteamVR as OpenXR runtime when the headset is available" })

$steam = Get-RegisteredValue @("HKCU:\Software\Valve\Steam", "HKLM:\Software\WOW6432Node\Valve\Steam") "SteamPath"
$steamVr = $false
if ($steam) {
    $steamVr = Test-Path -LiteralPath (Join-Path $steam "steamapps\common\SteamVR")
}
Add-Check "steamvr" $(if ($steamVr) { "detected" } else { "not-yet-verified" }) $(if ($steamVr) { "SteamVR installation directory detected (not runtime or headset proof)" } else { "SteamVR directory not detected in the standard Steam library; other libraries are not searched" })

$adapters = @()
try {
    $adapters = @(Get-CimInstance Win32_VideoController -ErrorAction Stop |
        Select-Object -First 3 -ExpandProperty Name)
} catch { $adapters = @() }
$adapterNames = @($adapters | Where-Object { $_ -is [string] -and $_.Length -gt 0 } | ForEach-Object {
    $_.Substring(0, [Math]::Min(100, $_.Length))
})
Add-Check "graphics_adapter" $(if ($adapterNames.Count -gt 0) { "check" } else { "needs-review" }) $(if ($adapterNames.Count -gt 0) { "Reported GPU(s): " + ($adapterNames -join ", ") + ". Verify VR-capable GPU and physical DisplayPort 1.4 separately." } else { "GPU not identified; inspect graphics adapter manually" })

Add-Check "ps_vr2_adapter" "not-yet-verified" "Physical PS VR2 PC adapter, direct USB 3, DisplayPort 1.4, Bluetooth controllers and headset cannot be validated by this script."
Add-Check "hardware_acceptance" "not-yet-verified" "No native Unity player or actual headset/frame-rate/session acceptance is inferred from installed software."

$report = [ordered]@{
    schema_version = 1
    result = "informational-preflight-only"
    privacy = "local-only; no serial numbers, user names, project files or network requests"
    checks = @($checks.ToArray())
}
$json = $report | ConvertTo-Json -Depth 5
if (![string]::IsNullOrWhiteSpace($OutputPath)) {
    $parent = Split-Path -Path $OutputPath -Parent
    if ($parent -and !(Test-Path -LiteralPath $parent)) {
        throw "Output folder does not exist: $parent"
    }
    Set-Content -LiteralPath $OutputPath -Value $json -Encoding utf8
}
Write-Output $json
