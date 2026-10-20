"""Tests for producer-owned Maryborough physical room boundary shadow authority (Items 11 & 13)."""
from __future__ import annotations

import pytest
from shapely import wkb

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_maryborough_physical_room_boundary_shadow import (
    ITEM_11_ROOMS,
    ITEM_13_ROOMS,
    ROOM_AIRLOCK,
    ROOM_BOUNDARY_NOT_CLOSED,
    ROOM_DOOR_TRANSITION_MISSING,
    ROOM_F_AMB,
    ROOM_FOOD_PREP,
    ROOM_FREEZER,
    ROOM_INVALID_GEOMETRY,
    ROOM_LAUNDRY,
    ROOM_M_AMB,
    ROOM_OFFICE,
    ROOM_PWD,
    ROOM_SCALE_NOT_CORROBORATED,
    ROOM_WALL_DEFECT_REMAINS,
    ROOM_WASH_UP,
    SOURCE_ROOM_BOUNDARY_CANDIDATE,
    SOURCE_ROOM_BOUNDARY_RESOLVED,
    SOURCE_ROOM_BOUNDARY_UNAVAILABLE,
    SourceMaryboroughPhysicalRoomBoundaryAuthority,
    SourceMaryboroughPhysicalRoomBoundaryProducer,
    SourceMaryboroughPhysicalRoomRecord,
    SourceMaryboroughPhysicalRoomSelector,
    normalize_room_name,
)


def _make_selector(
    *,
    doc="doc-maryborough",
    rev="rev-01",
    sha="a" * 64,
    snap="snap-01",
    page="7",
    name="OFFICE",
) -> SourceMaryboroughPhysicalRoomSelector:
    return SourceMaryboroughPhysicalRoomSelector(
        document_id=doc,
        revision_id=rev,
        source_sha256=sha,
        snapshot_id=snap,
        page_id=page,
        room_name=name,
    )


def test_sealing_raises_permission_error():
    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceMaryboroughPhysicalRoomBoundaryProducer(object())

    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceMaryboroughPhysicalRoomBoundaryAuthority(object(), {})

    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceMaryboroughPhysicalRoomRecord(
            record_id="rec-1",
            document_id="doc",
            revision_id="rev",
            source_sha256="sha",
            snapshot_id="snap",
            page_id="7",
            room_name="OFFICE",
            room_key="OFFICE",
            workstream_item="Item 11",
            boundary_pts=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)),
            area_pt2=100.0,
            area_m2=4.0,
            perimeter_m=8.0,
            floor_finish_code="FT3",
            associated_door_ids=("D07",),
            wall_face_segment_ids=("w1", "w2", "w3", "w4"),
            wkb_hex=None,
            reason_codes=(),
        )


def test_name_normalization():
    assert normalize_room_name("M-AMB") == "M_AMB"
    assert normalize_room_name("F-AMB") == "F_AMB"
    assert normalize_room_name("WASH UP") == "WASH_UP"
    assert normalize_room_name("FOOD PREP") == "FOOD_PREP"
    assert normalize_room_name("office") == "OFFICE"
    assert normalize_room_name("  Air-Lock  ") == "AIR_LOCK"


def test_positive_item_11_rooms_boundary_recovery():
    producer = SourceMaryboroughPhysicalRoomBoundaryProducer.create()

    # Room 1: OFFICE (with door D07 chord at bottom wall from x=20 to x=35)
    office_pts = ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0))
    producer.register_room_boundary(
        document_id="doc-maryborough",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="7",
        room_name="OFFICE",
        boundary_pts=office_pts,
        wall_face_segment_ids=("wf-office-n", "wf-office-e", "wf-office-s", "wf-office-w"),
        associated_door_ids=("D07",),
        door_chords=(((20.0, 0.0), (35.0, 0.0)),),
        floor_finish_code="CARPET",
        scale_px_per_m=50.0,
    )

    # Room 2: FREEZER (with freezer door chord)
    freezer_pts = ((150.0, 0.0), (250.0, 0.0), (250.0, 80.0), (150.0, 80.0))
    producer.register_room_boundary(
        document_id="doc-maryborough",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="7",
        room_name="FREEZER",
        boundary_pts=freezer_pts,
        wall_face_segment_ids=("wf-frz-1", "wf-frz-2", "wf-frz-3", "wf-frz-4"),
        associated_door_ids=("D_FRZ",),
        door_chords=(((150.0, 10.0), (150.0, 25.0)),),
        floor_finish_code="FT3",
        scale_px_per_m=50.0,
    )

    authority = producer.authority()

    res_off = authority.resolve(_make_selector(name="OFFICE"))
    assert res_off.status == EvidenceResolutionStatus.CORROBORATED.value
    assert SOURCE_ROOM_BOUNDARY_RESOLVED in res_off.reason_codes
    assert res_off.records[0].workstream_item == "Item 11"
    assert res_off.records[0].area_m2 == 4.0  # 10000 / 2500 = 4 m2
    assert res_off.records[0].associated_door_ids == ("D07",)

    res_frz = authority.resolve(_make_selector(name="FREEZER"))
    assert res_frz.status == EvidenceResolutionStatus.CORROBORATED.value
    assert res_frz.records[0].workstream_item == "Item 11"
    assert res_frz.records[0].area_m2 == 3.2  # 8000 / 2500 = 3.2 m2


