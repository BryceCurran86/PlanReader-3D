"""Q02 source completeness must be determined from original bytes, not a flag."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz
import pytest

from tools.diag_gpt1_source_pdf_package_preflight import check_source_pdf_package


def _pdf(path: Path, pages: int = 2):
    d = fitz.open()
    for index in range(pages):
        page = d.new_page()
        page.insert_text((25, 25), f"source page {index + 1}")
    d.save(path)
    d.close()
    raw = path.read_bytes()
    return {
        "name": path.name,
        "role": "source_architecture",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "page_count": pages,
    }


def _manifest(root: Path, documents: list[dict]):
    path = root / "original-source-manifest.json"
    # Benchmark-like metadata is present but deliberately not used by the
    # preflight; it must not leak quantities or score input.
    path.write_text(json.dumps({
        "project_id": "synthetic-project",
        "status": "INCOMPLETE",
        "source_package_complete": True,
        "source_documents": documents,
        "verified_takeoff_items": [{
            "expected_quantity": 9999,
            "denominator_eligible": True,
        }],
        "reference_takeoff_documents": [{"name": "do-not-open.json"}],
    }))
    return path


def test_two_exact_pdf_bytes_required_for_runtime_complete(tmp_path):
    a = _pdf(tmp_path / "architecture.pdf")
    b = _pdf(tmp_path / "structure.pdf", 3)
    manifest = _manifest(tmp_path, [a, b])
    result = check_source_pdf_package(manifest, tmp_path)
    assert result["actual_source_package_runtime_complete"] is True
    assert result["verified_source_document_count"] == 2
    assert all(d["status"] == "VERIFIED" for d in result["source_documents"])
    assert result["manifest_declares_source_package_complete"] is True
    assert result["rcp_or_metric_or_finish_authority_granted"] is False
    assert result["commercial_quantity_publication_granted"] is False
    assert result["benchmark_score_granted"] is False


def test_manifest_complete_flag_cannot_hide_missing_structural_pdf(tmp_path):
    a = _pdf(tmp_path / "architecture.pdf")
    b = _pdf(tmp_path / "structure.pdf")
    (tmp_path / b["name"]).unlink()
    result = check_source_pdf_package(_manifest(tmp_path, [a, b]), tmp_path)
    assert result["manifest_declares_source_package_complete"] is True
    assert result["actual_source_package_runtime_complete"] is False
    assert result["verified_source_document_count"] == 1
    assert {d["name"]: d["status"] for d in result["source_documents"]} == {
        "architecture.pdf": "VERIFIED",
        "structure.pdf": "MISSING",
    }


def test_same_size_modified_content_does_not_validate_original_sha(tmp_path):
    a = _pdf(tmp_path / "architecture.pdf")
    path = tmp_path / a["name"]
    data = bytearray(path.read_bytes())
    position = len(data) // 2
    data[position] ^= 1
    path.write_bytes(data)
    rows = check_source_pdf_package(
        _manifest(tmp_path, [a]), tmp_path
    )["source_documents"]
    assert rows[0]["status"] == "SHA_MISMATCH"


def test_incorrect_size_or_page_count_denied(tmp_path):
    a = _pdf(tmp_path / "architecture.pdf")
    for key, value, expected in (
        ("size_bytes", a["size_bytes"] + 1, "SIZE_MISMATCH"),
        ("page_count", a["page_count"] + 1, "PAGE_COUNT_MISMATCH"),
    ):
        changed = dict(a, **{key: value})
        result = check_source_pdf_package(
            _manifest(tmp_path, [changed]), tmp_path
        )
        assert result["source_documents"][0]["status"] == expected
        assert not result["actual_source_package_runtime_complete"]


@pytest.mark.parametrize("change", [
    {"name": "../escape.pdf"},
    {"name": "/tmp/escape.pdf"},
    {"name": "folder\\escape.pdf"},
    {"name": "architecture.PDF", "role": ""},
    {"sha256": "NOT_SHA"},
    {"page_count": 0},
    {"size_bytes": True},
    {"page_count": False},
])
def test_untrusted_manifest_entry_raises_before_any_source_promotion(tmp_path, change):
    a = _pdf(tmp_path / "architecture.pdf")
    entry = {**a, **change}
    with pytest.raises(ValueError, match="invalid, unsafe"):
        check_source_pdf_package(_manifest(tmp_path, [entry]), tmp_path)


def test_duplicate_case_insensitive_original_name_rejected(tmp_path):
    a = _pdf(tmp_path / "architecture.pdf")
    b = dict(a, name="ARCHITECTURE.PDF")
    with pytest.raises(ValueError, match="duplicate"):
        check_source_pdf_package(_manifest(tmp_path, [a, b]), tmp_path)


def test_symlink_to_external_source_is_not_accepted(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "external.pdf"
    a = _pdf(outside)
    (root / a["name"]).symlink_to(outside)
    result = check_source_pdf_package(
        _manifest(root, [a]), root
    )
    assert result["source_documents"][0]["status"] == "SOURCE_SYMLINK_UNTRUSTED"
    assert not result["actual_source_package_runtime_complete"]


def test_source_manifest_flags_and_gold_are_not_proof(tmp_path):
    a = _pdf(tmp_path / "architecture.pdf")
    manifest = _manifest(tmp_path, [a])
    d = json.loads(manifest.read_text())
    d["source_package_complete"] = False
    d["verified_takeoff_items"][0]["expected_quantity"] = 100000000
    manifest.write_text(json.dumps(d))
    result = check_source_pdf_package(manifest, tmp_path)
    assert result["actual_source_package_runtime_complete"]
    assert not result["manifest_declares_source_package_complete"]
    assert "expected_quantity" not in json.dumps(result)
