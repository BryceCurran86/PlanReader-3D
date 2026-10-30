"""Source-neutral frozen V2 integrity negatives for present-but-unsafe originals.

Never reads, copies or publishes private customer PDFs or frozen expected BOQs.
"""
from __future__ import annotations

from hashlib import sha256
import importlib.util
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


_REPO = Path(__file__).resolve().parents[1]
_BYTES = b"synthetic source payload; no private drawing"


def _guard():
    # The tests/benchmarks package can shadow the repository benchmark package.
    stash = {
        name: sys.modules.pop(name)
        for name in list(sys.modules)
        if name == "benchmarks" or name.startswith("benchmarks.")
    }
    sys.path.insert(0, str(_REPO))
    try:
        spec = importlib.util.spec_from_file_location(
            "_gpt3_frozen_source_presence_guard",
            _REPO / "scripts" / "check_full_plan_v2_integrity.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(_REPO))
        for name in list(sys.modules):
            if name == "benchmarks" or name.startswith("benchmarks."):
                del sys.modules[name]
        sys.modules.update(stash)
    return module


def _manifest():
    return SimpleNamespace(
        project_id="synthetic_project",
        source_documents=(
            SimpleNamespace(
                name="source.pdf",
                size_bytes=len(_BYTES),
                sha256=sha256(_BYTES).hexdigest(),
            ),
        ),
    )


def _failures(guard, root):
    return guard.source_document_failures((_manifest(),), root)


def test_missing_private_original_is_only_permitted_absence(tmp_path):
    guard = _guard()
    assert _failures(guard, tmp_path) == []
    (tmp_path / "source.pdf").write_bytes(_BYTES)
    assert _failures(guard, tmp_path) == []


def test_present_source_wrong_sha_and_size_still_rejected(tmp_path):
    guard = _guard()
    source = tmp_path / "source.pdf"
    source.write_bytes(b"X" * len(_BYTES))
    assert any("SHA mismatch" in failure for failure in _failures(guard, tmp_path))
    source.write_bytes(_BYTES + b"X")
    failures = _failures(guard, tmp_path)
    assert any("SHA mismatch" in failure for failure in failures)
    assert any("size mismatch" in failure for failure in failures)


def test_symlink_to_byte_exact_original_cannot_be_accepted(tmp_path):
    guard = _guard()
    target = tmp_path / "other.pdf"
    target.write_bytes(_BYTES)
    try:
        (tmp_path / "source.pdf").symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not supported")
    assert any("not a regular file" in f for f in _failures(guard, tmp_path))


def test_dangling_symlink_is_not_a_missing_original(tmp_path):
    guard = _guard()
    try:
        (tmp_path / "source.pdf").symlink_to(tmp_path / "absent.pdf")
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not supported")
    assert any("not a regular file" in f for f in _failures(guard, tmp_path))


def test_directory_masquerading_as_source_fails_closed(tmp_path):
    guard = _guard()
    (tmp_path / "source.pdf").mkdir()
    assert any("not a regular file" in f for f in _failures(guard, tmp_path))


def test_inaccessible_source_metadata_is_not_missing(tmp_path, monkeypatch):
    guard = _guard()
    source = tmp_path / "source.pdf"
    source.write_bytes(_BYTES)
    original_lstat = Path.lstat

    def inaccessible(path, *args, **kwargs):
        if path == source:
            raise PermissionError("synthetic access denied")
        return original_lstat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", inaccessible)
    assert any("cannot be inspected" in f for f in _failures(guard, tmp_path))


def test_inaccessible_descriptor_is_not_missing(tmp_path, monkeypatch):
    guard = _guard()
    source = tmp_path / "source.pdf"
    source.write_bytes(_BYTES)
    original_open = os.open

    def inaccessible(path, flags, *args, **kwargs):
        if Path(path) == source:
            raise PermissionError("synthetic access denied")
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(guard.os, "open", inaccessible)
    assert any("inaccessible" in f for f in _failures(guard, tmp_path))


def test_same_byte_inode_replacement_before_open_is_rejected(tmp_path, monkeypatch):
    guard = _guard()
    source = tmp_path / "source.pdf"
    source.write_bytes(_BYTES)
    original_open = os.open
    swapped = False

    def replace_at_open(path, flags, *args, **kwargs):
        nonlocal swapped
        if Path(path) == source and not swapped:
            swapped = True
            replacement = tmp_path / "replacement"
            replacement.write_bytes(_BYTES)
            os.replace(replacement, source)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(guard.os, "open", replace_at_open)
    assert any("changed" in f for f in _failures(guard, tmp_path))
    assert swapped


def test_same_byte_inode_replacement_after_read_is_rejected(tmp_path, monkeypatch):
    guard = _guard()
    source = tmp_path / "source.pdf"
    source.write_bytes(_BYTES)
    original_lstat = Path.lstat
    inspected = 0

    def replace_after_read(path, *args, **kwargs):
        nonlocal inspected
        if path == source:
            inspected += 1
            if inspected == 2:
                replacement = tmp_path / "replacement"
                replacement.write_bytes(_BYTES)
                os.replace(replacement, source)
        return original_lstat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", replace_after_read)
    assert any("changed" in f for f in _failures(guard, tmp_path))
    assert inspected == 2


def test_disappearance_after_initial_stat_is_not_permitted_absence(tmp_path, monkeypatch):
    guard = _guard()
    source = tmp_path / "source.pdf"
    source.write_bytes(_BYTES)
    original_open = os.open

    def disappear_at_open(path, flags, *args, **kwargs):
        if Path(path) == source:
            source.unlink()
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(guard.os, "open", disappear_at_open)
    assert any("changed or became inaccessible" in f for f in _failures(guard, tmp_path))
