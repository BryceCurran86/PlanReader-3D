"""Offline release receipt negative tests; synthetic bytes only."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "vr-editor/windows/release_receipt.py"
spec = importlib.util.spec_from_file_location("release_receipt", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.installer = root / mod.INSTALLER_NAME
        self.installer.write_bytes(b"synthetic unsigned installer")
        self.inventory = root / "inventory.json"
        self.data = {"schema": 1, "release_type": "unsigned-review-only", "files": [
            {"path": "PlanReaderDesktop.exe", "bytes": 5, "sha256": "a" * 64},
            {"path": "web/index.html", "bytes": 6, "sha256": "b" * 64}]}
        self.save()

    def save(self):
        self.inventory.write_text(json.dumps(self.data), encoding="utf-8")

    def test_deterministic_and_never_trusted(self):
        result = mod.receipt(self.installer, self.inventory)
        self.assertEqual(result, mod.receipt(self.installer, self.inventory))
        for key in ("trusted_attestation", "production_authorized", "hardware_verified", "unity_player_verified", "signed"):
            self.assertFalse(result[key])

    def test_installer_tamper_changes_receipt(self):
        before = mod.receipt(self.installer, self.inventory)
        self.installer.write_bytes(b"changed")
        self.assertNotEqual(before["installer_sha256"], mod.receipt(self.installer, self.inventory)["installer_sha256"])

    def test_inventory_tamper_changes_receipt(self):
        before = mod.receipt(self.installer, self.inventory)
        self.data["files"][0]["bytes"] = 10
        self.save()
        self.assertNotEqual(before["inventory_sha256"], mod.receipt(self.installer, self.inventory)["inventory_sha256"])

    def test_reject_production_inventory(self):
        self.data["release_type"] = "production"
        self.save()
        with self.assertRaises(ValueError):
            mod.receipt(self.installer, self.inventory)

    def test_reject_duplicate_paths(self):
        self.data["files"].append(self.data["files"][0])
        self.save()
        with self.assertRaises(ValueError):
            mod.receipt(self.installer, self.inventory)

    def test_reject_traversal(self):
        self.data["files"][0]["path"] = "../secret"
        self.save()
        with self.assertRaises(ValueError):
            mod.receipt(self.installer, self.inventory)

    def test_reject_boolean_size(self):
        self.data["files"][0]["bytes"] = True
        self.save()
        with self.assertRaises(ValueError):
            mod.receipt(self.installer, self.inventory)

    def test_reject_symlink(self):
        link = self.inventory.parent / "linked.json"
        try:
            link.symlink_to(self.inventory)
        except OSError:
            self.skipTest("symlinks unavailable")
        with self.assertRaises(ValueError):
            mod.receipt(self.installer, link)

if __name__ == "__main__":
    unittest.main()
