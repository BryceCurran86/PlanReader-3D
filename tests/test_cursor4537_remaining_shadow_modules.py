"""Focused tests for Cursor-07..10 shadow modules (#4537)."""
from __future__ import annotations

from pb_source_finished_interior_face_recovery_shadow import (
    recover_finished_interior_face_candidates,
)
from pb_source_native_live_trace_diagnostics_shadow import (
    build_source_native_live_trace_diagnostics,
)
from pb_source_opening_host_correlation_index_shadow import (
    build_opening_host_correlation_index,
    lookup_hosts_for_opening,
    lookup_openings_for_host,
)
from pb_source_open_plan_room_ring_shadow import audit_open_plan_room_rings
from pb_migration_contracts import EvidenceResolutionStatus
from pb_layered_wall_doorway_room_ring_shadow import LayeredRoomRingResult


def test_finished_face_false_wall_thickness_veto():
    drawings = [
        {"layer": "WallInternal", "rect": (0.0, 0.0, 40.0, 0.02)},
        {"layer": "WallInternal", "rect": (0.0, 20.0, 40.0, 20.02)},
    ]
    words = ((10.0, 8.0, 30.0, 12.0, "BED", 0, 0, 0), (31.0, 8.0, 40.0, 12.0, "2", 0, 0, 0))
    rows = recover_finished_interior_face_candidates(
        drawings, words, room_labels=("BED 2",), min_thickness_pt=1.5,
    )
    assert len(rows) == 1
    assert rows[0].status == "ABSTAINED"
    assert rows[0].reason == "false_wall_thickness_veto"


def test_finished_face_unique_label_with_positive_thickness():
    drawings = [
        {"layer": "WallInternal", "rect": (0.0, 0.0, 40.0, 4.0)},
        {"layer": "WallInternal", "rect": (0.0, 30.0, 40.0, 34.0)},
        {"layer": "Annotation_Dimensions", "rect": (5.0, 5.0, 8.0, 8.0)},
    ]
    words = ((10.0, 14.0, 30.0, 18.0, "WIR", 0, 0, 0),)
    rows = recover_finished_interior_face_candidates(
        drawings, words, room_labels=("WIR",),
    )
    assert rows[0].status == "CANDIDATE"
    assert rows[0].thickness_pt is not None and rows[0].thickness_pt >= 1.5
    assert rows[0].physical_face_authenticated is False


def test_open_plan_audit_no_invented_partitions():
    stub = LayeredRoomRingResult(
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=("layered_wall_ring_closed_by_source_ink",),
        rings=(),
        closures=(),
        wall_strip_count=0,
        wall_gap_count=0,
        unresolved_gap_count=0,
        non_strip_wall_fill_count=0,
        unplaced_swing_count=0,
        ambiguous_swing_count=0,
    )
    audit = audit_open_plan_room_rings(
        [],
        source_sha256="a" * 64,
        page_index=0,
        ring_result=stub,
    )
    assert audit.status == "CANDIDATE"
    assert audit.invented_partition_count == 0
    assert audit.to_dict()["commercial_publishable"] is False


def test_opening_host_index_lookups_and_duplicate_abstain():
    index = build_opening_host_correlation_index(
        [
            {"opening_id": "o1", "host_path_ids": (10, 11)},
            {"opening_id": "o2", "host_path_ids": (11, 12)},
        ]
    )
    assert index.status == "CANDIDATE"
    assert lookup_openings_for_host(index, 11) == ("o1", "o2")
    assert lookup_hosts_for_opening(index, "o1") == (10, 11)
    dup = build_opening_host_correlation_index(
        [
            {"opening_id": "o1", "host_path_ids": (1,)},
            {"opening_id": "o1", "host_path_ids": (2,)},
        ]
    )
    assert dup.status == "ABSTAINED"


def test_live_trace_diagnostics_non_commercial():
    diag = build_source_native_live_trace_diagnostics(
        page_index=2,
        source_sha256="b" * 64,
        room_candidate_count=3,
    )
    payload = diag.to_dict()
    assert payload["visual_output_non_commercial"] is True
    assert payload["commercial_publishable"] is False
    assert payload["color_legend"]["outside_walls"] == "red"