def test_positive_item_13_rooms_boundary_recovery():
    producer = SourceMaryboroughPhysicalRoomBoundaryProducer.create()

    # M-AMB (with D12 door chord)
    m_amb_pts = ((0.0, 0.0), (50.0, 0.0), (50.0, 80.0), (0.0, 80.0))
    producer.register_room_boundary(
        document_id="doc-maryborough",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="7",
        room_name="M-AMB",
        boundary_pts=m_amb_pts,
        wall_face_segment_ids=("w-m-1", "w-m-2", "w-m-3", "w-m-4"),
        associated_door_ids=("D12",),
        door_chords=(((10.0, 0.0), (25.0, 0.0)),),
        floor_finish_code="FT2",
        scale_px_per_m=50.0,
    )

    # F-AMB (with D11 door chord)
    f_amb_pts = ((50.0, 0.0), (100.0, 0.0), (100.0, 80.0), (50.0, 80.0))
    producer.register_room_boundary(
        document_id="doc-maryborough",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="7",
        room_name="F-AMB",
        boundary_pts=f_amb_pts,
        wall_face_segment_ids=("w-f-1", "w-f-2", "w-f-3", "w-f-4"),
        associated_door_ids=("D11",),
        door_chords=(((60.0, 0.0), (75.0, 0.0)),),
        floor_finish_code="FT2",
        scale_px_per_m=50.0,
    )

    # LAUNDRY (with D10 door chord)
    laundry_pts = ((120.0, 0.0), (180.0, 0.0), (180.0, 90.0), (120.0, 90.0))
    producer.register_room_boundary(
        document_id="doc-maryborough",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="7",
        room_name="LAUNDRY",
        boundary_pts=laundry_pts,
        wall_face_segment_ids=("w-l-1", "w-l-2", "w-l-3", "w-l-4"),
        associated_door_ids=("D10",),
        door_chords=(((130.0, 0.0), (145.0, 0.0)),),
        floor_finish_code="FT2",
        scale_px_per_m=50.0,
    )

    authority = producer.authority()

    res_m = authority.resolve(_make_selector(name="M-AMB"))
    assert res_m.status == EvidenceResolutionStatus.CORROBORATED.value
    assert res_m.records[0].workstream_item == "Item 13"
    assert res_m.records[0].room_key == "M_AMB"

    res_f = authority.resolve(_make_selector(name="F-AMB"))
    assert res_f.status == EvidenceResolutionStatus.CORROBORATED.value
    assert res_f.records[0].workstream_item == "Item 13"
    assert res_f.records[0].room_key == "F_AMB"

    res_l = authority.resolve(_make_selector(name="LAUNDRY"))
    assert res_l.status == EvidenceResolutionStatus.CORROBORATED.value
    assert res_l.records[0].workstream_item == "Item 13"
    assert res_l.records[0].associated_door_ids == ("D10",)


def test_door_chord_discontinuous_fails_defect():
    producer = SourceMaryboroughPhysicalRoomBoundaryProducer.create()
    pts = ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0))
    # Door chord floating far away from the room boundary (offset > 2.5 pt)
    floating_chord = (((200.0, 200.0), (215.0, 200.0)),)
    producer.register_room_boundary(
        document_id="doc-maryborough",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="7",
        room_name="PWD",
        boundary_pts=pts,
        wall_face_segment_ids=("w1", "w2", "w3", "w4"),
        associated_door_ids=("D13",),
        door_chords=floating_chord,
        floor_finish_code="FT2",
        scale_px_per_m=50.0,
    )
    authority = producer.authority()
    res = authority.resolve(_make_selector(name="PWD"))
    assert res.status == EvidenceResolutionStatus.ABSTAINED.value
    assert ROOM_WALL_DEFECT_REMAINS in res.reason_codes
    assert res.resolution_mode == "abstain_boundary_defect_remains"


def test_missing_door_transition_triggers_warning():
    producer = SourceMaryboroughPhysicalRoomBoundaryProducer.create()
    pts = ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0))
    producer.register_room_boundary(
        document_id="doc-maryborough",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="7",
        room_name="OFFICE",
        boundary_pts=pts,
        wall_face_segment_ids=("w1", "w2", "w3", "w4"),
        associated_door_ids=(),
        door_chords=(),
        scale_px_per_m=50.0,
    )
    authority = producer.authority()
    res = authority.resolve(_make_selector(name="OFFICE"))
    assert res.status == EvidenceResolutionStatus.CANDIDATE.value
    assert ROOM_DOOR_TRANSITION_MISSING in res.reason_codes


def test_invalid_collinear_polygon_fails():
    producer = SourceMaryboroughPhysicalRoomBoundaryProducer.create()
    pts = ((0.0, 0.0), (50.0, 0.0), (100.0, 0.0))
    producer.register_room_boundary(
        document_id="doc-maryborough",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="7",
        room_name="OFFICE",
        boundary_pts=pts,
        wall_face_segment_ids=("w1",),
        associated_door_ids=("D07",),
        door_chords=(),
        scale_px_per_m=50.0,
    )
    authority = producer.authority()
    res = authority.resolve(_make_selector(name="OFFICE"))
    assert res.status == EvidenceResolutionStatus.ABSTAINED.value
    assert ROOM_INVALID_GEOMETRY in res.reason_codes
    assert ROOM_BOUNDARY_NOT_CLOSED in res.reason_codes


def test_unregistered_room_returns_unavailable():
    producer = SourceMaryboroughPhysicalRoomBoundaryProducer.create()
    authority = producer.authority()
    res = authority.resolve(_make_selector(name="NON-EXISTENT"))
    assert res.status == EvidenceResolutionStatus.ABSTAINED.value
    assert SOURCE_ROOM_BOUNDARY_UNAVAILABLE in res.reason_codes
