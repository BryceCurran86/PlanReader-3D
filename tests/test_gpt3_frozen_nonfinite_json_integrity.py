"""Source-neutral GPT3 regressions for non-finite frozen V2 JSON numbers.

No private original, signed/customer, or frozen benchmark file is modified.
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
    # Match the existing frozen-integrity tests' isolation of benchmark imports.
    stash = {
        name: sys.modules.pop(name)
        for name in list(sys.modules)
        if name == "benchmarks" or name.startswith("benchmarks.")
    }
    sys.path.insert(0, str(_REPO))
    try:
        spec = importlib.util.spec_from_file_location(
            "_gpt3_frozen_nonfinite_json_integrity",
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
    root.mkdir(parents=True)
    (root / "manifest.json").write_text(
        json.dumps({
            "schema_version": "2.0",
            "projects": ["synthetic"],
            "required_project_count": 1,
        }),
        encoding="utf-8",
    )
    project = root / "projects" / "synthetic"
    project.mkdir(parents=True)
    (project / "source_manifest.json").write_text(
        '{"schema_version":"2.0","project_id":"synthetic"}',
        encoding="utf-8",
    )
    for name in (
        "reference_takeoff.json", "object_universe.json",
        "verification_report.json", "unresolved_items.json",
    ):
        (project / name).write_text("{}", encoding="utf-8")
    return project


def _stub_loader(monkeypatch, guard):
    calls = []

    def load(path):
        calls.append(path)
        return SimpleNamespace(
            project_id="synthetic",
            source_documents=(),
            reference_takeoff_documents=(),
            verified_items=(),
        )

    monkeypatch.setattr(guard, "load_project_manifest", load)
    return calls


@pytest.mark.parametrize("literal", [
    "NaN", "Infinity", "-Infinity", "1e999", "-1e999",
    '{"nested":[0,{"quantity":NaN}]}',
    '[{"quantity":1e999}]',
])
def test_nonfinite_json_numeric_literals_rejected_at_stable_reader(
    tmp_path, literal,
):
    guard = _guard()
    path = tmp_path / "synthetic.json"
    path.write_text('{"value":' + literal + '}', encoding="utf-8")
    with pytest.raises(ValueError, match="non-finite JSON numeric value"):
        guard._json(path)


def test_finite_numbers_and_literal_strings_remain_valid(tmp_path):
    guard = _guard()
    path = tmp_path / "synthetic.json"
    path.write_text(
        '{"values":[0,1,-2,1e308,-1e-300,0.0],'
        '"label":"NaN Infinity 1e999","nested":{"value":3.5}}',
        encoding="utf-8",
    )
    parsed = guard._json(path)
    assert parsed["values"] == [0, 1, -2, 1e308, -1e-300, 0.0]
    assert parsed["label"] == "NaN Infinity 1e999"
    assert parsed["nested"]["value"] == 3.5


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity", "1e999"])
def test_suite_nonfinite_extra_field_blocks_before_project_loader(
    tmp_path, monkeypatch, literal,
):
    guard = _guard()
    root = tmp_path / "frozen"
    _suite(root)
    calls = _stub_loader(monkeypatch, guard)
    (root / "manifest.json").write_text(
        '{"schema_version":"2.0","projects":["synthetic"],'
        '"required_project_count":1,"untrusted":' + literal + '}',
        encoding="utf-8",
    )
    failures = guard.validate_suite(root, tmp_path / "absent_private")
    assert len(failures) == 1
    assert "non-finite JSON numeric value" in failures[0]
    assert calls == []


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity", "1e999"])
def test_project_nonfinite_json_blocks_canonical_loader(
    tmp_path, monkeypatch, literal,
):
    guard = _guard()
    root = tmp_path / "frozen"
    project = _suite(root)
    calls = _stub_loader(monkeypatch, guard)
    (project / "source_manifest.json").write_text(
        '{"schema_version":"2.0","project_id":"synthetic",'
        '"untrusted":{"nested":[' + literal + ']}}',
        encoding="utf-8",
    )
    failures = guard.validate_suite(root, tmp_path / "absent_private")
    assert len(failures) == 1
    assert "non-finite JSON numeric value" in failures[0]
    assert calls == []


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity", "1e999"])
def test_object_universe_nonfinite_json_fails_closed(
    tmp_path, monkeypatch, literal,
):
    guard = _guard()
    root = tmp_path / "frozen"
    project = _suite(root)
    calls = _stub_loader(monkeypatch, guard)
    (project / "object_universe.json").write_text(
        '{"objects":[{"area":' + literal + '}]}', encoding="utf-8",
    )
    failures = guard.validate_suite(root, tmp_path / "absent_private")
    assert len(failures) == 1
    assert "object_universe invalid JSON" in failures[0]
    assert "non-finite JSON numeric value" in failures[0]
    assert calls == [project / "source_manifest.json"]


def test_valid_synthetic_suite_still_passes_with_strict_decoder(
    tmp_path, monkeypatch,
):
    guard = _guard()
    root = tmp_path / "frozen"
    project = _suite(root)
    calls = _stub_loader(monkeypatch, guard)
    (project / "object_universe.json").write_text(
        '{"objects":[{"area":1e308,"name":"Infinity"}]}',
        encoding="utf-8",
    )
    assert guard.validate_suite(root, tmp_path / "absent_private") == []
    assert calls == [project / "source_manifest.json"]
