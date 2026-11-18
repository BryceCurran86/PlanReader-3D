"""Ensure the actual Windows packaging path enforces offline inventory checks."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_packaging_creates_and_verifies_inventory_before_inno():
    script = (ROOT / "vr-editor/windows/Build-Desktop.ps1").read_text(encoding="utf-8")
    assert 'release_integrity.py' in script
    assert 'desktop-release-inventory.json' in script
    assert script.index('& python $integrity create') < script.index('& python $integrity verify')
    assert script.index('& python $integrity verify') < script.index('& $inno')
    assert 'Desktop release inventory creation failed' in script
    assert 'Desktop release inventory verification failed' in script


def test_windows_artifact_contains_inventory_and_checks_payload():
    workflow = (ROOT / ".github/workflows/vr-desktop-windows.yml").read_text(encoding="utf-8")
    assert 'python vr-editor/windows/release_integrity.py verify' in workflow
    assert 'vr-editor/windows/out/desktop-release-inventory.json' in workflow
    assert 'vr-editor/windows/out/installer/PlanReader-VR-Desktop-Preview-Setup.exe' in workflow
    assert 'if ($LASTEXITCODE -ne 0)' in workflow
