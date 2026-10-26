"""No missing original/signed path may change type while four-project report writes.

These tests are source-neutral: no private PDF, frozen truth, customer data
or benchmark number is accessed. They exercise the real GPT3 publication
snapshot assertion used both before and after exclusive diagnostic output.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from tools.report_gpt3_four_project_evidence import (
    _assert_four_project_publication_inputs_stable as assert_unchanged,
    _stable_original_digest as witness,
)


def test_unchanged_missing_and_unchanged_regular_paths_remain_acceptable(tmp_path: Path):
    missing = tmp_path / "private-not-provisioned.pdf"
    signed = tmp_path / "source-sealed.json"
    signed.write_bytes(b"already-verified-signed-input")
    digest = witness(signed)
    snapshot = ((missing, None), (signed, digest))
    assert_unchanged(snapshot)
    assert_unchanged(tuple(reversed(snapshot)))
    assert not missing.exists()


@pytest.mark.parametrize("path_type", ["directory", "regular_file", "symlink"])
def test_original_absent_path_that_appears_invalidates_publication(tmp_path: Path, path_type: str):
    missing = tmp_path / "missing-original.pdf"
    snapshot = ((missing, None),)
    assert_unchanged(snapshot)
    if path_type == "directory":
        missing.mkdir()
    elif path_type == "regular_file":
        missing.write_bytes(b"%PDF-new-after-inventory")
    else:
        existing = tmp_path / "elsewhere"
        existing.write_bytes(b"foreign")
        missing.symlink_to(existing)
    with pytest.raises(ValueError, match="four-project input changed"):
        assert_unchanged(snapshot)


@pytest.mark.parametrize("replacement", ["absent", "directory", "new_bytes", "symlink"])
def test_existing_signed_input_replaced_or_modified_fails(tmp_path: Path, replacement: str):
    signed = tmp_path / "source-signed.json"
    signed.write_bytes(b"certified-signed-run")
    prior = witness(signed)
    snapshot = ((signed, prior),)
    assert_unchanged(snapshot)
    signed.unlink()
    if replacement == "directory":
        signed.mkdir()
    elif replacement == "new_bytes":
        signed.write_bytes(b"tampered-signed-run")
    elif replacement == "symlink":
        other = tmp_path / "other-signed.json"
        other.write_bytes(b"certified-signed-run")
        signed.symlink_to(other)
    with pytest.raises(ValueError, match="four-project input changed"):
        assert_unchanged(snapshot)


def test_empty_input_is_not_a_regular_file_and_directory_cannot_hide(tmp_path: Path):
    empty = tmp_path / "missing-map.json"
    snapshot = ((empty, None),)
    assert_unchanged(snapshot)
    empty.mkdir()
    with pytest.raises(ValueError):
        assert_unchanged(snapshot)
    assert empty.is_dir()


def test_input_read_error_fails_closed(tmp_path: Path, monkeypatch):
    from tools import report_gpt3_four_project_evidence as report
    original = tmp_path / "original.pdf"
    original.write_bytes(b"%PDF-protected")
    digest = witness(original)
    def unavailable(_path):
        raise OSError("read unavailable")
    monkeypatch.setattr(report, "_stable_original_digest", unavailable)
    with pytest.raises(ValueError, match="four-project input changed"):
        report._assert_four_project_publication_inputs_stable(((original, digest),))
    assert original.read_bytes() == b"%PDF-protected"


@pytest.mark.parametrize("error_type", [PermissionError, OSError])
@pytest.mark.parametrize("was_present", [False, True])
def test_uninspectable_input_fails_closed_before_and_after_publication(
    tmp_path: Path, monkeypatch, error_type, was_present: bool,
):
    """Python 3.14 pathlib predicates can hide these lstat errors."""
    input_path = tmp_path / "private-source.pdf"
    if was_present:
        input_path.write_bytes(b"%PDF-original-unchanged")
    digest = witness(input_path) if was_present else None
    receipt = ((input_path, digest),)
    assert_unchanged(receipt)
    original_lstat = Path.lstat

    def unavailable(self, *args, **kwargs):
        if self == input_path:
            raise error_type("inaccessible parent or filesystem")
        return original_lstat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", unavailable)
    # This assertion is the exact callback invoked both before publication
    # and by write_new_diagnostic after its exclusive output link.
    for _ in range(2):
        with pytest.raises(ValueError, match="four-project input changed"):
            assert_unchanged(receipt)
    if was_present:
        assert input_path.read_bytes() == b"%PDF-original-unchanged"


@pytest.mark.parametrize("error_type", [PermissionError, OSError])
@pytest.mark.parametrize("was_present", [False, True])
def test_snapshot_rejects_uninspectable_original_or_signed_path(
    tmp_path: Path, monkeypatch, error_type, was_present: bool,
):
    from tools import report_gpt3_four_project_evidence as report

    frozen_root = tmp_path / "frozen"
    frozen_root.mkdir()
    manifest = frozen_root / "manifest.json"
    if was_present:
        manifest.write_bytes(b"existing-frozen-input-unchanged")
    monkeypatch.setattr(report, "FROZEN_ROOT", frozen_root)
    monkeypatch.setattr(report, "load_suite_manifests", lambda _root: [])
    original_lstat = Path.lstat

    def unavailable(self, *args, **kwargs):
        if self == manifest:
            raise error_type("inaccessible parent or filesystem")
        return original_lstat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", unavailable)
    with pytest.raises(ValueError, match="publication input path cannot be inspected"):
        report._snapshot_four_project_publication_inputs(
            source_dir=tmp_path / "originals", sealed_dir=tmp_path / "sealed",
            identity_map_dir=tmp_path / "maps", customer_dir=tmp_path / "customer",
        )
    if was_present:
        assert manifest.read_bytes() == b"existing-frozen-input-unchanged"


def test_dangling_symlink_is_not_a_missing_input(tmp_path: Path):
    from tools import report_gpt3_four_project_evidence as report
    missing = tmp_path / "original.pdf"
    missing.symlink_to(tmp_path / "never-existed.pdf")
    with pytest.raises(ValueError, match="four-project input changed"):
        assert_unchanged(((missing, None),))
    assert report._publication_input_path_kind(missing) == "symlink"


def test_same_bytes_different_inode_cannot_revalidate_signed_customer_or_original(tmp_path: Path):
    """A matching SHA does not make a substituted physical input the original."""
    for filename in ("original.pdf", "sealed.json", "customer_rows.json", "source_manifest.json"):
        original = tmp_path / filename
        original.write_bytes(b"same-content-but-new-physical-input")
        receipt = ((original, witness(original)),)
        assert_unchanged(receipt)
        replacement = tmp_path / ("replacement-" + filename)
        replacement.write_bytes(original.read_bytes())
        replacement.replace(original)
        assert original.read_bytes() == b"same-content-but-new-physical-input"
        with pytest.raises(ValueError, match="four-project input changed"):
            assert_unchanged(receipt)


def test_same_byte_source_replacement_after_exclusive_link_rolls_back_report(
    tmp_path: Path, monkeypatch,
):
    """Exercise the real create-only publication callback, not only its helper."""
    from tools import gpt3_safe_original_report_output as publish

    original = tmp_path / "sealed-source.json"
    original.write_bytes(b"source-neutral-signed-bytes")
    output = tmp_path / "four-project-report.json"
    receipt = ((original, witness(original)),)
    actual_link = publish.os.link
    swapped = False

    def substitute_after_link(staged, destination):
        nonlocal swapped
        actual_link(staged, destination)
        replacement = tmp_path / "same-byte-replacement.json"
        replacement.write_bytes(original.read_bytes())
        replacement.replace(original)
        swapped = True

    monkeypatch.setattr(publish.os, "link", substitute_after_link)
    with pytest.raises(ValueError, match="four-project input changed"):
        publish.write_new_diagnostic(
            output, '{"publication_status":"UNPUBLISHED"}\\n',
            protected_roots=(original,),
            verify_inputs=lambda: assert_unchanged(receipt),
        )
    assert swapped
    assert not output.exists()
    assert original.read_bytes() == b"source-neutral-signed-bytes"
    assert not list(tmp_path.glob(".gpt3-original-report-*.tmp"))


def test_same_inode_stable_witness_accepts_repeated_checks_without_persisting_identity(
    tmp_path: Path,
):
    original = tmp_path / "original.pdf"
    original.write_bytes(b"%PDF-source-neutral-fixture")
    receipt = ((original, witness(original)),)
    assert len(receipt[0][1][0]) == 64
    assert isinstance(receipt[0][1][1], tuple)
    assert_unchanged(receipt)
    assert_unchanged(receipt)
