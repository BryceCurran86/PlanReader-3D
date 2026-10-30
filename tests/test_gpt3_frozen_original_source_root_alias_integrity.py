"""GPT3 private-original source directory alias integrity regressions.

Synthetic bytes only; no private PDFs, frozen truth or signed/customer rows.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


_REPO = Path(__file__).resolve().parents[1]


def _guard():
    stash = {
        name: sys.modules.pop(name)
        for name in list(sys.modules)
        if name == "benchmarks" or name.startswith("benchmarks.")
    }
    sys.path.insert(0, str(_REPO))
    try:
        spec = importlib.util.spec_from_file_location(
            "_gpt3_frozen_original_source_root_alias",
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


def _manifest(data: bytes):
    return SimpleNamespace(
        project_id="synthetic",
        source_documents=(
            SimpleNamespace(
                name="synthetic_source.bin",
                sha256=hashlib.sha256(data).hexdigest(),
                size_bytes=len(data),
            ),
        ),
    )


def test_regular_source_directory_preserves_pinned_byte_verification(tmp_path):
    guard = _guard()
    data = b"synthetic source bytes only"
    root = tmp_path / "trusted"
    root.mkdir()
    (root / "synthetic_source.bin").write_bytes(data)
    assert guard.source_document_failures((_manifest(data),), root) == []
    assert guard.source_document_failures((_manifest(b"different"),), root)
    assert (root / "synthetic_source.bin").read_bytes() == data


def test_genuinely_missing_public_original_directory_remains_source_unavailable(tmp_path):
    guard = _guard()
    assert guard.source_document_failures(
        (_manifest(b"not provided"),), tmp_path / "absent_private"
    ) == []


def test_matching_external_bytes_via_source_directory_symlink_fail_closed(tmp_path):
    guard = _guard()
    data = b"same pinned synthetic bytes"
    external = tmp_path / "external"
    external.mkdir()
    (external / "synthetic_source.bin").write_bytes(data)
    alias = tmp_path / "trusted"
    try:
        alias.symlink_to(external, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    assert guard.source_document_failures((_manifest(data),), alias) == [
        "original source directory is not a regular directory"
    ]
    assert (external / "synthetic_source.bin").read_bytes() == data


def test_present_non_directory_source_root_is_not_absent(tmp_path):
    guard = _guard()
    root = tmp_path / "trusted"
    root.write_bytes(b"not a directory")
    assert guard.source_document_failures((_manifest(b"synthetic"),), root) == [
        "original source directory is not a regular directory"
    ]
    assert root.read_bytes() == b"not a directory"


def test_inaccessible_source_root_metadata_is_not_absent(tmp_path, monkeypatch):
    guard = _guard()
    root = tmp_path / "trusted"
    root.mkdir()
    original = Path.lstat

    def denied(self):
        if self == root:
            raise PermissionError("synthetic denied source root")
        return original(self)

    monkeypatch.setattr(Path, "lstat", denied)
    assert guard.source_document_failures((_manifest(b"synthetic"),), root) == [
        "original source directory cannot be inspected"
    ]


def test_alias_rejected_even_if_no_manifest_sources_are_listed(tmp_path):
    guard = _guard()
    external = tmp_path / "external"
    external.mkdir()
    alias = tmp_path / "trusted"
    try:
        alias.symlink_to(external, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    manifest = SimpleNamespace(project_id="synthetic", source_documents=())
    assert guard.source_document_failures((manifest,), alias) == [
        "original source directory is not a regular directory"
    ]
