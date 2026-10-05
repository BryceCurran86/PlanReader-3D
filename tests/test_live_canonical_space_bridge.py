from __future__ import annotations

from pb_canonical_building import ObjectType, ReviewState
from pb_live_canonical_room_composition import (
    LIVE_CANONICAL_ROOM_RESOLVED,
    LiveCanonicalRoomComposition,
    LiveCanonicalRoomObject,
)
from pb_live_canonical_space_bridge import (
    LIVE_CANONICAL_SPACE_BRIDGE_PARTIAL,
    LIVE_CANONICAL_SPACE_BRIDGE_RESOLVED,
    LIVE_CANONICAL_SPACE_BRIDGE_UNAVAILABLE,
    compose_live_canonical_spaces,
)
from pb_migration_contracts import EvidenceResolutionStatus


def _room(*, label: str | None = "OFFICE") -> LiveCanonicalRoomObject:
    return LiveCanonicalRoomObject(
        canonical_room_id="live_physical_room_abc",
        physical_room_id="live_physical_room_abc",
        document_id="logical-doc",
        revision_id="revision-1",
        source_sha256="a" * 64,
        snapshot_id="snapshot-1",
        page_id="7",
        viewport_id="floor-plan-vp",
        decision_scope_id="wall-source:viewport:7:floor-plan-vp",
        polygon_pdf_pts=(
            (10.0, 10.0),
            (20.0, 10.0),
            (20.0, 20.0),
            (10.0, 20.0),
        ),
        bounding_wall_ids=("w1", "w2", "w3", "w4"),
        canonical_bounding_wall_ids=("cw1", "cw2", "cw3", "cw4"),
        wall_relationships_complete=True,
        area_page_pts2=100.0,
        source_room_face_record_id="source-room-face-record",
        evidence_ids=("source-room-face-record",),
        geometry_complete=True,
        metric_geometry_complete=False,
        room_label=label,
        room_label_binding_record_id=(
            "source-room-label-record" if label else None
        ),
        room_label_evidence_ids=(
            ("source-word-observation",) if label else ()
        ),
        room_label_reason_codes=(
            ("source_room_label_resolved",)
            if label
            else ("source_room_label_unavailable",)
        ),
    )


def test_live_room_adapts_to_existing_canonical_space_fail_closed() -> None:
    room = _room()
    composition = LiveCanonicalRoomComposition(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(LIVE_CANONICAL_ROOM_RESOLVED,),
        rooms=(room,),
        source_pages=(7,),
    )

    result = compose_live_canonical_spaces(composition)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (LIVE_CANONICAL_SPACE_BRIDGE_RESOLVED,)
    assert len(result.spaces) == 1
    space = result.spaces[0]
    assert space.id == room.canonical_room_id
    assert space.object_type is ObjectType.SPACE
    assert space.name == "OFFICE"
    assert space.review_state is ReviewState.INFERRED
    assert space.takeoff_eligible is False
    assert space.deduction_authority is False

    # Page points are retained as source provenance, never relabelled as metres.
    assert space.boundary_polygon == []
    assert space.height_m is None
    assert space.specified_floor_area_m2 is None
    assert space.provenance.coordinate_space == "source_page_points"
    assert space.provenance.page_number == 7
    assert space.provenance.source_coords["polygon_pdf_pts"] == [
        [10.0, 10.0],
        [20.0, 10.0],
        [20.0, 20.0],
        [10.0, 20.0],
    ]
    assert space.metadata["physical_room_id"] == room.physical_room_id
    assert space.metadata["source_room_face_record_id"] == (
        room.source_room_face_record_id
    )
    assert set(space.provenance.contributing_evidence) == {
        "source-room-face-record",
        "source-word-observation",
    }


def test_partial_room_universe_yields_review_required_space() -> None:
    composition = LiveCanonicalRoomComposition(
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=("live_canonical_room_composition_partial",),
        rooms=(_room(label=None),),
        source_pages=(7,),
    )

    result = compose_live_canonical_spaces(composition)

    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.reason_codes[0] == LIVE_CANONICAL_SPACE_BRIDGE_PARTIAL
    assert len(result.spaces) == 1
    assert result.spaces[0].review_state is ReviewState.REVIEW_REQUIRED
    assert result.spaces[0].name == "Unnamed Element"
    assert result.spaces[0].boundary_polygon == []


def test_no_room_geometry_creates_no_canonical_space() -> None:
    composition = LiveCanonicalRoomComposition(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=("live_canonical_room_composition_unavailable",),
        rooms=(),
        source_pages=(),
    )

    result = compose_live_canonical_spaces(composition)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (LIVE_CANONICAL_SPACE_BRIDGE_UNAVAILABLE,)
    assert result.spaces == ()
