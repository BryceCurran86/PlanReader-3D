"""First-failure ledger adversarial source-only checks; never asserts a count."""
from copy import deepcopy

import pytest

from tools.gptmax_source_first_failure_ledger import build_first_failure_ledger


SHA = "1" * 64


def report():
    return {
        "source_sha256": SHA,
        "selected_geometry_page_ids": ["3"],
        "all_source_pages_requested": True,
        "primitive_safety_cap": 20000,
        "summary": {"physical_existence_claims": 4, "authenticated_hosts": 2,
                    "resolved_source_frames": 1},
        "opening_bindings": [
            {"opening_identity_id": "c", "status": "corroborated",
             "page_id": "3", "host_wall_id": "wall-c",
             "record_id": "host-c", "reason_codes": []},
            {"opening_identity_id": "a", "status": "abstained",
             "page_id": "3", "host_wall_id": None, "record_id": None,
             "reason_codes": ["raster_source_band_left_source_primitive_unmapped"]},
            {"opening_identity_id": "d", "status": "conflict",
             "page_id": "3", "host_wall_id": None, "record_id": None,
             "reason_codes": ["ambiguous_physical_wall_equivalence_for_host"]},
            {"opening_identity_id": "b", "status": "corroborated",
             "page_id": "3", "host_wall_id": "wall-b", "record_id": "host-b",
             "reason_codes": []},
        ],
        "host_frame_traces": [
            {"opening_identity_id": "a", "record_id": None,
             "reason_codes": ["opening_host_frame_wall_unavailable"]},
            {"opening_identity_id": "b", "record_id": "frame-b",
             "reason_codes": []},
            {"opening_identity_id": "c", "record_id": None,
             "reason_codes": ["opening_host_frame_connected_edge_unproven"]},
            {"opening_identity_id": "d", "record_id": None,
             "reason_codes": ["opening_host_frame_wall_unavailable"]},
        ],
        "raster_candidate_closures": [
            {"page_id": "3", "raw_candidate_count": 30,
             "resolved_candidate_count": 21,
             "candidate_universe_complete": False,
             "unresolved_candidate_ids": ["raw9", "raw8"],
             "unresolved_observation_ids": ["source1", "source2"],
             "reason_codes": ["physical_opening_candidate_closure_unresolved"]}
        ],
    }


def test_four_authority_gates_are_separate_from_raw_raster():
    data=build_first_failure_ledger(report())
    assert data["physical_opening_source_identity_count"] == 4
    assert data["authenticated_host_receipt_count"] == 2
    assert data["authenticated_frame_receipt_count"] == 1
    assert data["first_unresolved_stage_counts"] == {
        "DOWNSTREAM_WITNESS_AND_COUNT_UNVERIFIED": 1,
        "HOST_AUTHORITY_UNRESOLVED": 1,
        "HOST_EQUIVALENCE_CONFLICT": 1,
        "HOST_FRAME_GEOMETRY_UNRESOLVED": 1,
    }
    c=data["registered_raster_candidate_family"]
    assert c["total_registered_raw_candidates"] == 30
    assert c["total_resolved_raw_candidates"] == 21
    assert c["unresolved_raw_candidate_ids"] == ["raw8", "raw9"]
    assert data["raw_candidate_to_physical_identity_join"] == "UNPROVEN_NOT_ATTEMPTED"
    assert data["whole_building_opening_universe_complete"] is False
    assert not data["count_quantity_publication_allowed"]
    assert data["frozen_benchmark_reconciliation"] is None


def test_order_is_not_identity_and_source_is_not_mutated():
    x=report()
    y=deepcopy(x)
    y["opening_bindings"].reverse()
    y["host_frame_traces"].reverse()
    y["raster_candidate_closures"][0]["unresolved_candidate_ids"].reverse()
    result1=build_first_failure_ledger(x)
    result2=build_first_failure_ledger(y)
    assert result1 == result2
    assert x == report()


