"""Pure fail-closed audit of before/after G17 source publication consequences."""
from __future__ import annotations

from copy import deepcopy

import pytest

from tools.diag_gptmax_g17_nomination_retention import (
    audit_g17_nomination_retention as audit,
)


def source():
    return {
        "source_sha256": "a" * 64,
        "primitive_safety_cap": 20_000,
        "snapshot_id": "original",
        "opening_bindings": [
            {"opening_identity_id": "a", "host_wall_id": "old-host",
             "record_id": "old-record", "member_wall_candidate_ids": ["w1", "w2"]},
            {"opening_identity_id": "b", "host_wall_id": None, "record_id": None,
             "member_wall_candidate_ids": []},
        ],
        "host_frame_traces": [
            {"opening_identity_id": "a", "host_wall_id": "old-host",
             "record_id": "old-frame"},
            {"opening_identity_id": "b", "host_wall_id": None, "record_id": None},
        ],
        "canonical_openings": [
            {"canonical_opening_id": "a", "area_m2": 2.16,
             "evidence_ids": ["old-record", "old-frame"]},
            {"canonical_opening_id": "b", "area_m2": None, "evidence_ids": []},
        ],
        "source_owned_wall_scopes": [{"page_id": "3", "records": [
            {"wall_candidate_id": "w1", "geometry": [1, 2, 3, 4]},
            {"wall_candidate_id": "w2", "geometry": [5, 6, 7, 8]},
        ]}],
        "source_room_face_scopes": [{"result": {"records": ["physical-face"]}}],
    }


def test_identical_original_reports_are_only_an_audit_and_never_promotion():
    x = source()
    result = audit(x, deepcopy(x))
    assert result["new_candidate_host_ids"] == []
    assert result["changed_existing_host_receipt_ids"] == []
    assert result["changed_existing_frame_receipt_ids"] == []
    assert result["changed_w4_record_ids"] == []
    assert result["source_authority_changed"] is False
    assert result["physical_host_granted"] is False
    assert result["customer_quantity_granted"] is False
    assert result["benchmark_score_granted"] is False
    assert result["ready_for_production_promotion"] is False


def test_authentic_potential_host_gain_does_not_hide_rekeyed_existing_receipts():
    old = source()
    new = deepcopy(old)
    new["snapshot_id"] = "new"
    new["opening_bindings"][0].update(host_wall_id="changed-host", record_id="changed-record")
    new["opening_bindings"][1].update(host_wall_id="new-host", record_id="new-record",
                                      member_wall_candidate_ids=["w1", "w2"])
    new["host_frame_traces"][0].update(host_wall_id="changed-host", record_id="changed-frame")
    new["canonical_openings"][0]["evidence_ids"] = ["changed-record", "changed-frame"]
    new["source_room_face_scopes"][0]["result"]["records"] = ["changed-physical-face"]
    report = audit(old, new)
    assert report["baseline_authenticated_host_count"] == 1
    assert report["candidate_authenticated_host_count"] == 2
    assert report["new_candidate_host_ids"] == ["b"]
    assert report["changed_existing_host_receipt_ids"] == ["a"]
    assert report["changed_existing_frame_receipt_ids"] == ["a"]
    assert report["changed_existing_canonical_area_evidence_ids"] == ["a"]
    assert report["changed_existing_canonical_area_value_ids"] == []
    assert report["changed_w4_record_ids"] == []
    assert report["room_scope_changed"] is True
    assert report["source_authority_changed"] is True
    assert report["ready_for_production_promotion"] is False
    assert report["customer_quantity_granted"] is False
    assert old["opening_bindings"][0]["record_id"] == "old-record"


@pytest.mark.parametrize("damage", [
    "foreign_source", "different_safety_bound", "duplicate_physical_opening",
    "missing_frame", "duplicate_w4", "missing_room", "different_canonical_universe",
])
def test_conflicting_or_incomplete_source_fails_closed(damage):
    old, new = source(), source()
    if damage == "foreign_source":
        new["source_sha256"] = "b" * 64
    elif damage == "different_safety_bound":
        new["primitive_safety_cap"] = 10_000
    elif damage == "duplicate_physical_opening":
        new["opening_bindings"].append(deepcopy(new["opening_bindings"][0]))
    elif damage == "missing_frame":
        new["host_frame_traces"] = []
    elif damage == "duplicate_w4":
        new["source_owned_wall_scopes"][0]["records"].append(
            deepcopy(new["source_owned_wall_scopes"][0]["records"][0]))
    elif damage == "missing_room":
        new["source_room_face_scopes"] = []
    else:
        new["canonical_openings"][0]["canonical_opening_id"] = "impostor"
    with pytest.raises(ValueError):
        audit(old, new)


def test_existing_quantity_value_mutation_is_reported_not_accepted():
    old, new = source(), source()
    new["canonical_openings"][0]["area_m2"] = 9.99
    report = audit(old, new)
    assert report["changed_existing_canonical_area_value_ids"] == ["a"]
    assert report["customer_quantity_granted"] is False
    assert report["source_authority_changed"] is True
