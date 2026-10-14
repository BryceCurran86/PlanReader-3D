"""The two-project signed development audit never publishes full Plan V2."""
from __future__ import annotations

import json

import pytest

from tools import report_gpt3_selected_two_project_original_evidence as module


def _project(project, *, denominator, matched, missed, extras=0, ids=("q1",)):
    return {
        "project_id": project,
        "original_source_sha_verified": True,
        "source_sha256s": ["a" * 64],
        "sealed_run_id": "sealed:" + project,
        "sealed_run_fingerprint": "b" * 64,
        "customer_quantity_ids": list(ids),
        "customer_bijection_verified": True,
        "reconciliation_complete": True,
        "denominator": denominator,
        "matched_within_tolerance": matched,
        "matched_outside_tolerance": 0,
        "missed": missed,
        "partial": 0,
        "unresolved": 0,
        "unsupported_extra": extras,
        "abstained_outputs": 0,
        "lineage_conflicts": 0,
        "coverage_accuracy": matched / denominator,
        "precision_adjusted_accuracy": matched / denominator,
        "produced_items": [],
    }


def test_independently_validated_selected_projects_do_not_publish_four_project_score(monkeypatch):
    projects = {
        "source-a": _project("source-a", denominator=27, matched=8, missed=19, ids=("q-a",)),
        "source-b": _project(
            "source-b", denominator=24, matched=0, missed=24, extras=3,
            ids=("q-b1", "q-b2", "q-b3"),
        ),
    }
    monkeypatch.setattr(module, "_checked_one", lambda r: projects[r["project_id"]])
    report = module.build_selected_two_project_development_evidence(
        [{"project_id": "source-b"}, {"project_id": "source-a"}]
    )
    assert [x["project_id"] for x in report["projects"]] == ["source-a", "source-b"]
    assert report["publication_status"] == "SELECTED_PROJECT_DEVELOPMENT_ONLY"
    assert report["selected_project_count"] == 2
    assert report["selected_denominator"] == 51
    assert report["matched_within_tolerance"] == 8
    assert report["missed"] == 43
    assert report["unsupported_extra"] == 3
    assert report["selected_coverage_accuracy"] == pytest.approx(8 / 51)
    assert report["selected_precision_adjusted_accuracy"] is None
    assert report["official_four_project_suite_result"] is None
    assert report["official_four_project_accuracy"] is None
    assert report["full_four_project_publication_allowed"] is False


def test_missing_or_extra_project_does_not_fake_an_unexecuted_denominator(monkeypatch):
    monkeypatch.setattr(
        module, "_checked_one", lambda _r: (_ for _ in ()).throw(
            AssertionError("unexecuted source must never be scored")
        ),
    )
    for data in ([], [{}], [{}, {}, {}]):
        with pytest.raises(ValueError, match="exactly two"):
            module.build_selected_two_project_development_evidence(data)


def test_duplicate_project_id_and_cross_project_customer_identity_fail(monkeypatch):
    project = _project("same-source", denominator=24, matched=0, missed=24)
    monkeypatch.setattr(module, "_checked_one", lambda _: project)
    with pytest.raises(ValueError, match="reuse one source"):
        module.build_selected_two_project_development_evidence([{}, {}])
    copies = {
        "a": _project("a", denominator=27, matched=8, missed=19, ids=("same-q",)),
        "b": _project("b", denominator=24, matched=0, missed=24, ids=("same-q",)),
    }
    monkeypatch.setattr(module, "_checked_one", lambda r: copies[r["project_id"]])
    with pytest.raises(ValueError, match="identity reused"):
        module.build_selected_two_project_development_evidence([
            {"project_id": "a"}, {"project_id": "b"},
        ])


def test_invalid_original_entry_never_consults_evaluator():
    for entry in (
        {}, {"project_id": "unknown"},
        {"manifest": "", "original_files": [], "sealed": "", "customer": "",
         "identity_map": "", "exact_report": ""},
    ):
        with pytest.raises(ValueError):
            module._checked_one(entry)


def test_selected_report_writer_cannot_overwrite_an_existing_signed_file(
    tmp_path, monkeypatch
):
    original = tmp_path / "original-sealed.json"
    original.write_text('{"signed":true}', encoding="utf-8")
    other = tmp_path / "other.json"
    other.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(module, "build_selected_two_project_development_evidence",
                        lambda _entries: {"publication_status": "SELECTED_PROJECT_DEVELOPMENT_ONLY"})
    monkeypatch.setattr(module, "_json_object", lambda _path: {
        "manifest": str(other), "original_files": [], "sealed": str(original),
        "customer": str(other), "identity_map": str(other), "exact_report": str(other),
    })
    with pytest.raises(FileExistsError):
        module.main(["--entry", str(other), "--entry", str(other),
                     "--output", str(original)])
    assert original.read_text(encoding="utf-8") == '{"signed":true}'
