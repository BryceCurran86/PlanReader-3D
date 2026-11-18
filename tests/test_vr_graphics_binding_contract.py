import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("graphics_binding_contract", Path(__file__).resolve().parents[1] / "vr-editor" / "windows" / "graphics_binding_contract.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

GOOD = dict(platform="windows", graphics_api="D3D11", openxr_graphics_extension="XR_KHR_D3D11_enable", feature_level="11_0", runtime_adapter_luid="00000000ABCDEF01", device_adapter_luid="00000000abcdef01", graphics_requirements_queried=True, device_created=True)


class GraphicsContractTests(unittest.TestCase):
    def test_valid_consistent_report(self):
        self.assertEqual(module.validate(GOOD), [])

    def test_missing_report(self):
        self.assertTrue(module.validate(None))

    def test_missing_field(self):
        for field in GOOD:
            with self.subTest(field=field):
                report = dict(GOOD)
                del report[field]
                self.assertTrue(module.validate(report))

    def test_adapter_mismatch(self):
        self.assertIn("D3D device adapter does not match OpenXR runtime adapter", module.validate({**GOOD, "device_adapter_luid": "0000000000000000"}))

    def test_invalid_luids(self):
        for luid in ("", "0x1234567890abcdef", "../test", 42, "GGGGGGGGGGGGGGGG"):
            with self.subTest(luid=luid):
                self.assertTrue(module.validate({**GOOD, "runtime_adapter_luid": luid}))

    def test_boolean_fail_closed(self):
        for value in (0, 1, "true", None, False):
            with self.subTest(value=value):
                self.assertTrue(module.validate({**GOOD, "device_created": value}))

    def test_wrong_api_or_extension(self):
        for field, value in (("graphics_api", "Vulkan"), ("openxr_graphics_extension", "XR_KHR_vulkan_enable"), ("feature_level", "10_0")):
            self.assertTrue(module.validate({**GOOD, field: value}))


if __name__ == "__main__":
    unittest.main()
