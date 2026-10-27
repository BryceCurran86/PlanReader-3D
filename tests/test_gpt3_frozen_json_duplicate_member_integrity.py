"""GPT3 frozen V2 JSON duplicate-member fail-closed regressions.

All documents are synthetic; no original PDFs, benchmark expected values,
signed/customer output or secrets are opened or modified.
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
    # The full CI suite may have imported a test fixture named "benchmarks".
    stash = {
        name: sys.modules.pop(name)
        for name in list(sys.modules)
        if name == "benchmarks" or name.startswith("benchmarks.")
    }
    sys.path.insert(0, str(_REPO))
    try:
        spec = importlib.util.spec_from_file_location(
            "_gpt3_frozen_json_duplicate_member_integrity",
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


@pytest.mark.parametrize("payload", [
    '{"projects":["first"],"projects":["second"]}',
    '{"source_documents":[{"sha256":"first","sha256":"second"}]}',
    '{"verified_takeoff_items":[{"expected_quantity":1,"expected_quantity":2}]}',
    '{"object":{"nested":{"object_ref":"first","object_ref":"second"}}}',
    '{"a":null,"a":false}',
])
def test_duplicate_members_at_any_depth_fail_closed(tmp_path, payload):
    guard = _guard()
    path = tmp_path / "synthetic.json"
    path.write_text(payload, encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="duplicate JSON object member"):
        guard._json(path)
    assert path.read_bytes() == before


def test_unique_nested_json_preserves_existing_decoding(tmp_path):
    path = tmp_path / "synthetic.json"
    expected = {"projects": [{"id": "first"}, {"id": "second"}], "status": None}
    path.write_text(json.dumps(expected), encoding="utf-8")
    assert _guard()._json(path) == expected


def _suite(root):
    (root / "manifest.json").write_text(
        json.dumps({
            "schema_version": "2.0",
            "projects": ["synthetic_project"],
            "required_project_count": 1,
        }),
        encoding="utf-8",
    )


def test_duplicate_suite_project_selection_never_reaches_loader(tmp_path, monkeypatch):
    guard = _guard()
    (tmp_path / "manifest.json").write_text(
        '{"schema_version":"2.0","projects":["synthetic_project"],'
        '"projects":["other"],"required_project_count":1}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        guard, "load_project_manifest",
        lambda path: pytest.fail("ambiguous suite reached project loader"),
    )
    failures = guard.validate_suite(tmp_path, tmp_path / "missing_private")
    assert len(failures) == 1
    assert "duplicate JSON object member" in failures[0]


@pytest.mark.parametrize("nested", [
    '{"source_documents":[{"name":"synthetic.pdf","name":"other.pdf"}]}',
    '{"verified_takeoff_items":[{"item_id":"one","item_id":"two"}]}',
    '{"reference_takeoff_documents":[{"sha256":"first","sha256":"second"}]}',
])
def test_duplicate_project_manifest_nested_members_never_reach_loader(
    tmp_path, monkeypatch, nested,
):
    guard = _guard()
    _suite(tmp_path)
    project = tmp_path / "projects" / "synthetic_project"
    project.mkdir(parents=True)
    (project / "source_manifest.json").write_text(
        '{"schema_version":"2.0","project_id":"synthetic_project",'
        + nested[1:],
        encoding="utf-8",
    )
    monkeypatch.setattr(
        guard, "load_project_manifest",
        lambda path: pytest.fail("ambiguous project reached canonical loader"),
    )
    failures = guard.validate_suite(tmp_path, tmp_path / "missing_private")
    assert len(failures) == 1
    assert "duplicate JSON object member" in failures[0]


def test_unique_project_manifest_still_reaches_canonical_loader(
    tmp_path, monkeypatch,
):
    guard = _guard()
    _suite(tmp_path)
    project = tmp_path / "projects" / "synthetic_project"
    project.mkdir(parents=True)
    path = project / "source_manifest.json"
    path.write_text(
        '{"schema_version":"2.0","project_id":"synthetic_project",'
        '"source_documents":[{"name":"synthetic.pdf","sha256":"abc"}]}',
        encoding="utf-8",
    )
    called = []

    def loader(value):
        called.append(value)
        raise ValueError("canonical loader invoked")

    monkeypatch.setattr(guard, "load_project_manifest", loader)
    failures = guard.validate_suite(tmp_path, tmp_path / "missing_private")
    assert len(failures) == 1
    assert "canonical loader invoked" in failures[0]
    assert called == [path]


def test_duplicate_object_universe_member_cannot_pass_integrity(
    tmp_path, monkeypatch,
):
    guard = _guard()
    _suite(tmp_path)
    project = tmp_path / "projects" / "synthetic_project"
    project.mkdir(parents=True)
    for name in (
        "source_manifest.json", "reference_takeoff.json",
        "verification_report.json", "unresolved_items.json",
    ):
        (project / name).write_text("{}", encoding="utf-8")
    (project / "object_universe.json").write_text(
        '{"objects":[{"object_ref":"first","object_ref":"second"}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        guard, "load_project_manifest",
        lambda path: SimpleNamespace(
            project_id="synthetic_project", source_documents=(),
            reference_takeoff_documents=(), verified_items=(),
        ),
    )
    failures = guard.validate_suite(tmp_path, tmp_path / "missing_private")
    assert any(
        "object_universe invalid JSON: duplicate JSON object member" in failure
        for failure in failures
    )
