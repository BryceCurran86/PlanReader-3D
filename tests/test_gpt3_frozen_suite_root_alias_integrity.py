"""GPT3 frozen V2 suite-root namespace ownership regressions.

Synthetic JSON only; no original PDFs, frozen expected quantities or customer rows.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


_REPO = Path(__file__).resolve().parents[1]


def _guard():
    # Other full-suite tests may have imported an unrelated benchmarks package.
    stash = {
        name: sys.modules.pop(name)
        for name in list(sys.modules)
        if name == "benchmarks" or name.startswith("benchmarks.")
    }
    sys.path.insert(0, str(_REPO))
    try:
        spec = importlib.util.spec_from_file_location(
            "_gpt3_frozen_suite_root_alias_integrity",
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


def _suite(root: Path):
    root.mkdir()
    (root / "manifest.json").write_text(
        json.dumps({
            "schema_version": "2.0",
            "projects": ["synthetic_project"],
            "required_project_count": 1,
        }),
        encoding="utf-8",
    )
    project = root / "projects" / "synthetic_project"
    project.mkdir(parents=True)
    for name in (
        "source_manifest.json", "reference_takeoff.json",
        "object_universe.json", "verification_report.json", "unresolved_items.json",
    ):
        (project / name).write_text("{}", encoding="utf-8")
    return project


def _stub_loader(monkeypatch, guard):
    calls = []

    def load(path):
        calls.append(path)
        return SimpleNamespace(
            project_id="synthetic_project",
            source_documents=(),
            reference_takeoff_documents=(),
            verified_items=(),
        )

    monkeypatch.setattr(guard, "load_project_manifest", load)
    return calls


def test_regular_suite_root_keeps_existing_validation_and_bytes(tmp_path, monkeypatch):
    guard = _guard()
    root = tmp_path / "frozen"
    project = _suite(root)
    calls = _stub_loader(monkeypatch, guard)
    before = (root / "manifest.json").read_bytes()
    assert guard.validate_suite(root, tmp_path / "absent_private") == []
    assert calls == [project / "source_manifest.json"]
    assert (root / "manifest.json").read_bytes() == before


def test_byte_identical_external_suite_through_root_symlink_is_rejected(
    tmp_path, monkeypatch,
):
    guard = _guard()
    external = tmp_path / "external"
    project = _suite(external)
    before = (external / "manifest.json").read_bytes()
    alias = tmp_path / "frozen"
    try:
        alias.symlink_to(external, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    monkeypatch.setattr(
        guard, "load_project_manifest",
        lambda path: pytest.fail("aliased suite reached canonical project loader"),
    )
    expected = ["suite/manifest validation failed: frozen suite root is missing or aliased"]
    assert guard.validate_suite(alias, tmp_path / "absent_private") == expected
    assert guard.validate_suite(alias, tmp_path / "absent_private") == expected
    assert (external / "manifest.json").read_bytes() == before
    assert (project / "source_manifest.json").read_bytes() == b"{}"


def test_non_directory_suite_root_is_not_accepted(tmp_path, monkeypatch):
    guard = _guard()
    root = tmp_path / "frozen"
    root.write_bytes(b"synthetic regular file")
    monkeypatch.setattr(
        guard, "_json",
        lambda path: pytest.fail("non-directory suite reached JSON read"),
    )
    assert guard.validate_suite(root) == [
        "suite/manifest validation failed: frozen suite root is missing or aliased"
    ]
    assert root.read_bytes() == b"synthetic regular file"


def test_missing_suite_root_is_not_accepted(tmp_path, monkeypatch):
    guard = _guard()
    monkeypatch.setattr(
        guard, "_json",
        lambda path: pytest.fail("missing suite reached JSON read"),
    )
    assert guard.validate_suite(tmp_path / "missing") == [
        "suite/manifest validation failed: frozen suite root is missing or aliased"
    ]


def test_inaccessible_suite_root_metadata_fails_before_json(
    tmp_path, monkeypatch,
):
    guard = _guard()
    root = tmp_path / "frozen"
    _suite(root)
    original_lstat = Path.lstat

    def denied(self):
        if self == root:
            raise PermissionError("synthetic denied suite root")
        return original_lstat(self)

    monkeypatch.setattr(Path, "lstat", denied)
    monkeypatch.setattr(
        guard, "_json",
        lambda path: pytest.fail("inaccessible suite reached JSON read"),
    )
    assert guard.validate_suite(root) == [
        "suite/manifest validation failed: frozen suite root is missing or aliased"
    ]
