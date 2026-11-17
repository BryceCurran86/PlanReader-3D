"""No-source/no-network Windows PS VR2 readiness contract."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pc_preflight_remains_local_and_non_authoritative():
    source = (ROOT / "tools" / "vr2_pc_preflight.ps1").read_text(encoding="utf-8")
    assert "Get-CimInstance Win32_OperatingSystem" in source
    assert "Get-CimInstance Win32_VideoController" in source
    assert 'Get-RegisteredValue $openXrKeys "ActiveRuntime"' in source
    assert "webview2_runtime" in source
    assert "steamvr" in source
    assert '"not-yet-verified"' in source
    assert '"informational-preflight-only"' in source
    for risky in ("Invoke-WebRequest", "Invoke-RestMethod", "Get-Credential",
                  "Get-PnpDevice", "documents/sources", "benchmarks/frozen_holdout"):
        assert risky not in source


def test_workflow_really_runs_native_windows_report():
    workflow = (ROOT / ".github" / "workflows" / "vr2-pc-preflight.yml").read_text(encoding="utf-8")
    assert "runs-on: windows-2022" in workflow
    assert "vr2_pc_preflight.ps1 -OutputPath" in workflow
    assert '"informational-preflight-only"' in workflow
    assert "permissions:" in workflow
