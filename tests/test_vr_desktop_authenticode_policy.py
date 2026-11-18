"""Static security contract tests for the Windows-only Authenticode policy.

Actual signature verification is performed by PowerShell on Windows, not mocked here.
"""
from pathlib import Path

POLICY = Path(__file__).resolve().parents[1] / "vr-editor/windows/Verify-ReleaseSignature.ps1"
BUILD = Path(__file__).resolve().parents[1] / "vr-editor/windows/Build-Desktop.ps1"


def test_policy_fail_closed_for_production():
    source = POLICY.read_text(encoding="utf-8")
    assert "Get-AuthenticodeSignature" in source
    assert "SignatureStatus]::Valid" in source
    assert "SignerCertificate.Thumbprint" in source
    assert "Signer thumbprint mismatch" in source
    assert "^[A-Fa-f0-9]{40}$" in source


def test_preview_must_remain_unsigned():
    source = POLICY.read_text(encoding="utf-8")
    assert "SignatureStatus]::NotSigned" in source
    assert "Preview channel must remain unsigned" in source
    assert "hardware_verified=$false" in source


def test_no_embedded_signing_material_or_automatic_signing():
    source = POLICY.read_text(encoding="utf-8")
    assert "signtool sign" not in source.lower()
    assert "ConvertTo-SecureString" not in source
    assert "Get-FileHash" in source
    assert "Get-AuthenticodeSignature" in source
    assert "Get-AuthenticodeSignature" not in BUILD.read_text(encoding="utf-8")
