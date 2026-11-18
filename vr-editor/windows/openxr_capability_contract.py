"""Fail-closed offline OpenXR capability report validator for PS VR2 PC review.

Consumes a locally captured *untrusted* diagnostic JSON report; never probes hardware,
starts a runtime, claims Unity compilation, or authorizes commercial measurements.
"""
import argparse
import json
import re
from pathlib import Path

MAX_REPORT_BYTES = 65536
KNOWN_EXTENSIONS = frozenset({
    "XR_KHR_D3D11_enable", "XR_KHR_D3D12_enable",
    "XR_KHR_vulkan_enable", "XR_KHR_vulkan_enable2",
    "XR_KHR_opengl_enable", "XR_EXT_hand_tracking",
})
VERSION = re.compile(r"^[0-9]+\\.[0-9]+\\.[0-9]+$")
RUNTIME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._+()/-]{0,127}$")


class InvalidCapabilityReport(ValueError):
    pass


def validate(report):
    if type(report) is not dict or set(report) != {
        "schema", "runtime_name", "runtime_version", "runtime_active",
        "system_available", "graphics_api", "extensions", "headset_connected",
    }:
        raise InvalidCapabilityReport("invalid report shape")
    if type(report["schema"]) is not int or report["schema"] != 1:
        raise InvalidCapabilityReport("unsupported schema")
    if type(report["runtime_name"]) is not str or not RUNTIME.fullmatch(report["runtime_name"]):
        raise InvalidCapabilityReport("invalid runtime name")
    if type(report["runtime_version"]) is not str or not VERSION.fullmatch(report["runtime_version"]):
        raise InvalidCapabilityReport("invalid runtime version")
    for key in ("runtime_active", "system_available", "headset_connected"):
        if type(report[key]) is not bool:
            raise InvalidCapabilityReport("invalid boolean: " + key)
    if report["graphics_api"] not in ("D3D11", "D3D12", "Vulkan", "OpenGL"):
        raise InvalidCapabilityReport("unsupported graphics API")
    extensions = report["extensions"]
    if type(extensions) is not list or len(extensions) > 256 or any(
        type(x) is not str or not re.fullmatch(r"XR_[A-Za-z0-9_]{1,100}", x)
        for x in extensions
    ) or len(set(extensions)) != len(extensions):
        raise InvalidCapabilityReport("invalid or duplicate extension")
    required = {
        "D3D11": "XR_KHR_D3D11_enable",
        "D3D12": "XR_KHR_D3D12_enable",
        "Vulkan": "XR_KHR_vulkan_enable2",
        "OpenGL": "XR_KHR_opengl_enable",
    }[report["graphics_api"]]
    # This is a diagnostic capability indication, NOT a headset/Unity acceptance.
    blockers = []
    if not report["runtime_active"]:
        blockers.append("openxr_runtime_not_active")
    if not report["system_available"]:
        blockers.append("openxr_system_unavailable")
    if required not in extensions and not (
        report["graphics_api"] == "Vulkan" and "XR_KHR_vulkan_enable" in extensions
    ):
        blockers.append("graphics_binding_extension_missing")
    if not report["headset_connected"]:
        blockers.append("headset_not_reported_connected")
    return {
        "schema": 1,
        "diagnostic_ready": not blockers,
        "blockers": blockers,
        "graphics_api": report["graphics_api"],
        "runtime_name": report["runtime_name"],
        "hardware_verified": False,
        "unity_player_verified": False,
        "production_authorized": False,
    }


def load(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_REPORT_BYTES:
        raise InvalidCapabilityReport("invalid report file")
    try:
        return validate(json.loads(path.read_text(encoding="utf-8")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise InvalidCapabilityReport("invalid JSON") from exc


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("report", type=Path)
    args = p.parse_args()
    try:
        result = load(args.report)
    except (InvalidCapabilityReport, OSError) as exc:
        p.exit(2, f"capability report rejected: {exc}\\n")
    print(json.dumps(result, sort_keys=True, indent=2))
    if not result["diagnostic_ready"]:
        p.exit(1, "OpenXR capability preflight blocked\\n")


if __name__ == "__main__":
    main()