@pytest.mark.parametrize("damage", [
    "source_sha", "primitive_cap", "physical_duplicate", "frame_duplicate",
    "frame_missing", "summary_hosts", "summary_frames", "summary_openings",
    "frame_without_host", "host_without_receipt", "host_without_wall",
    "bad_host_reasons", "bad_frame_reasons", "physical_wrong_page", "frame_wrong_page",
])
def test_malformed_source_evidence_fails_closed(damage):
    x=report()
    if damage=="source_sha": x["source_sha256"] = "not-a-sha"
    elif damage=="primitive_cap": x["primitive_safety_cap"] = 20001
    elif damage=="physical_duplicate": x["opening_bindings"].append(deepcopy(x["opening_bindings"][0]))
    elif damage=="frame_duplicate": x["host_frame_traces"].append(deepcopy(x["host_frame_traces"][0]))
    elif damage=="frame_missing": x["host_frame_traces"].pop()
    elif damage=="summary_hosts": x["summary"]["authenticated_hosts"] = 3
    elif damage=="summary_frames": x["summary"]["resolved_source_frames"] = 2
    elif damage=="summary_openings": x["summary"]["physical_existence_claims"] = 3
    elif damage=="frame_without_host": x["host_frame_traces"][0]["record_id"] = "false-frame"
    elif damage=="host_without_receipt": x["opening_bindings"][0]["record_id"] = None
    elif damage=="host_without_wall": x["opening_bindings"][0]["host_wall_id"] = None
    elif damage=="bad_host_reasons": x["opening_bindings"][0]["reason_codes"] = [False]
    elif damage=="bad_frame_reasons": x["host_frame_traces"][0]["reason_codes"] = None
    elif damage=="physical_wrong_page": x["opening_bindings"][0]["page_id"] = "8"
    elif damage=="frame_wrong_page": x["host_frame_traces"][0]["page_id"] = "8"
    with pytest.raises(ValueError):
        build_first_failure_ledger(x)


@pytest.mark.parametrize("damage", [
    "bad_raw", "bad_resolved", "closure_false_claim", "duplicate_id",
    "unknown_page", "candidate_array", "negative_raw", "missing_page",
])
def test_raster_closure_cannot_certify_incomplete_source(damage):
    x=report()
    c=x["raster_candidate_closures"][0]
    if damage=="bad_raw": c["raw_candidate_count"]=True
    elif damage=="bad_resolved": c["resolved_candidate_count"]=40
    elif damage=="closure_false_claim": c["candidate_universe_complete"]=True
    elif damage=="duplicate_id": c["unresolved_candidate_ids"]=["raw9","raw9"]
    elif damage=="unknown_page": c["page_id"]="4"
    elif damage=="candidate_array": x["raster_candidate_closures"]="not an array"
    elif damage=="negative_raw": c["raw_candidate_count"]=-1
    else: c["page_id"]=None
    with pytest.raises(ValueError):
        build_first_failure_ledger(x)


def test_missing_raster_audit_is_not_empty_or_complete():
    x=report()
    x["raster_candidate_closures"]=None
    result=build_first_failure_ledger(x)
    assert result["registered_raster_candidate_family"]["available"] is False
    assert result["registered_raster_candidate_family"]["total_registered_raw_candidates"] is None
    assert not result["whole_building_opening_universe_complete"]


def test_even_closed_registered_detector_family_is_not_count_completeness():
    x=report()
    x["raster_candidate_closures"][0].update(raw_candidate_count=21,
        resolved_candidate_count=21, candidate_universe_complete=True,
        unresolved_candidate_ids=[], unresolved_observation_ids=[],
        reason_codes=["registered_family_closure_only"])
    result=build_first_failure_ledger(x)
    assert result["registered_raster_candidate_family"]["registered_candidate_complete"]
    assert result["whole_building_opening_universe_complete"] is False
    assert not result["count_quantity_publication_allowed"]
