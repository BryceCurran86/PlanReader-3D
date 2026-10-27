"""GPT3 frozen V2 ancestor namespace alias regressions (synthetic only).

No original PDFs, customer/signed receipts, benchmark truth or private secrets.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


_REPO = Path(__file__).resolve().parents[1]
_DATA = b"synthetic non-original bytes for ancestor ownership"


def _guard():
    # Full-suite tests sometimes shadow the repository's benchmark package.
    stash = {
        name: sys.modules.pop(name)
        for name in list(sys.modules)
        if name == "benchmarks" or name.startswith("benchmarks.")
    }
    sys.path.insert(0, str(_REPO))
    try:
        spec = importlib.util.spec_from_file_location(
            "_gpt3_frozen_ancestor_alias_integrity",
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


def _symlink(link: Path, target: Path):
    try:
        link.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"directory symlinks unavailable: {exc}")


def _suite(root: Path):
    root.mkdir(parents=True)
    (root / "manifest.json").write_text(json.dumps({
        "schema_version": "2.0",
        "projects": ["synthetic_project"],
        "required_project_count": 1,
    }), encoding="utf-8")
    project = root / "projects" / "synthetic_project"
    project.mkdir(parents=True)
    (project / "source_manifest.json").write_text(json.dumps({
        "schema_version": "2.0", "project_id": "synthetic_project",
    }), encoding="utf-8")
    for name in (
        "reference_takeoff.json", "object_universe.json",
        "verification_report.json", "unresolved_items.json",
    ):
        (project / name).write_text("{}", encoding="utf-8")
    return project


def _stub_loader(monkeypatch, guard):
    calls = []

    def loader(path):
        calls.append(path)
        return SimpleNamespace(
            project_id="synthetic_project", source_documents=(),
            reference_takeoff_documents=(), verified_items=(),
        )

    monkeypatch.setattr(guard, "load_project_manifest", loader)
    return calls


def _manifest(data=_DATA):
    return SimpleNamespace(
        project_id="synthetic_project",
        source_documents=(SimpleNamespace(
            name="synthetic.bin", sha256=hashlib.sha256(data).hexdigest(),
            size_bytes=len(data),
        ),),
    )


def test_regular_ancestor_chain_preserves_frozen_manifest_validation(tmp_path, monkeypatch):
    guard = _guard()
    project = _suite(tmp_path / "trusted" / "frozen")
    calls = _stub_loader(monkeypatch, guard)
    root = project.parents[1]
    assert guard.validate_suite(root, tmp_path / "absent_private") == []
    assert calls == [project / "source_manifest.json"]


def test_symlinked_parent_of_regular_frozen_root_fails_before_json(tmp_path, monkeypatch):
    guard = _guard()
    external = tmp_path / "external_parent"
    project = _suite(external / "frozen")
    before = (project / "source_manifest.json").read_bytes()
    alias = tmp_path / "alias_parent"
    _symlink(alias, external)
    assert (alias / "frozen").is_dir()
    assert not (alias / "frozen").is_symlink()
    monkeypatch.setattr(guard, "_json", lambda path: pytest.fail(
        f"aliased ancestor reached frozen JSON: {path}"
    ))
    expected = ["suite/manifest validation failed: frozen suite root is missing or aliased"]
    assert guard.validate_suite(alias / "frozen") == expected
    assert guard.validate_suite(alias / "frozen") == expected
    assert (project / "source_manifest.json").read_bytes() == before


def test_regular_source_ancestor_preserves_sha_and_missing_private_abstention(tmp_path):
    guard = _guard()
    source_root = tmp_path / "trusted" / "sources"
    source_root.mkdir(parents=True)
    (source_root / "synthetic.bin").write_bytes(_DATA)
    assert guard.source_document_failures((_manifest(),), source_root) == []
    assert guard.source_document_failures((_manifest(b"wrong"),), source_root)
    assert guard.source_document_failures(
        (_manifest(),), tmp_path / "trusted" / "absent_private"
    ) == []


def test_symlinked_parent_of_regular_source_root_fails_before_digest(tmp_path, monkeypatch):
    guard = _guard()
    external = tmp_path / "external_parent"
    source_root = external / "sources"
    source_root.mkdir(parents=True)
    (source_root / "synthetic.bin").write_bytes(_DATA)
    alias = tmp_path / "alias_parent"
    _symlink(alias, external)
    assert (alias / "sources").is_dir()
    assert not (alias / "sources").is_symlink()
    monkeypatch.setattr(guard, "_present_source_digest", lambda path: pytest.fail(
        f"aliased ancestor reached source digest: {path}"
    ))
    assert guard.source_document_failures((_manifest(),), alias / "sources") == [
        "original source directory is not a regular directory"
    ]
    assert (source_root / "synthetic.bin").read_bytes() == _DATA


def test_missing_private_root_under_symlinked_parent_is_not_safe_absence(tmp_path):
    guard = _guard()
    external = tmp_path / "external_parent"
    external.mkdir()
    alias = tmp_path / "alias_parent"
    _symlink(alias, external)
    assert guard.source_document_failures((_manifest(),), alias / "missing") == [
        "original source directory is not a regular directory"
    ]
    assert guard.source_document_failures((_manifest(),), tmp_path / "missing") == []


def test_parent_traversal_is_not_normalized_away_before_ownership_check(tmp_path):
    guard = _guard()
    root = tmp_path / "frozen"
    _suite(root)
    # Path retains '..' even though os.path.abspath would normalize it.
    lexical_alias = root / ".." / "frozen"
    assert ".." in lexical_alias.parts
    assert guard.validate_suite(lexical_alias) == [
        "suite/manifest validation failed: frozen suite root is missing or aliased"
    ]
    assert guard.source_document_failures(
        (_manifest(),), tmp_path / "nonexistent" / ".." / "missing"
    ) == ["original source directory is not a regular directory"]


def test_ancestor_metadata_error_fails_closed_without_opening_source(tmp_path, monkeypatch):
    guard = _guard()
    source_root = tmp_path / "trusted" / "sources"
    source_root.mkdir(parents=True)
    original_lstat = Path.lstat

    def denied(self):
        if self == source_root.parent:
            raise PermissionError("synthetic ancestor denied")
        return original_lstat(self)

    monkeypatch.setattr(Path, "lstat", denied)
    assert guard.source_document_failures((_manifest(),), source_root) == [
        "original source directory cannot be inspected"
    ]


def test_junction_like_ancestor_is_rejected_even_if_directory_mode(tmp_path, monkeypatch):
    if not hasattr(Path, "is_junction"):
        pytest.skip("junction API unavailable")
    guard = _guard()
    root = tmp_path / "trusted" / "frozen"
    _suite(root)
    original = Path.is_junction

    def junction(self):
        return self == root.parent or original(self)

    monkeypatch.setattr(Path, "is_junction", junction)
    assert guard.validate_suite(root) == [
        "suite/manifest validation failed: frozen suite root is missing or aliased"
    ]
