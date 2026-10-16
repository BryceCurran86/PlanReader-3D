"""The owner-side launcher is a harness: it must verify bytes, bound runtime and never leak local paths."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from tools import four_job_windows_launcher as launcher


def _kit(root: Path, *, damage: str | None = None) -> Path:
    docs = []
    for index, project in enumerate(launcher.PROJECTS):
        name = f"doc{index}.pdf"
        payload = f"%PDF synthetic {index}".encode()
        folder = root / "sources" / project
        folder.mkdir(parents=True)
        (folder / name).write_bytes(payload)
        docs.append({"project_id": project, "manifest_name": name,
                     "expected_size_bytes": len(payload),
                     "original_sha256": hashlib.sha256(payload).hexdigest()})
    # The inventory needs ten entries; add six more documents under the first project folders.
    for index in range(4, 10):
        project = launcher.PROJECTS[index % 4]
        name = f"extra{index}.pdf"
        payload = f"%PDF synthetic extra {index}".encode()
        (root / "sources" / project / name).write_bytes(payload)
        docs.append({"project_id": project, "manifest_name": name,
                     "expected_size_bytes": len(payload),
                     "original_sha256": hashlib.sha256(payload).hexdigest()})
    (root / "LOCAL_SOURCE_INVENTORY.json").write_text(json.dumps({
        "benchmark_id": "full_plan_takeoff_reconciliation_v2", "docs": docs}), encoding="utf-8")
    if damage == "missing":
        (root / "sources" / docs[0]["project_id"] / docs[0]["manifest_name"]).unlink()
    elif damage == "changed":
        path = root / "sources" / docs[1]["project_id"] / docs[1]["manifest_name"]
        data = bytearray(path.read_bytes())
        data[-1] ^= 1  # same size, different bytes
        path.write_bytes(bytes(data))
    return root


def test_verify_originals_accepts_exact_bytes_and_writes_a_report(tmp_path):
    kit = _kit(tmp_path / "kit")
    report = tmp_path / "report"
    assert launcher.verify_originals(kit, report) is True
    written = json.loads((report / "SOURCE_SHA_VERIFICATION.json").read_text(encoding="utf-8"))
    assert written["verified_document_count"] == 10 and written["score_granted"] is False


@pytest.mark.parametrize("damage", ["missing", "changed"])
def test_verify_originals_rejects_missing_or_same_size_modified_bytes(tmp_path, damage):
    kit = _kit(tmp_path / "kit", damage=damage)
    assert launcher.verify_originals(kit, tmp_path / "report") is False


def test_verify_originals_requires_exactly_ten_documents(tmp_path):
    kit = _kit(tmp_path / "kit")
    inventory = json.loads((kit / "LOCAL_SOURCE_INVENTORY.json").read_text(encoding="utf-8"))
    inventory["docs"] = inventory["docs"][:9]
    (kit / "LOCAL_SOURCE_INVENTORY.json").write_text(json.dumps(inventory), encoding="utf-8")
    with pytest.raises(ValueError, match="ten original"):
        launcher.verify_originals(kit, tmp_path / "report")


def test_verify_originals_accepts_inventory_with_utf8_bom(tmp_path):
    kit = _kit(tmp_path / "kit")
    path = kit / "LOCAL_SOURCE_INVENTORY.json"
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    assert launcher.verify_originals(kit, tmp_path / "report") is True


def test_output_report_creates_nested_parent(tmp_path):
    target = tmp_path / "a" / "b" / "report.json"
    launcher.output_report(target, {"k": 1})
    assert json.loads(target.read_text(encoding="utf-8")) == {"k": 1}


def test_run_logged_kills_a_process_that_exceeds_its_limit(tmp_path):
    rc, status, _ = launcher.run_logged(
        [sys.executable, "-c", "import time; time.sleep(60)"], tmp_path, tmp_path / "x.log",
        timeout_s=1, poll_s=0.2)
    assert (rc, status) == (None, "TIMEOUT")


def test_run_logged_reports_exit_codes(tmp_path):
    assert launcher.run_logged([sys.executable, "-c", "pass"], tmp_path, tmp_path / "ok.log",
                               poll_s=0.2)[:2] == (0, "COMPLETED")
    rc, status, _ = launcher.run_logged([sys.executable, "-c", "raise SystemExit(3)"], tmp_path,
                                        tmp_path / "bad.log", poll_s=0.2)
    assert (rc, status) == (3, "PROCESS_FAILED")


def test_share_safe_status_removes_the_local_home_path():
    bs = chr(92)
    home = "C:" + bs + "Users" + bs + "someone"
    status = {"output_folder": home + bs + "Documents" + bs + "Run", "n": 1}
    safe = launcher.share_safe(status, home)
    assert "someone" not in json.dumps(safe) and safe["n"] == 1
    assert safe["output_folder"].startswith("<HOME>")
