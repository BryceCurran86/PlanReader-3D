# Fail-closed Windows Authenticode release policy. No signing keys or certificates are stored here.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Installer,
    [ValidateSet('preview','production')][string]$Channel = 'preview',
    [string]$ExpectedSignerThumbprint = ''
)
$ErrorActionPreference = 'Stop'
$resolved = (Resolve-Path -LiteralPath $Installer -ErrorAction Stop).Path
if (-not [IO.File]::Exists($resolved) -or [IO.Path]::GetExtension($resolved).ToLowerInvariant() -ne '.exe') {
    throw 'Release artifact must be an existing .exe file'
}
if ([IO.Path]::GetFileName($resolved) -ne 'PlanReader-VR-Desktop-Preview-Setup.exe' -and $Channel -eq 'preview') {
    throw 'Unexpected preview installer filename'
}
$signature = Get-AuthenticodeSignature -LiteralPath $resolved
if ($null -eq $signature) { throw 'No Authenticode result available' }
$sha256 = (Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash.ToLowerInvariant()
if ($Channel -eq 'preview') {
    if ($signature.Status -ne [System.Management.Automation.SignatureStatus]::NotSigned) {
        throw "Preview channel must remain unsigned (actual: $($signature.Status))"
    }
    [pscustomobject]@{ schema=1; channel='preview'; sha256=$sha256; signed=$false; hardware_verified=$false } | ConvertTo-Json -Compress
    exit 0
}
if ($ExpectedSignerThumbprint -notmatch '^[A-Fa-f0-9]{40}$') {
    throw 'Production requires an explicit 40-hex-character trusted signer thumbprint'
}
if ($signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid) {
    throw "Production requires a valid trusted Authenticode signature (actual: $($signature.Status))"
}
if ($null -eq $signature.SignerCertificate) { throw 'Production signer certificate missing' }
$actual = ($signature.SignerCertificate.Thumbprint -replace '\s','').ToUpperInvariant()
if ($actual -ne $ExpectedSignerThumbprint.ToUpperInvariant()) { throw 'Signer thumbprint mismatch' }
[pscustomobject]@{ schema=1; channel='production'; sha256=$sha256; signed=$true; signer_thumbprint=$actual; hardware_verified=$false } | ConvertTo-Json -Compress
