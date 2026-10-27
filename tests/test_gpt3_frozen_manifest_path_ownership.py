"""Source-neutral GPT3 frozen-manifest namespace ownership regressions.

No real customer PDF, frozen expected quantity, signed output or secret is read.
The test names and bytes are synthetic; source-path rejection precedes I/O.
"""
from __future__ import annotations

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


_REPO = Path(__file__).resolve().parents[1]
_BYTES = b"synthetic source bytes; not an original customer PDF"


def _guard():
    # Preserve the repository benchmark import when test/benchmark packages
    # have previously shadowed it during the complete CI test suite.
    stash = {
        name: sys.modules.pop(name)
        for name in list(sys.modules)
        if name == "benchmarks" or name.startswith("benchmarks.")
    }
    sys.path.insert(0, str(_REPO))
    try:
        spec = importlib.util.spec_from_file_location(
            "_gpt3_frozen_manifest_path_ownership",
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


def _document(name: str):
    return SimpleNamespace(
        name=name, size_bytes=len(_BYTES), sha256=sha256(_BYTES).hexdigest(),
    )


def _manifest(*, source_names=(), reference_names=()):
    return SimpleNamespace(
        project_id="synthetic_project",
        source_documents=tuple(_document(name) for name in source_names),
        reference_takeoff_documents=tuple(_document(name) for name in reference_names),
    )


@pytest.mark.parametrize("name", [
    "au_qld_synthetic", "Original Plan.pdf", "reference_takeoff.json",
    "file-with_underscores.2026.pdf", "COM10.pdf", "LPT0.pdf",
    "company.txt", "file[1].pdf",
])
def test_portable_single_components_are_accepted(name):
    assert _guard()._safe_path_component(name)


@pytest.mark.parametrize("name", [
    "", " ", ".", "..", "../external.pdf", "dir/file.pdf",
    r"..\\external.pdf", r"C:\\private\\original.pdf", "C:original.pdf",
    "/tmp/other.pdf", "original.pdf.", "original.pdf ",
    "file\nname.pdf", "file\x00name.pdf", "file\x7fname.pdf",
    "CON", "con.pdf", "NUL.txt", "PrN.pdf", "AUX", "COM1.pdf",
    "LPT9.pdf", "COM¹.pdf", "lpt³.pdf", "CONIN$.txt", "CONOUT$.txt",
    "CON .pdf", "bad?.pdf", "bad*.pdf", "bad<.pdf", "bad>.pdf",
    'bad"quote.pdf', "bad|pipe.pdf",
])
def test_unsafe_components_are_rejected(name):
    assert not _guard()._safe_path_component(name)


@pytest.mark.parametrize("name", [
    "../outside.pdf", r"..\\outside.pdf", "C:outside.pdf",
    "/tmp/outside.pdf", "source.pdf.", "source.pdf\nother",
    "CON.pdf", "nul.txt", "COM1.pdf", "LPT².pdf", "CON .pdf",
    "bad?.pdf", "bad|name.pdf",
])
def test_source_path_escape_is_vetoed_before_digest(tmp_path, monkeypatch, name):
    guard = _guard()
    monkeypatch.setattr(
        guard, "_present_source_digest",
        lambda path: pytest.fail(f"unsafe source reached digest: {path}"),
    )
    failures = guard.source_document_failures(
        (_manifest(source_names=(name,)),), tmp_path,
    )
    assert len(failures) == 1
    assert "unsafe source document name" in failures[0]


@pytest.mark.parametrize("name", [
    "../outside.json", r"..\\outside.json", "C:outside.json",
    "/tmp/outside.json", "reference_takeoff.json.", "ref\x00name.json",
    "PRN.json", "AUX.json", "LPT9.json", "COM¹.json",
    "CONIN$.json", "bad*.json", "bad<name.json",
])
def test_reference_path_escape_is_vetoed_before_digest(tmp_path, monkeypatch, name):
    guard = _guard()
    monkeypatch.setattr(
        guard, "_present_source_digest",
        lambda path: pytest.fail(f"unsafe reference reached digest: {path}"),
    )
    failures = guard.reference_document_failures(
        _manifest(reference_names=(name,)), tmp_path,
    )
    assert len(failures) == 1
    assert "unsafe reference document name" in failures[0]


@pytest.mark.parametrize("project_id", [
    "../outside", r"..\\outside", "/tmp/elsewhere", "C:outside",
    "project.", "project ", "project\nother", 123, None,
    "CON", "con.txt", "NUL", "LPT3", "COM³", "CONOUT$.json",
    "bad?", 'bad"quote', "bad|name",
])
def test_unsafe_project_id_fails_before_manifest_loader(
    tmp_path, monkeypatch, project_id,
):
    guard = _guard()
    (tmp_path / "manifest.json").write_text(
        json.dumps({"schema_version": "2.0", "projects": [project_id], "required_project_count": 1}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        guard, "load_project_manifest",
        lambda path: pytest.fail("unsafe project reached manifest loader"),
    )
    failures = guard.validate_suite(tmp_path)
    assert len(failures) == 1
    assert "unsafe project id" in failures[0]


def test_suite_project_ids_must_be_a_list_before_manifest_loader(
    tmp_path, monkeypatch,
):
    guard = _guard()
    (tmp_path / "manifest.json").write_text(
        json.dumps({"schema_version": "2.0", "projects": "au_qld_synthetic", "required_project_count": 1}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        guard, "load_project_manifest",
        lambda path: pytest.fail("non-list project IDs reached loader"),
    )
    assert "unsafe project id" in guard.validate_suite(tmp_path)[0]


def test_safe_project_id_reaches_existing_manifest_authority(
    tmp_path, monkeypatch,
):
    guard = _guard()
    (tmp_path / "manifest.json").write_text(
        json.dumps({"schema_version": "2.0", "projects": ["au_qld_synthetic"], "required_project_count": 1}),
        encoding="utf-8",
    )
    # The strict duplicate-member preflight now reads the synthetic project
    # manifest before invoking the unchanged canonical loader. Supply a
    # valid, unique-key file so this test still isolates safe ID routing.
    project = tmp_path / "projects" / "au_qld_synthetic"
    project.mkdir(parents=True)
    (project / "source_manifest.json").write_text(
        json.dumps({"schema_version": "2.0", "project_id": "au_qld_synthetic"}),
        encoding="utf-8",
    )
    called = []

    def loader(path):
        called.append(path)
        raise ValueError("synthetic loader reached")

    monkeypatch.setattr(guard, "load_project_manifest", loader)
    assert "synthetic loader reached" in guard.validate_suite(tmp_path)[0]
    assert called == [
        tmp_path / "projects" / "au_qld_synthetic" / "source_manifest.json"
    ]


def test_safe_source_digest_and_genuine_missing_private_source_stay_unchanged(tmp_path):
    guard = _guard()
    manifest = _manifest(source_names=("synthetic.pdf",))
    assert guard.source_document_failures((manifest,), tmp_path) == []
    (tmp_path / "synthetic.pdf").write_bytes(_BYTES)
    assert guard.source_document_failures((manifest,), tmp_path) == []


def test_safe_required_reference_uses_existing_sha_size_checks(tmp_path):
    guard = _guard()
    reference = tmp_path / "reference_takeoff.json"
    reference.write_bytes(_BYTES)
    manifest = _manifest(reference_names=("reference_takeoff.json",))
    assert guard.reference_document_failures(manifest, tmp_path) == []
    reference.write_bytes(_BYTES + b"x")
    failures = guard.reference_document_failures(manifest, tmp_path)
    assert any("SHA mismatch" in failure for failure in failures)
    assert any("size mismatch" in failure for failure in failures)


def test_rejected_escape_does_not_mutate_external_matching_bytes(tmp_path):
    guard = _guard()
    source_root = tmp_path / "sources"
    source_root.mkdir()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(_BYTES)
    manifest = _manifest(source_names=("../outside.pdf",))
    first = guard.source_document_failures((manifest,), source_root)
    second = guard.source_document_failures((manifest,), source_root)
    assert first == second
    assert len(first) == 1
    assert outside.read_bytes() == _BYTES
