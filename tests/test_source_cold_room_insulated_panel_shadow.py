"""Tests for producer-owned cold-room insulated panel structural boundary shadow authority (Item 62)."""
from __future__ import annotations

import pytest
from shapely import wkb

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_cold_room_insulated_panel_shadow import (
    COLD_ROOM_DOOR_REBATE_VERIFIED,
    COLD_ROOM_GEOMETRY_INVALID,
    COLD_ROOM_PANEL_THICKNESS_CORROBORATED,
    NON_COLD_ROOM_NAME_UNAUTHENTICATED,
    PANEL_MATERIAL_PIR,
    PANEL_THICKNESS_OUT_OF_BOUNDS,
    SOURCE_COLD_ROOM_BOUNDARY_RESOLVED,
    SOURCE_COLD_ROOM_BOUNDARY_UNAVAILABLE,
    THERMAL_BREAK_GAP_DEFECT,
    THERMAL_PERIMETER_ENCLOSED,
    SourceColdRoomInsulatedPanelAuthority,
    SourceColdRoomInsulatedPanelProducer,
    SourceColdRoomPanelRecord,
    SourceColdRoomPanelSelector,
    normalize_cold_room_name,
)


def _make_selector(
    *,
    doc="doc-maryborough",
    rev="rev-01",
    sha="a" * 64,
    snap="snap-01",
    page="7",
    name="FREEZER",
) -> SourceColdRoomPanelSelector:
    return SourceColdRoomPanelSelector(
        document_id=doc,
        revision_id=rev,
        source_sha256=sha,
        snapshot_id=snap,
        page_id=page,
        room_name=name,
    )


def test_sealing_raises_permission_error():
    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceColdRoomInsulatedPanelProducer(object())

    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceColdRoomInsulatedPanelAuthority(object(), {})

    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceColdRoomPanelRecord(
            record_id="rec-1",
            document_id="doc",
            revision_id="rev",
            source_sha256="sha",
            snapshot_id="snap",
            page_id="7",
            room_name="FREEZER",
            room_key="FREEZER",
            panel_material=PANEL_MATERIAL_PIR,
            panel_thickness_m=0.10,
            internal_area_m2=10.0,
            internal_perimeter_m=13.0,
            storage_volume_m3=27.0,
            panel_segment_ids=("p1", "p2"),
            door_opening_ids=("D_FRZ",),
            boundary_pts=((0.0, 0.0), (10.0, 0.0), (10.0, 1.0), (0.0, 1.0)),
            wkb_hex=None,
            reason_codes=(),
        )


def test_positive_cold_room_boundary_resolution():
    producer = SourceColdRoomInsulatedPanelProducer.create()
    # 4m x 3m internal freezer footprint (200 pt x 150 pt @ 50 pt/m)
    pts = ((100.0, 100.0), (300.0, 100.0), (300.0, 250.0), (100.0, 250.0))
    producer.register_cold_room(
        document_id="doc-maryborough",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="7",
        room_name="FREEZER",
        panel_material=PANEL_MATERIAL_PIR,
        panel_thickness_m=0.100,  # 100 mm PIR panel
        boundary_pts=pts,
        panel_segment_ids=("panel_n", "panel_e", "panel_s", "panel_w"),
        door_opening_ids=("D_FRZ",),
        clear_height_m=2.7,
        scale_px_per_m=50.0,
    )
    authority = producer.authority()
    sel = _make_selector()
    res = authority.resolve(sel)

    assert res.status == EvidenceResolutionStatus.CORROBORATED.value
    assert SOURCE_COLD_ROOM_BOUNDARY_RESOLVED in res.reason_codes
    assert THERMAL_PERIMETER_ENCLOSED in res.reason_codes
    assert COLD_ROOM_PANEL_THICKNESS_CORROBORATED in res.reason_codes
    assert COLD_ROOM_DOOR_REBATE_VERIFIED in res.reason_codes
    # Area: 200 * 150 / 2500 = 12.0 m2
    assert res.internal_area_m2 == 12.0
    # Volume: 12.0 * 2.7 = 32.4 m3
    assert res.storage_volume_m3 == 32.4

    rec = res.record
    assert rec is not None
    assert rec.status == EvidenceResolutionStatus.CANDIDATE.value
    assert rec.commercial_projection_allowed is False
    assert rec.takeoff_eligible is False

    geom = wkb.loads(bytes.fromhex(rec.wkb_hex))
    assert geom.geom_type == "Polygon"
    assert geom.is_valid
    assert abs(geom.area - 30000.0) < 1e-4


def test_out_of_bounds_thickness_fails_closed():
    producer = SourceColdRoomInsulatedPanelProducer.create()
    pts = ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0))
    producer.register_cold_room(
        document_id="doc-maryborough",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="7",
        room_name="FREEZER",
        panel_material=PANEL_MATERIAL_PIR,
        panel_thickness_m=0.040,  # 40 mm is too thin for cold room panel (< 75 mm min)
        boundary_pts=pts,
        panel_segment_ids=("p1",),
        door_opening_ids=("D1",),
        scale_px_per_m=50.0,
    )
    authority = producer.authority()
    res = authority.resolve(_make_selector())

    assert res.status == EvidenceResolutionStatus.ABSTAINED.value
    assert PANEL_THICKNESS_OUT_OF_BOUNDS in res.reason_codes
    assert res.resolution_mode == "abstain_cold_room_panel_defect"


def test_non_cold_room_name_fails_closed():
    producer = SourceColdRoomInsulatedPanelProducer.create()
    pts = ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0))
    producer.register_cold_room(
        document_id="doc-maryborough",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="7",
        room_name="BEDROOM",  # Not a refrigerated room!
        panel_material=PANEL_MATERIAL_PIR,
        panel_thickness_m=0.100,
        boundary_pts=pts,
        panel_segment_ids=("p1",),
        door_opening_ids=("D1",),
        scale_px_per_m=50.0,
    )
    authority = producer.authority()
    res = authority.resolve(_make_selector(name="BEDROOM"))

    assert res.status == EvidenceResolutionStatus.ABSTAINED.value
    assert NON_COLD_ROOM_NAME_UNAUTHENTICATED in res.reason_codes


def test_invalid_collinear_polygon_fails_closed():
    producer = SourceColdRoomInsulatedPanelProducer.create()
    pts = ((0.0, 0.0), (50.0, 0.0), (100.0, 0.0))
    producer.register_cold_room(
        document_id="doc-maryborough",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="7",
        room_name="FREEZER",
        panel_material=PANEL_MATERIAL_PIR,
        panel_thickness_m=0.100,
        boundary_pts=pts,
        panel_segment_ids=("p1",),
        door_opening_ids=(),
        scale_px_per_m=50.0,
    )
    authority = producer.authority()
    res = authority.resolve(_make_selector())

    assert res.status == EvidenceResolutionStatus.ABSTAINED.value
    assert COLD_ROOM_GEOMETRY_INVALID in res.reason_codes
    assert THERMAL_BREAK_GAP_DEFECT in res.reason_codes


def test_unregistered_selector_returns_unavailable():
    producer = SourceColdRoomInsulatedPanelProducer.create()
    authority = producer.authority()
    res = authority.resolve(_make_selector(name="NON_EXISTENT"))

    assert res.status == EvidenceResolutionStatus.ABSTAINED.value
    assert SOURCE_COLD_ROOM_BOUNDARY_UNAVAILABLE in res.reason_codes
