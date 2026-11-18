"""Source-neutral OpenXR report contract tests; no device required."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "vr-editor/windows/openxr_capability_contract.py"
spec = importlib.util.spec_from_file_location("openxr_contract", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class OpenXRContractTests(unittest.TestCase):
    def setUp(self):
        self.good = dict(
            schema=1, runtime_name="SteamVR", runtime_version="2.0.1",
            runtime_active=True, system_available=True, graphics_api="D3D11",
            extensions=["XR_KHR_D3D11_enable"], headset_connected=True,
        )

    def test_diagnostic_never_hardware_acceptance(self):
        result = mod.validate(self.good)
        self.assertTrue(result["diagnostic_ready"])
        self.assertFalse(result["hardware_verified"])
        self.assertFalse(result["unity_player_verified"])
        self.assertFalse(result["production_authorized"])

    def test_missing_binding_blocks(self):
        self.good["extensions"] = []
        self.assertIn("graphics_binding_extension_missing", mod.validate(self.good)["blockers"])

    def test_inactive_runtime_blocks(self):
        self.good["runtime_active"] = False
        self.assertIn("openxr_runtime_not_active", mod.validate(self.good)["blockers"])

    def test_unavailable_system_blocks(self):
        self.good["system_available"] = False
        self.assertIn("openxr_system_unavailable", mod.validate(self.good)["blockers"])

    def test_unconnected_headset_blocks(self):
        self.good["headset_connected"] = False
        self.assertIn("headset_not_reported_connected", mod.validate(self.good)["blockers"])

    def test_vulkan_legacy_binding_supported(self):
        self.good["graphics_api"] = "Vulkan"
        self.good["extensions"] = ["XR_KHR_vulkan_enable"]
        self.assertTrue(mod.validate(self.good)["diagnostic_ready"])

    def test_unknown_graphics_rejected(self):
        self.good["graphics_api"] = "Metal"
        with self.assertRaises(mod.InvalidCapabilityReport):
            mod.validate(self.good)

    def test_boolean_spoof_rejected(self):
        self.good["runtime_active"] = 1
        with self.assertRaises(mod.InvalidCapabilityReport):
            mod.validate(self.good)

    def test_duplicate_extensions_rejected(self):
        self.good["extensions"] *= 2
        with self.assertRaises(mod.InvalidCapabilityReport):
            mod.validate(self.good)

    def test_unknown_field_rejected(self):
        self.good["customer_quantity"] = 12
        with self.assertRaises(mod.InvalidCapabilityReport):
            mod.validate(self.good)

    def test_file_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "report.json"
            path.write_text(json.dumps(self.good), encoding="utf-8")
            self.assertTrue(mod.load(path)["diagnostic_ready"])

    def test_oversized_report_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "report.json"
            path.write_bytes(b" " * (mod.MAX_REPORT_BYTES + 1))
            with self.assertRaises(mod.InvalidCapabilityReport):
                mod.load(path)


if __name__ == "__main__":
    unittest.main()
