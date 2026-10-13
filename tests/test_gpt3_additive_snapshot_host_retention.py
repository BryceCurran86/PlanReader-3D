from copy import deepcopy

import pytest

from tools.verify_gpt3_additive_snapshot_host_retention import (
    compare_additive_snapshot_retention,
)

OLD = "physical_opening_existence_old"
TARGET = "physical_opening_existence_target"
SHA = "a" * 64


def _wall(wall_id, candidate_id, source_id):
    return {
        "wall_candidate_id": wall_id,
        "physical_identity": {
            "candidate_identity_id": candidate_id,
            "source_primitive_ids": [source_id],
            "edge_ids": [f"edge:{wall_id}"],
        },
    }


def _binding(opening_id, *, hosted, wall_id=None, receipt="old"):
    return {
        "opening_identity_id": opening_id,
        "representative_observation_id": f"obs:{opening_id}",
        "page_id": "3",
        "status": "corroborated" if hosted else "abstained",
        "reason_codes": (
            ["opening_host_binding_resolved", "raster_source_band_host_resolved"]
            if hosted
            else ["no_authenticated_host_wall_band"]
        ),
        "record_id": f"binding:{receipt}:{opening_id}" if hosted else None,
        "host_wall_id": f"host:{receipt}:{opening_id}" if hosted else None,
        "member_wall_candidate_ids": [wall_id] if hosted else [],
    }


def _frame(opening_id, wall_id, *, receipt="old", u1=2.0):
    return {
        "selector": {
            "snapshot_id": f"snapshot:{receipt}",
            "opening_identity_id": opening_id,
        },
        "record_id": f"frame-record:{receipt}:{opening_id}",
        "opening_identity_id": opening_id,
        "host_binding_record_id": f"binding:{receipt}:{opening_id}",
        "host_wall_id": f"host:{receipt}:{opening_id}",
        "whole_wall_frame_id": f"whole-frame:{receipt}:{opening_id}",
        "whole_wall_candidate_ids": [wall_id],
        "source_observation_ids": [f"source:{wall_id}"],
        "origin_pt": [0.0, 0.0],
        "axis_unit": [1.0, 0.0],
        "normal_unit": [0.0, 1.0],
        "u0_pt": 0.5,
        "u1_pt": u1,
        "wall_thickness_pt": 0.2,
        "whole_wall_length_pt": 4.0,
        "coordinate_unit": "pdf_point",
    }


def _report(*, candidate=False):
    old_wall = _wall("wall-old", "wall2_old", "source:wall-old")
    target_wall = _wall("wall-target", "wall2_target", "source:wall-target")
    report = {
        "source_sha256": SHA,
        "revision_id": "revision-1",
        "selected_geometry_page_ids": ["3"],
        "primitive_safety_cap": 20_000,
        "canonical_openings": [
            {
                "physical_opening_id": OLD,
                "document_id": "document-1",
                "page_id": "3",
            },
            {
                "physical_opening_id": TARGET,
                "document_id": "document-1",
                "page_id": "3",
            },
        ],
        "source_owned_wall_scopes": [
            {"records": [old_wall, target_wall]},
        ],
        "opening_bindings": [
            _binding(OLD, hosted=True, wall_id="wall-old",
                     receipt="new" if candidate else "old"),
            _binding(
                TARGET,
                hosted=candidate,
                wall_id="wall-target" if candidate else None,
                receipt="new",
            ),
        ],
        "resolved_host_frame_evidence": [
            _frame(OLD, "wall-old", receipt="new" if candidate else "old"),
        ],
    }
    if candidate:
        report["resolved_host_frame_evidence"].append(
            _frame(TARGET, "wall-target", receipt="new")
        )
    return report


