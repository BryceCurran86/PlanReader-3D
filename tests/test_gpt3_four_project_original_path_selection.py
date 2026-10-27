"""Four-project original path selection must never hide unsafe source candidates.

No private PDFs, frozen truth reads or commercial quantities are needed here.
"""
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import report_gpt3_four_project_evidence as report


def _resolve(root: Path):
    return report._resolve_original_paths(
        root, "project", (SimpleNamespace(name="original.pdf"),)
    )


def test_genuinely_absent_original_stays_unavailable(tmp_path):
    files, conflicts = _resolve(tmp_path)
    assert files == [tmp_path / "original.pdf"]
    assert conflicts == []


@pytest.mark.parametrize("source_kind", ["flat", "scoped"])
def test_one_genuine_regular_original_is_selected(tmp_path, source_kind):
    source = (
        tmp_path / "original.pdf" if source_kind == "flat"
        else tmp_path / "project" / "original.pdf"
    )
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"source-neutral test PDF placeholder")
    files, conflicts = _resolve(tmp_path)
    assert files == [source]
    assert not conflicts


def test_equal_distinct_inodes_keep_existing_scoped_preference(tmp_path):
    scoped = tmp_path / "project" / "original.pdf"
    scoped.parent.mkdir()
    scoped.write_bytes(b"identical invented source bytes")
    (tmp_path / "original.pdf").write_bytes(scoped.read_bytes())
    selected, conflicts = _resolve(tmp_path)
    assert selected == [scoped]
    assert conflicts == []


def test_distinct_source_bytes_conflict_even_with_equal_sizes(tmp_path):
    scoped = tmp_path / "project" / "original.pdf"
    scoped.parent.mkdir()
    scoped.write_bytes(b"abc")
    (tmp_path / "original.pdf").write_bytes(b"abd")
    _, conflicts = _resolve(tmp_path)
    assert conflicts == ["conflicting_flat_and_scoped_original:original.pdf"]


@pytest.mark.parametrize("candidate", ["flat", "scoped"])
@pytest.mark.parametrize("kind", ["symlink", "dangling", "directory"])
def test_present_unsafe_original_never_becomes_missing_or_preferred(
    tmp_path, candidate, kind
):
    good = tmp_path / "original.pdf" if candidate == "scoped" else tmp_path / "project" / "original.pdf"
    good.parent.mkdir(parents=True, exist_ok=True)
    good.write_bytes(b"genuine invented source")
    target = tmp_path / "project" / "original.pdf" if candidate == "scoped" else tmp_path / "original.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    if kind == "directory":
        target.mkdir()
    else:
        try:
            target.symlink_to(good if kind == "symlink" else tmp_path / "missing.pdf")
        except (OSError, NotImplementedError):
            pytest.skip("symlinks unsupported")
    _, conflicts = _resolve(tmp_path)
    assert conflicts == ["unsafe_original_source_path:original.pdf"]


def test_unreadable_source_candidate_fails_closed(monkeypatch, tmp_path):
    original = report._publication_input_path_kind
    def classify(path):
        if path == tmp_path / "project" / "original.pdf":
            raise PermissionError("synthetic access denial")
        return original(path)
    monkeypatch.setattr(report, "_publication_input_path_kind", classify)
    _, conflicts = _resolve(tmp_path)
    assert conflicts == ["unsafe_original_source_path:original.pdf"]


def test_source_inode_change_during_duplicate_hash_fails_closed(monkeypatch, tmp_path):
    scoped = tmp_path / "project" / "original.pdf"
    scoped.parent.mkdir()
    scoped.write_bytes(b"unchanged")
    (tmp_path / "original.pdf").write_bytes(b"unchanged")
    original = report._stable_original_digest
    def unstable(path):
        if path == scoped:
            raise ValueError("synthetic source identity replaced during digest")
        return original(path)
    monkeypatch.setattr(report, "_stable_original_digest", unstable)
    _, conflicts = _resolve(tmp_path)
    assert conflicts == ["unsafe_original_source_path:original.pdf"]


def test_real_four_project_ledger_marks_unsafe_original_as_conflict(tmp_path):
    """Direct ledger consumers must not confuse a supplied symlink with omission."""
    manifest = report.load_suite_manifests(report.FROZEN_ROOT)[0]
    source_document = manifest.source_documents[0]
    originals = tmp_path / "originals"
    unsafe = originals / manifest.project_id / source_document.name
    unsafe.parent.mkdir(parents=True)
    try:
        unsafe.symlink_to(tmp_path / "absent-original.pdf")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unsupported")
    result = report.build_four_project_evidence_ledger(
        source_dir=originals,
        sealed_dir=tmp_path / "sealed",
        identity_map_dir=tmp_path / "identity",
        customer_dir=tmp_path / "customer",
    )
    project = next(
        row for row in result["projects"]
        if row["project_id"] == manifest.project_id
    )
    assert project["first_failing_authority_stage"] == "original_source_path_conflict"
    assert project["publication_status"] == "CONFLICT"
    assert "unsafe_original_source_path:" + source_document.name in project["reason_codes"]
    assert project["missing_original_source_document_count"] == 0
    assert project["source_sha_verified"] is False
    assert result["publication_status"] == "UNPUBLISHED"
    assert result["coverage_accuracy"] is None
