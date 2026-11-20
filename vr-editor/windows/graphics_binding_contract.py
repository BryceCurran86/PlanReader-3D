"""Offline, fail-closed Windows D3D11/OpenXR graphics binding report validator.

Report consistency is not physical hardware, Unity 6, or headset acceptance.
"""
import argparse
import json
import re
from pathlib import Path

_LUID = re.compile(r"^[0-9a-fA-F]{16}$")
_FEATURES = {"11_0", "11_1", "12_0", "12_1", "12_2"}


def validate(report):
    errors = []
    if not isinstance(report, dict):
        return ["report must be an object"]
    if report.get("platform") != "windows":
        errors.append("platform must be windows")
    if report.get("graphics_api") != "D3D11":
        errors.append("graphics_api must be D3D11")
    if report.get("openxr_graphics_extension") != "XR_KHR_D3D11_enable":
        errors.append("XR_KHR_D3D11_enable is required")
    if not isinstance(report.get("feature_level"), str) or report["feature_level"] not in _FEATURES:
        errors.append("feature_level must be a supported D3D feature level")
    runtime = report.get("runtime_adapter_luid")
    device = report.get("device_adapter_luid")
    if not isinstance(runtime, str) or not _LUID.fullmatch(runtime):
        errors.append("runtime_adapter_luid must be 16 hex characters")
    if not isinstance(device, str) or not _LUID.fullmatch(device):
        errors.append("device_adapter_luid must be 16 hex characters")
    if isinstance(runtime, str) and isinstance(device, str) and _LUID.fullmatch(runtime) and _LUID.fullmatch(device) and runtime.lower() != device.lower():
        errors.append("D3D device adapter does not match OpenXR runtime adapter")
    if type(report.get("graphics_requirements_queried")) is not bool or not report["graphics_requirements_queried"]:
        errors.append("graphics requirements query must be positively recorded")
    if type(report.get("device_created")) is not bool or not report["device_created"]:
        errors.append("D3D device creation must be positively recorded")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.report.read_text(encoding="utf-8"))
        errors = validate(data)
    except (OSError, UnicodeError, ValueError) as exc:
        errors = [f"unreadable or invalid JSON report: {exc.__class__.__name__}"]
    print(json.dumps({"status": "PASS" if not errors else "ABSTAIN", "errors": errors}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