def test_snapshot_scoped_receipt_rekey_is_allowed_only_when_source_physics_match():
    result = compare_additive_snapshot_retention(
        _report(),
        _report(candidate=True),
        expected_new_host_ids=(TARGET,),
    )
    assert result["additive_snapshot_rekey_only"] is True
    assert result["baseline_host_count"] == 1
    assert result["candidate_host_count"] == 2
    assert result["baseline_frame_count"] == 1
    assert result["candidate_frame_count"] == 2
    assert result["new_host_ids"] == [TARGET]
    assert result["new_frame_ids"] == [TARGET]
    assert result["host_publication_granted_by_checker"] is False
    assert result["benchmark_score_granted_by_checker"] is False


@pytest.mark.parametrize(
    "mutation, message",
    [
        ("candidate_identity", "physical host/source proposition changed"),
        ("source_primitive", "physical host/source proposition changed"),
        ("edge", "physical host/source proposition changed"),
        ("frame_geometry", "physical frame/source geometry changed"),
        ("lost_frame", "previously resolved host frame was lost"),
        ("extra_host", "host population changed outside"),
        ("physical_opening", "physical opening identity universe changed"),
    ],
)
def test_any_non_rekey_source_or_geometry_change_fails_closed(mutation, message):
    before = _report()
    after = _report(candidate=True)
    if mutation == "candidate_identity":
        after["source_owned_wall_scopes"][0]["records"][0]["physical_identity"][
            "candidate_identity_id"
        ] = "wall2_different"
    elif mutation == "source_primitive":
        after["source_owned_wall_scopes"][0]["records"][0]["physical_identity"][
            "source_primitive_ids"
        ] = ["source:different"]
    elif mutation == "edge":
        after["source_owned_wall_scopes"][0]["records"][0]["physical_identity"][
            "edge_ids"
        ] = ["edge:different"]
    elif mutation == "frame_geometry":
        after["resolved_host_frame_evidence"][0]["u1_pt"] = 2.1
    elif mutation == "lost_frame":
        after["resolved_host_frame_evidence"] = after["resolved_host_frame_evidence"][1:]
    elif mutation == "extra_host":
        extra = "physical_opening_existence_extra"
        before["canonical_openings"].append(
            {"physical_opening_id": extra, "document_id": "document-1", "page_id": "3"}
        )
        after["canonical_openings"].append(
            {"physical_opening_id": extra, "document_id": "document-1", "page_id": "3"}
        )
        before["opening_bindings"].append(_binding(extra, hosted=False))
        after["opening_bindings"].append(
            _binding(extra, hosted=True, wall_id="wall-old", receipt="new")
        )
    else:
        after["opening_bindings"].pop()
        after["canonical_openings"].pop()

    with pytest.raises(ValueError, match=message):
        compare_additive_snapshot_retention(
            before,
            after,
            expected_new_host_ids=(TARGET,),
        )


def test_unrelated_unhosted_authority_cannot_change_during_additive_recovery():
    before = _report()
    after = _report(candidate=True)
    other = "physical_opening_existence_other"
    for report in (before, after):
        report["canonical_openings"].append(
            {"physical_opening_id": other, "document_id": "document-1", "page_id": "3"}
        )
        report["opening_bindings"].append(_binding(other, hosted=False))
    after["opening_bindings"][-1]["reason_codes"] = ["different_failure"]

    with pytest.raises(ValueError, match="unrelated opening authority changed"):
        compare_additive_snapshot_retention(
            before,
            after,
            expected_new_host_ids=(TARGET,),
        )


def test_expected_new_figured_area_host_may_honestly_remain_frame_abstain():
    before = _report()
    after = _report(candidate=True)
    after["resolved_host_frame_evidence"] = [
        row for row in after["resolved_host_frame_evidence"]
        if row["opening_identity_id"] != TARGET
    ]
    result = compare_additive_snapshot_retention(
        before,
        after,
        expected_new_host_ids=(TARGET,),
    )
    assert result["new_host_ids"] == [TARGET]
    assert result["new_frame_ids"] == []
    assert result["baseline_frame_count"] == result["candidate_frame_count"] == 1
