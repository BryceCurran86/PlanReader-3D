"""Read-only host/frame stage ledger must never score or invent openings."""
from copy import deepcopy

import pytest

from tools.diag_gpt3_maryborough_source_stage_ledger import (
    build_maryborough_source_stage_ledger as build,
)


def _inputs():
    summary = {
        "project_id": "au_qld_maryborough_service_station",
        "source_sha256": "a" * 64,
        "family_group": "core",
        "claim_status": "abstained",
        "benchmark_score_granted": False,
        "family_counts": {
            "floor_area": 0, "opening_area": 0, "opening_count": 0,
        },
    }
    bindings = [
        {
            "opening_identity_id": "opening-A", "page_id": "7",
            "status": "abstained", "record_id": None, "host_wall_id": None,
            "reason_codes": ["no_authenticated_host_wall_band", "universe_unproven"],
        },
        {
            "opening_identity_id": "opening-B", "page_id": "7",
            "status": "corroborated", "record_id": "binding-B",
            "host_wall_id": "wall-B", "reason_codes": ["opening_host_binding_resolved"],
        },
        {
            "opening_identity_id": "opening-C", "page_id": "7",
            "status": "corroborated", "record_id": "binding-C",
            "host_wall_id": "wall-C", "reason_codes": ["opening_host_binding_resolved"],
        },
    ]
    frames = [
        {
            "opening_identity_id": "opening-A", "status": "abstained",
            "record_id": None, "host_wall_id": None,
            "reason_codes": ["host_binding_record_unavailable"],
        },
        {
            "opening_identity_id": "opening-B", "status": "abstained",
            "record_id": None, "host_wall_id": None,
            "reason_codes": ["complete_whole_wall_unproven"],
        },
        {
            "opening_identity_id": "opening-C", "status": "corroborated",
            "record_id": "frame-C", "host_wall_id": "wall-C",
            "reason_codes": ["host_frame_resolved"],
        },
    ]
    composition = {
        "source_sha256": "a" * 64,
        "binding_count": 3, "binding_resolved_count": 2,
        "frame_count": 3, "frame_resolved_count": 1,
        "bindings": bindings, "frames": frames,
        "binding_reason_counts": {
            "no_authenticated_host_wall_band": 1, "universe_unproven": 1,
            "opening_host_binding_resolved": 2,
        },
        "frame_reason_counts": {
            "host_binding_record_unavailable": 1,
            "complete_whole_wall_unproven": 1,
            "host_frame_resolved": 1,
        },
    }
    return summary, composition


def test_true_first_stage_counts_preserve_one_opening_per_physical_identity():
    summary, composition = _inputs()
    report = build(summary, composition)
    assert report["first_unproved_stage_counts"] == {
        "HOST_BINDING_UNPROVEN": 1,
        "COMPLETE_HOST_FRAME_UNPROVEN": 1,
        "HOST_AND_FRAME_SOURCE_SUPPORTED_UNSCORED": 1,
    }
    assert report["opening_universe_size"] == 3
    assert report["host_bindings_source_resolved"] == 2
    assert report["frames_source_resolved"] == 1
    assert report["source_family_quantity_counts_unscored"]["opening_area"] == 0
    assert report["original_source_independently_verified"] is False
    assert report["benchmark_score_granted"] is False
    assert report["benchmark_accuracy"] is None
    assert report["frozen_v2_reconciliation_complete"] is False
    assert report["opening_first_stage_rows"][0]["first_stage_reason_codes"] == [
        "no_authenticated_host_wall_band", "universe_unproven",
    ]


@pytest.mark.parametrize("tamper", [
    "sha_mismatch", "duplicate_opening", "missing_frame", "different_universe",
    "false_binding_count", "false_resolved_count", "false_reason_counts",
    "frame_without_host", "wrong_host", "duplicate_reason", "nonfinite_count",
    "fake_accuracy", "not_core", "missing_source_sha",
])
def test_conflicting_source_evidence_rejected_without_score(tamper):
    summary, composition = _inputs()
    if tamper == "sha_mismatch":
        composition["source_sha256"] = "b" * 64
    elif tamper == "duplicate_opening":
        composition["bindings"].append(deepcopy(composition["bindings"][0]))
        composition["binding_count"] += 1
    elif tamper == "missing_frame":
        composition.pop("frames")
    elif tamper == "different_universe":
        composition["frames"][0]["opening_identity_id"] = "unrelated-opening"
    elif tamper == "false_binding_count":
        composition["binding_count"] = 4
    elif tamper == "false_resolved_count":
        composition["frame_resolved_count"] = 3
    elif tamper == "false_reason_counts":
        composition["binding_reason_counts"]["universe_unproven"] = 0
    elif tamper == "frame_without_host":
        composition["frames"][0].update(record_id="frame-forged", host_wall_id="wall-X")
        composition["frame_resolved_count"] = 2
    elif tamper == "wrong_host":
        composition["frames"][2]["host_wall_id"] = "wall-X"
    elif tamper == "duplicate_reason":
        composition["bindings"][0]["reason_codes"].append("universe_unproven")
    elif tamper == "nonfinite_count":
        summary["family_counts"]["floor_area"] = float("nan")
    elif tamper == "fake_accuracy":
        summary["benchmark_score_granted"] = True
    elif tamper == "not_core":
        summary["family_group"] = "all"
    elif tamper == "missing_source_sha":
        summary.pop("source_sha256")
    with pytest.raises(ValueError):
        build(summary, composition)


def test_row_permutation_does_not_change_source_first_stage_results():
    summary, composition = _inputs()
    original = build(summary, composition)
    composition["bindings"].reverse()
    composition["frames"].reverse()
    result = build(summary, composition)
    assert original == result


def test_absent_resolved_frame_never_becomes_success_when_producer_abstains():
    summary, composition = _inputs()
    for row in composition["frames"]:
        row["record_id"] = None
        row["host_wall_id"] = None
    composition["frame_resolved_count"] = 0
    composition["frame_reason_counts"] = {
        "host_binding_record_unavailable": 1,
        "complete_whole_wall_unproven": 1,
        "host_frame_resolved": 1,
    }
    report = build(summary, composition)
    assert report["frames_source_resolved"] == 0
    assert "HOST_AND_FRAME_SOURCE_SUPPORTED_UNSCORED" not in (
        report["first_unproved_stage_counts"]
    )
