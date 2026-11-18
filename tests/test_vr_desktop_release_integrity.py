"""Source-neutral negative tests; no private PDFs or Windows device required."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "vr-editor/windows/release_integrity.py"
spec = importlib.util.spec_from_file_location("release_integrity", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ReleaseInventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "web").mkdir()
        (self.root / "PlanReaderDesktop.exe").write_bytes(b"synthetic binary")
        (self.root / "web/index.html").write_text("review-only")

    def test_deterministic_inventory(self):
        self.assertEqual(mod.inventory(self.root), mod.inventory(self.root))
        self.assertEqual(mod.inventory(self.root)["release_type"], "unsigned-review-only")

    def test_detects_tamper(self):
        before = mod.inventory(self.root)
        (self.root / "web/index.html").write_text("modified")
        self.assertNotEqual(before, mod.inventory(self.root))

    def test_rejects_private_pdf(self):
        (self.root / "source.pdf").write_bytes(b"%PDF")
        with self.assertRaises(ValueError):
            mod.inventory(self.root)

    def test_rejects_credentials(self):
        (self.root / ".env.local").write_text("SECRET=abc")
        with self.assertRaises(ValueError):
            mod.inventory(self.root)

    def test_rejects_missing_binary(self):
        (self.root / "PlanReaderDesktop.exe").unlink()
        with self.assertRaises(ValueError):
            mod.inventory(self.root)

    def test_rejects_symlink(self):
        link = self.root / "web/link"
        try:
            link.symlink_to(self.root / "web/index.html")
        except OSError:
            self.skipTest("symlinks unavailable")
        with self.assertRaises(ValueError):
            mod.inventory(self.root)


if __name__ == "__main__":
    unittest.main()
