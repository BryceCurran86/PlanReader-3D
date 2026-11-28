"""Focused tests for AG-R06/R08 cross-sheet floor-finish association & threshold continuity."""
from __future__ import annotations

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_floor_finish_threshold_continuity_shadow import (
    PlanRoomFinishOccurrenceWitness,
    RoomAdjacencyThresholdWitness,
    ScheduleFinishSpecWitness,
    ThresholdContinuityKind,
    canonicalize_finish_code,
    evaluate_cross_sheet_floor_finish_and_thresholds_shadow,
)

SHA = "b" * 64


def _spec(sid: str, code: str, desc: str, *, rev="rev1"):
    return ScheduleFinishSpecWitness(
        spec_id=sid,
        document_id="doc1",
        revision_id=rev,
        source_sha256=SHA,
        page_id="2",
        finish_code=code,
        material_description=desc,
    )


def _occ(oid: str, room: str, code: str, *, rev="rev1"):
    return PlanRoomFinishOccurrenceWitness(
        occurrence_id=oid,
        document_id="doc1",
        revision_id=rev,
        source_sha256=SHA,
        page_id="7",
        viewport_id="vp_plan",
        room_key=room,
        finish_code=code,
    )


def test_canonicalize_finish_code_normalizes_hyphen_and_leading_zeros() -> None:
    assert canonicalize_finish_code("FT-02") == "FT2"
    assert canonicalize_finish_code(" ft 003 ") == "FT3"
    assert canonicalize_finish_code("VNL-01A") == "VNL1A"


def test_cross_sheet_association_and_all_four_threshold_continuity_modes() -> None:
    specs = (
        _spec("s1", "FT-02", "Commercial Vinyl Sheet"),
        _spec("s2", "FT-03", "Slip-Resistant Ceramic Tile"),
    )
    occs = (
        _occ("o1", "ROOM_1", "FT2"),
        _occ("o2", "ROOM_2", "FT-02"),
        _occ("o3", "ROOM_3", "FT3"),
        _occ("o4", "ROOM_4", "FT-03"),
    )
    adjs = (
        RoomAdjacencyThresholdWitness("a_same", "ROOM_1", "ROOM_2"),
        RoomAdjacencyThresholdWitness("a_door", "ROOM_1", "ROOM_3", has_doorway_opening=True),
        RoomAdjacencyThresholdWitness(
            "a_open_line",
            "ROOM_2",
            "ROOM_3",
            has_explicit_finish_transition_line=True,
            transition_line_observation_ids=("obs_dash_1",),
        ),
        RoomAdjacencyThresholdWitness("a_open_none", "ROOM_2", "ROOM_4"),
    )
    res = evaluate_cross_sheet_floor_finish_and_thresholds_shadow(
        schedule_specs=specs, room_occurrences=occs, adjacencies=adjs,
    )
    assert res.shadow_only is True
    assert res.commercial_authority_granted is False
    assert len(res.associations) == 4
    assert all(a.status is EvidenceResolutionStatus.CORROBORATED for a in res.associations)

    by_adj = {d.adjacency_id: d for d in res.threshold_decisions}
    assert by_adj["a_same"].continuity_kind is ThresholdContinuityKind.CONTINUOUS_SAME_FINISH
    assert by_adj["a_same"].status is EvidenceResolutionStatus.CORROBORATED
    assert by_adj["a_door"].continuity_kind is ThresholdContinuityKind.THRESHOLD_TRANSITION_AT_DOORWAY
    assert by_adj["a_door"].status is EvidenceResolutionStatus.CORROBORATED
    assert by_adj["a_open_line"].continuity_kind is ThresholdContinuityKind.OPEN_PLAN_EXPLICIT_BOUNDARY_LINE
    assert by_adj["a_open_line"].status is EvidenceResolutionStatus.CORROBORATED
    assert by_adj["a_open_line"].transition_line_observation_ids == ("obs_dash_1",)
    # Never invents a boundary when open-plan finishes differ with no drawn line!
    assert by_adj["a_open_none"].continuity_kind is ThresholdContinuityKind.ABSTAINED_NO_EXPLICIT_THRESHOLD
    assert by_adj["a_open_none"].status is EvidenceResolutionStatus.ABSTAINED


def test_conflicting_specs_conflicting_room_codes_and_cross_revision_fail_closed() -> None:
    specs = (
        _spec("s1", "FT2", "Vinyl"),
        _spec("s2", "FT-02", "Epoxy"),  # conflict on same code!
        _spec("s3", "FT9", "Carpet", rev="rev_other"),  # cross-revision!
    )
    occs = (
        _occ("o1", "ROOM_CONFLICT_SPEC", "FT2"),
        _occ("o2", "ROOM_CROSS_REV", "FT9"),
        _occ("o3", "ROOM_TWO_CODES", "FT2"),
        _occ("o4", "ROOM_TWO_CODES", "FT9"),
    )
    res = evaluate_cross_sheet_floor_finish_and_thresholds_shadow(
        schedule_specs=specs, room_occurrences=occs,
    )
    by_room = {a.room_key: a for a in res.associations}
    assert by_room["ROOM_CONFLICT_SPEC"].status is EvidenceResolutionStatus.CONFLICT
    assert by_room["ROOM_CROSS_REV"].status is EvidenceResolutionStatus.ABSTAINED
    assert by_room["ROOM_TWO_CODES"].status is EvidenceResolutionStatus.CONFLICT
