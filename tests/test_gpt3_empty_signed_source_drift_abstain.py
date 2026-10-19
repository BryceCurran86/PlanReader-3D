"""Empty, internally valid V1 run is not an original-source-positive execution."""
from __future__ import annotations

import json

from pb_source_closed_run_export import seal_source_closed_run
from tools import gpt3_four_project_signed_run_drift as suite
from tools.gpt3_signed_v1_physical_drift import compare_signed_v1_physical_runs
from test_gpt3_signed_v1_physical_drift import _pair, _run
from test_gpt3_four_project_signed_run_drift import _source_fixtures


def _empty(project_id="project-7"):
    return seal_source_closed_run(
        [], project_id=project_id, traces_by_quantity_id={},
    )


def test_two_empty_signed_envelopes_are_not_identical_physical_source_evidence():
    sealed = _empty()
    report = compare_signed_v1_physical_runs(sealed, sealed)
    assert report["comparison_status"] == "NO_SIGNED_SOURCE_QUANTITY_UNIVERSE"
    assert report["baseline_quantity_count"] == 0
    assert report["candidate_quantity_count"] == 0
    assert report["unchanged_quantity_ids"] == []
    assert report["source_authenticated"] is False
    assert report["official_v2_accuracy"] is None


def test_eight_to_zero_signed_regression_does_not_fabricate_rekeyed_identity():
    q, trace = _pair()
    real = _run((q, trace))
    empty = _empty()
    report = compare_signed_v1_physical_runs(real, empty)
    assert report["comparison_status"] == "NO_SIGNED_SOURCE_QUANTITY_UNIVERSE"
    assert report["baseline_quantity_count"] == 1
    assert report["candidate_quantity_count"] == 0
    assert report["removed_quantity_ids"] == [q.quantity_id]
    assert report["added_quantity_ids"] == []
    assert report["quantity_ids_alias_inferred"] is False
    assert not report["unchanged_quantity_ids"]


def test_four_project_suite_cannot_publish_completeness_for_empty_sealed_sources(
    tmp_path, monkeypatch,
):
    old, new, manifests = _source_fixtures(tmp_path, monkeypatch)
    for m in manifests:
        empty = _empty(m.project_id).to_dict()
        (new / (m.project_id + ".json")).write_text(
            json.dumps(empty), encoding="utf-8",
        )
    report = suite.build_four_project_signed_run_drift(
        baseline_dir=old, candidate_dir=new,
    )
    assert report["verified_signed_run_comparisons"] == 0
    assert report["unchanged_signed_run_comparisons"] == 0
    assert report["comparison_status"] == "PARTIAL_OR_UNAVAILABLE"
    assert all(
        row["comparison_status"] == "NO_SIGNED_SOURCE_QUANTITY_UNIVERSE"
        for row in report["projects"]
    )
    assert report["official_v2_accuracy"] is None

def test_eight_signed_quantities_lost_to_empty_run_keep_exact_missing_ids():
    pairs = [_pair(qid=f"signed-{i}", eid=f"physical-{i}") for i in range(8)]
    report = compare_signed_v1_physical_runs(_run(*pairs), _empty())
    assert report["comparison_status"] == "NO_SIGNED_SOURCE_QUANTITY_UNIVERSE"
    assert report["removed_quantity_ids"] == [f"signed-{i}" for i in range(8)]
    assert report["added_quantity_ids"] == []
    assert report["source_authenticated"] is False
    assert report["official_v2_accuracy"] is None


def test_empty_baseline_to_eight_does_not_claim_authenticated_additions():
    pairs = [_pair(qid=f"signed-{i}", eid=f"physical-{i}") for i in range(8)]
    report = compare_signed_v1_physical_runs(_empty(), _run(*pairs))
    assert report["comparison_status"] == "NO_SIGNED_SOURCE_QUANTITY_UNIVERSE"
    assert report["added_quantity_ids"] == [f"signed-{i}" for i in range(8)]
    assert report["removed_quantity_ids"] == []
    assert report["source_authenticated"] is False
    assert report["official_v2_accuracy"] is None
