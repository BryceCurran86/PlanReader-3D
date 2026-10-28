"""Original-only scorer must reject path aliases before granting source SHA authority."""
import hashlib
from pathlib import Path

import pytest

from tools import run_gpt3_original_byte_gated_exact_project as scorer


def _manifest(data=b"synthetic original PDF bytes"):
    return {"source_documents": [{
        "name": "original.pdf", "sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
    }]}


def _gate(source, *, data=b"synthetic original PDF bytes"):
    return scorer._original_sha_gate(_manifest(data), [source])


def test_real_regular_original_sha_and_size_keep_exact_positive(tmp_path):
    source = tmp_path / "original.pdf"
    data = b"synthetic original PDF bytes"
    source.write_bytes(data)
    accepted, reasons, hashes = _gate(source)
    assert accepted is True
    assert reasons == []
    assert hashes == [hashlib.sha256(data).hexdigest()]


def test_absent_original_is_distinct_from_present_unsafe_source(tmp_path):
    ok, reasons, hashes = _gate(tmp_path / "original.pdf")
    assert ok is False and reasons == ["original_source_missing:original.pdf"]
    assert hashes == []


@pytest.mark.parametrize("kind", ["symlink", "dangling", "directory"])
def test_present_nonregular_source_never_authenticates_original_sha(tmp_path, kind):
    source = tmp_path / "original.pdf"
    if kind == "directory":
        source.mkdir()
    else:
        target = tmp_path / ("actual.pdf" if kind == "symlink" else "absent.pdf")
        if kind == "symlink":
            target.write_bytes(b"synthetic original PDF bytes")
        try:
            source.symlink_to(target)
        except (OSError, NotImplementedError):
            pytest.skip("symlinks unsupported")
    accepted, reasons, hashes = _gate(source)
    assert accepted is False and reasons == ["original_source_unreadable:original.pdf"]
    assert hashes == []


def test_genuine_regular_wrong_size_rejected_from_same_descriptor(tmp_path):
    source = tmp_path / "original.pdf"
    source.write_bytes(b"synthetic original PDF bytes plus extra")
    accepted, reasons, hashes = _gate(source)
    assert accepted is False and reasons == ["original_source_size_mismatch:original.pdf"]
    assert hashes == []


def test_genuine_regular_wrong_sha_rejected(tmp_path):
    source = tmp_path / "original.pdf"
    data = b"different data matching size"
    source.write_bytes(data)
    accepted, reasons, hashes = _gate(source, data=b"x" * len(data))
    assert accepted is False and reasons == ["original_source_sha_mismatch:original.pdf"]
    assert hashes == []


def test_source_permission_or_namespace_inspection_failure_is_not_absent(
    tmp_path, monkeypatch
):
    source = tmp_path / "original.pdf"
    source.write_bytes(b"synthetic original PDF bytes")
    def denied(_):
        raise ValueError("synthetic lstat permission rejection")
    monkeypatch.setattr(scorer, "_original_source_path_kind", denied)
    accepted, reasons, hashes = _gate(source)
    assert accepted is False and reasons == ["original_source_unreadable:original.pdf"]
    assert hashes == []


def test_inode_swap_during_checksum_cannot_issue_matching_sha(tmp_path, monkeypatch):
    source = tmp_path / "original.pdf"
    source.write_bytes(b"synthetic original PDF bytes")
    def raced(_):
        raise ValueError("synthetic same-byte inode replacement")
    monkeypatch.setattr(scorer, "_stable_original_digest", raced)
    accepted, reasons, hashes = _gate(source)
    assert accepted is False and reasons == ["original_source_unreadable:original.pdf"]
    assert hashes == []


def test_manifest_shape_veto_precedes_any_source_file_read(tmp_path, monkeypatch):
    source = tmp_path / "original.pdf"
    source.write_bytes(b"synthetic original PDF bytes")
    def forbidden(_):
        raise AssertionError("source accessed before malformed pin rejected")
    monkeypatch.setattr(scorer, "_original_source_path_kind", forbidden)
    bad = _manifest()
    bad["source_documents"][0]["sha256"] = "incorrect"
    assert scorer._original_sha_gate(bad, [source]) == (
        False, ["source_manifest_document_universe_invalid"], [],
    )
