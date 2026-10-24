"""Suite drift is a signed-receipt inventory, never a frozen accuracy result."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
import json

import pytest

from pb_source_closed_run_export import seal_source_closed_run
from test_customer_output_verification import quantity, trace
from tools import gpt3_four_project_signed_run_drift as report


def _source_fixtures(tmp_path, monkeypatch):
    old = tmp_path / "older"
    new = tmp_path / "newer"
    old.mkdir()
    new.mkdir()
    manifests = []
    for i in range(4):
        project_id = f"test-source-{i}"
        manifests.append(SimpleNamespace(project_id=project_id))
        q = quantity(f"qty-{i}", f"physical-{i}")
        q = replace(q, metadata={**q.metadata, "project_id": project_id})
        t = replace(trace(q), project_id=project_id)
        sealed = seal_source_closed_run(
            (q,), project_id=project_id, traces_by_quantity_id={q.quantity_id: t},
        )
        for path in (old, new):
            (path / (project_id + ".json")).write_text(
                json.dumps(sealed.to_dict()), encoding="utf-8",
            )
    monkeypatch.setattr(report, "load_suite_manifests", lambda _: manifests)
    return old, new, manifests


def test_four_unchanged_source_handoffs_are_not_official_accuracy(tmp_path, monkeypatch):
    old, new, manifests = _source_fixtures(tmp_path, monkeypatch)
    result = report.build_four_project_signed_run_drift(
        baseline_dir=old, candidate_dir=new,
    )
    assert result["comparison_status"] == "COMPLETE_EXACT_SIGNED_CONTENT"
    assert result["verified_signed_run_comparisons"] == 4
    assert result["unchanged_signed_run_comparisons"] == 4
    assert result["source_authenticated"] is False
    assert result["publication_status"] == "UNPUBLISHED"
    assert result["official_v2_accuracy"] is None
    assert all(item["drift_report"]["unchanged_quantity_ids"] for item in result["projects"])


def test_missing_new_project_is_unavailable_not_zero_quantity(tmp_path, monkeypatch):
    old, new, manifests = _source_fixtures(tmp_path, monkeypatch)
    (new / (manifests[0].project_id + ".json")).unlink()
    result = report.build_four_project_signed_run_drift(
        baseline_dir=old, candidate_dir=new,
    )
    assert result["comparison_status"] == "PARTIAL_OR_UNAVAILABLE"
    assert result["verified_signed_run_comparisons"] == 3
    assert result["unchanged_signed_run_comparisons"] == 3
    missing = next(x for x in result["projects"]
                   if x["project_id"] == manifests[0].project_id)
    assert missing["comparison_status"] == "SIGNED_RUN_UNAVAILABLE"
    assert missing["missing_sources"] == ["candidate"]
    assert missing["drift_report"] is None
    assert result["official_v2_accuracy"] is None


def test_one_corrupt_signature_aborts_four_project_source_comparison(tmp_path, monkeypatch):
    old, new, manifests = _source_fixtures(tmp_path, monkeypatch)
    path = new / (manifests[1].project_id + ".json")
    value = json.loads(path.read_text(encoding="utf-8"))
    value["quantities"][0]["value"] = 999
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises((ValueError, RuntimeError), match="fingerprint"):
        report.build_four_project_signed_run_drift(
            baseline_dir=old, candidate_dir=new,
        )


def test_two_different_project_recipts_cannot_fill_one_slot(tmp_path, monkeypatch):
    old, new, manifests = _source_fixtures(tmp_path, monkeypatch)
    (new / (manifests[0].project_id + ".json")).write_bytes(
        (old / (manifests[1].project_id + ".json")).read_bytes()
    )
    with pytest.raises(ValueError, match="project identity"):
        report.build_four_project_signed_run_drift(
            baseline_dir=old, candidate_dir=new,
        )


def test_suite_cli_rejects_existing_output_and_input_directory(tmp_path, monkeypatch):
    old, new, manifests = _source_fixtures(tmp_path, monkeypatch)
    args = ["--baseline-dir", str(old), "--candidate-dir", str(new),
            "--output", str(tmp_path / "comparison.json")]
    assert report.main(args) == 0
    result = json.loads((tmp_path / "comparison.json").read_text(encoding="utf-8"))
    assert result["comparison_status"] == "COMPLETE_EXACT_SIGNED_CONTENT"
    with pytest.raises(FileExistsError, match="new path"):
        report.main(args)
    args[-1] = str(old / "unsafe.json")
    with pytest.raises(ValueError, match="protected evidence"):
        report.main(args)
