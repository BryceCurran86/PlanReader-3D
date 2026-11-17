"""Ensure Windows installer smoke cannot run on the owner's real computer."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_installer_lifecycle_is_ephemeral_and_refuses_source_pdfs():
    src = (ROOT / "vr-editor" / "windows" / "Test-InstalledViewer.ps1").read_text(encoding="utf-8")
    assert "$env:RUNNER_TEMP" in src
    assert "ephemeral GitHub Actions Windows runner" in src
    assert "StartsWith" in src and "Refusing a non-temporary" in src
    assert 'Filter "*.pdf"' in src
    assert 'unins000.exe' in src
    assert 'PlanReaderDesktop.exe' in src
    assert 'web\\index.html' in src
    assert '"/VERYSILENT"' in src


def test_lifecycle_ci_is_windows_only_and_requires_real_installer():
    src = (ROOT / ".github" / "workflows" / "vr-desktop-install-smoke.yml").read_text(encoding="utf-8")
    assert "windows-2022" in src
    assert "Build-Desktop.ps1" in src
    assert "Test-InstalledViewer.ps1 -InstallerPath" in src
    assert "permissions:" in src
