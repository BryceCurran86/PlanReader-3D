"""Source-neutral frozen V2 reference-takeoff physical-identity regressions.

Uses synthetic bytes only; never opens private originals or frozen gold files.
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
_BYTES = b"synthetic reference-takeoff payload; no benchmark truth"


def _guard():
    # Keep tests/benchmarks from shadowing the repository benchmark package.
    stash = {
        name: sys.modules.pop(name)
        for name in list(sys.modules)
        if name == "benchmarks" or name.startswith("benchmarks.")
    }
    sys.path.insert(0, str(_REPO))
    try:
        spec = importlib.util.spec_from_file_location(
            "_gpt3_frozen_reference_inode_guard",
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
        reference_takeoff_documents=(
            SimpleNamespace(
                name="reference_takeoff.json",
                size_bytes=len(_BYTES),
                sha256=sha256(_BYTES).hexdigest(),
            ),
        ),
    )


def _failures(guard, project):
    return guard.reference_document_failures(_manifest(), project)


def test_required_reference_must_exist_and_stable_regular_bytes_pass(tmp_path):
    guard = _guard()
    assert any("missing pinned reference document" in f for f in _failures(guard, tmp_path))
    (tmp_path / "reference_takeoff.json").write_bytes(_BYTES)
    assert _failures(guard, tmp_path) == []


def test_reference_sha_and_size_mismatches_remain_independent(tmp_path):
    guard = _guard()
    reference = tmp_path / "reference_takeoff.json"
    reference.write_bytes(b"X" * len(_BYTES))
    assert any("SHA mismatch" in f for f in _failures(guard, tmp_path))
    reference.write_bytes(_BYTES + b"X")
    failures = _failures(guard, tmp_path)
    assert any("SHA mismatch" in f for f in failures)
    assert any("size mismatch" in f for f in failures)


def test_byte_exact_symlink_reference_is_rejected(tmp_path):
    guard = _guard()
    target = tmp_path / "outside.json"
    target.write_bytes(_BYTES)
    try:
        (tmp_path / "reference_takeoff.json").symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    assert any("not a regular file" in f for f in _failures(guard, tmp_path))


def test_dangling_symlink_is_not_missing_reference(tmp_path):
    guard = _guard()
    try:
        (tmp_path / "reference_takeoff.json").symlink_to(tmp_path / "absent.json")
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    failures = _failures(guard, tmp_path)
    assert any("not a regular file" in f for f in failures)
    assert not any("missing pinned reference document" in f for f in failures)


def test_directory_masquerading_as_reference_fails_closed(tmp_path):
    guard = _guard()
    (tmp_path / "reference_takeoff.json").mkdir()
    assert any("not a regular file" in f for f in _failures(guard, tmp_path))


def test_inaccessible_reference_metadata_is_not_treated_as_missing(tmp_path, monkeypatch):
    guard = _guard()
    reference = tmp_path / "reference_takeoff.json"
    reference.write_bytes(_BYTES)
    original_lstat = Path.lstat

    def inaccessible(path, *args, **kwargs):
        if path == reference:
            raise PermissionError("synthetic denied")
        return original_lstat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", inaccessible)
    assert any("cannot be inspected" in f for f in _failures(guard, tmp_path))


def test_same_byte_inode_swap_before_descriptor_open_is_rejected(tmp_path, monkeypatch):
    guard = _guard()
    reference = tmp_path / "reference_takeoff.json"
    reference.write_bytes(_BYTES)
    original_open = os.open
    swapped = False

    def replace_at_open(path, flags, *args, **kwargs):
        nonlocal swapped
        if Path(path) == reference and not swapped:
            swapped = True
            replacement = tmp_path / "replacement.json"
            replacement.write_bytes(_BYTES)
            os.replace(replacement, reference)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(guard.os, "open", replace_at_open)
    assert any("changed" in f for f in _failures(guard, tmp_path))
    assert swapped


def test_same_byte_inode_swap_after_read_is_rejected(tmp_path, monkeypatch):
    guard = _guard()
    reference = tmp_path / "reference_takeoff.json"
    reference.write_bytes(_BYTES)
    original_lstat = Path.lstat
    inspections = 0

    def replace_at_final_lstat(path, *args, **kwargs):
        nonlocal inspections
        if path == reference:
            inspections += 1
            if inspections == 2:
                replacement = tmp_path / "replacement.json"
                replacement.write_bytes(_BYTES)
                os.replace(replacement, reference)
        return original_lstat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", replace_at_final_lstat)
    assert any("changed" in f for f in _failures(guard, tmp_path))
    assert inspections == 2


def test_reference_disappearing_after_initial_stat_is_not_absent(tmp_path, monkeypatch):
    guard = _guard()
    reference = tmp_path / "reference_takeoff.json"
    reference.write_bytes(_BYTES)
    original_open = os.open

    def disappear_at_open(path, flags, *args, **kwargs):
        if Path(path) == reference:
            reference.unlink()
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(guard.os, "open", disappear_at_open)
    failures = _failures(guard, tmp_path)
    assert any("changed or became inaccessible" in f for f in failures)
    assert not any("missing pinned reference document" in f for f in failures)
