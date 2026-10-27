"""GPT3 frozen V2 filesystem alias/regular-inode integrity regressions.

Source-neutral synthetic files only. No original PDFs, signed/customer records,
frozen benchmark truth or production quantity data are modified.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


_REPO = Path(__file__).resolve().parents[1]
_REQUIRED = (
    "source_manifest.json", "reference_takeoff.json", "object_universe.json",
    "verification_report.json", "unresolved_items.json",
)


def _guard():
    stash = {
        name: sys.modules.pop(name)
        for name in list(sys.modules)
        if name == "benchmarks" or name.startswith("benchmarks.")
    }
    sys.path.insert(0, str(_REPO))
    try:
        spec = importlib.util.spec_from_file_location(
            "_gpt3_frozen_manifest_alias_integrity",
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


def _symlink(link: Path, target: Path, *, directory: bool = False):
    try:
        link.symlink_to(target, target_is_directory=directory)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink unavailable on this test platform: {exc}")


def _suite(root: Path):
    root.mkdir(parents=True, exist_ok=True)
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
    (project / "source_manifest.json").write_text(
        json.dumps({"schema_version": "2.0", "project_id": "synthetic_project"}),
        encoding="utf-8",
    )
    for name in _REQUIRED[1:]:
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


def test_valid_unique_json_and_safe_project_tree_preserve_integrity(tmp_path, monkeypatch):
    guard = _guard()
    root = tmp_path / "frozen"
    project = _suite(root)
    calls = _stub_loader(monkeypatch, guard)
    assert guard._json(root / "manifest.json")["projects"] == ["synthetic_project"]
    assert guard._json(project / "object_universe.json") == {}
    assert guard.validate_suite(root, tmp_path / "absent_private") == []
    assert calls == [project / "source_manifest.json"]


@pytest.mark.parametrize("name", [
    "manifest.json", "source_manifest.json", "object_universe.json",
])
def test_json_symlink_to_valid_external_bytes_is_rejected(tmp_path, name):
    guard = _guard()
    original = tmp_path / name
    external = tmp_path / "external.json"
    external.write_text('{"schema_version":"2.0"}', encoding="utf-8")
    _symlink(original, external)
    with pytest.raises(ValueError, match="not a regular file"):
        guard._json(original)
    assert external.read_text(encoding="utf-8") == '{"schema_version":"2.0"}'


def test_json_directory_is_rejected_without_reading(tmp_path):
    guard = _guard()
    directory = tmp_path / "synthetic.json"
    directory.mkdir()
    with pytest.raises(ValueError, match="not a regular file"):
        guard._json(directory)


@pytest.mark.parametrize("name", _REQUIRED)
def test_required_project_metadata_symlink_fails_closed(
    tmp_path, monkeypatch, name,
):
    guard = _guard()
    root = tmp_path / "frozen"
    project = _suite(root)
    _stub_loader(monkeypatch, guard)
    external = tmp_path / "outside.json"
    external.write_text("{}", encoding="utf-8")
    target = project / name
    target.unlink()
    _symlink(target, external)
    failures = guard.validate_suite(root, tmp_path / "absent_private")
    if name == "source_manifest.json":
        # Project manifests are read and vetoed by the strict preflight
        # before the later required-file census is reached.
        assert any("frozen JSON is not a regular file" in failure for failure in failures), failures
    else:
        assert any(
            f"missing {name} or unsafe file type" in failure for failure in failures
        ), failures
    assert external.read_bytes() == b"{}"


def test_symlinked_suite_manifest_fails_before_project_loader(
    tmp_path, monkeypatch,
):
    guard = _guard()
    root = tmp_path / "frozen"
    _suite(root)
    external = tmp_path / "outside_suite.json"
    external.write_bytes((root / "manifest.json").read_bytes())
    (root / "manifest.json").unlink()
    _symlink(root / "manifest.json", external)
    monkeypatch.setattr(
        guard, "load_project_manifest",
        lambda path: pytest.fail("aliased suite reached project loader"),
    )
    failures = guard.validate_suite(root)
    assert len(failures) == 1
    assert "not a regular file" in failures[0]


def test_symlinked_project_directory_fails_before_manifest_loader(
    tmp_path, monkeypatch,
):
    guard = _guard()
    root = tmp_path / "frozen"
    project = _suite(root)
    external = tmp_path / "outside_project"
    project.rename(external)
    _symlink(project, external, directory=True)
    monkeypatch.setattr(
        guard, "load_project_manifest",
        lambda path: pytest.fail("aliased project reached manifest loader"),
    )
    failures = guard.validate_suite(root)
    assert len(failures) == 1
    assert "project directory is missing or aliased" in failures[0]


def test_symlinked_projects_root_fails_before_manifest_loader(
    tmp_path, monkeypatch,
):
    guard = _guard()
    root = tmp_path / "frozen"
    _suite(root)
    projects = root / "projects"
    outside = tmp_path / "outside_projects"
    projects.rename(outside)
    _symlink(projects, outside, directory=True)
    monkeypatch.setattr(
        guard, "load_project_manifest",
        lambda path: pytest.fail("aliased projects root reached loader"),
    )
    failures = guard.validate_suite(root)
    assert len(failures) == 1
    assert "projects directory is missing or aliased" in failures[0]


def test_json_same_byte_inode_replacement_during_read_is_rejected(
    tmp_path, monkeypatch,
):
    guard = _guard()
    path = tmp_path / "synthetic.json"
    raw = b'{"schema_version":"2.0"}'
    path.write_bytes(raw)
    original_fstat = os.fstat
    calls = 0

    def replacing_fstat(fd):
        nonlocal calls
        calls += 1
        snapshot = original_fstat(fd)
        if calls == 2:
            replacement = tmp_path / "replacement.json"
            replacement.write_bytes(raw)
            os.replace(replacement, path)
        return snapshot

    monkeypatch.setattr(guard.os, "fstat", replacing_fstat)
    with pytest.raises(ValueError, match="changed during verification"):
        guard._json(path)
    assert path.read_bytes() == raw
    assert calls >= 2
