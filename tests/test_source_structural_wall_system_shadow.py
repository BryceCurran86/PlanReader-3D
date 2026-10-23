"""Tests for producer-owned structural wall system shadow authority (Item 1)."""
from __future__ import annotations

import pytest
from shapely import wkb

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_structural_wall_system_shadow import (
    JUNCTIONS_INTEGRATED,
    OPENINGS_EMBEDDED,
    PAIRED_FACES_PROVEN,
    SOURCE_STRUCTURAL_WALL_SYSTEM_CANDIDATE,
    SOURCE_STRUCTURAL_WALL_SYSTEM_UNAVAILABLE,
    WALL_GEOMETRY_INVALID,
    WALL_RUN_CONTINUITY_PROVEN,
    WALL_SYSTEM_DISCONTINUOUS,
    WALL_THICKNESS_CORROBORATED,
    WALL_THICKNESS_OUT_OF_BOUNDS,
    WALL_TYPE_EXTERNAL,
    WALL_TYPE_INTERNAL,
    SourceStructuralWallSystemAuthority,
    SourceStructuralWallSystemProducer,
    SourceStructuralWallSystemRecord,
    SourceStructuralWallSystemSelector,
)


def _make_selector(
    *,
    doc="doc-arch",
    rev="rev-01",
    sha="a" * 64,
    snap="snap-01",
    page="1",
    system_id="SYS_EXTERIOR_PERIMETER",
) -> SourceStructuralWallSystemSelector:
    return SourceStructuralWallSystemSelector(
        document_id=doc,
        revision_id=rev,
        source_sha256=sha,
        snapshot_id=snap,
        page_id=page,
        system_id=system_id,
    )


def test_sealing_raises_permission_error():
    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceStructuralWallSystemProducer(object())

    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceStructuralWallSystemAuthority(object(), {})

    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceStructuralWallSystemRecord(
            record_id="rec-1",
            document_id="doc",
            revision_id="rev",
            source_sha256="sha",
            snapshot_id="snap",
            page_id="1",
            system_id="sys-1",
            wall_runs=(),
            total_wall_length_m=10.0,
            total_wall_footprint_m2=2.4,
            wall_count=1,
            opening_count=0,
            junction_count=0,
            wkb_hex=None,
            reason_codes=(),
        )


def test_complete_structural_wall_system_resolution():
    producer = SourceStructuralWallSystemProducer.create()

    # 4 walls forming a 10m x 8m rectangular building footprint (thickness = 0.24m)
    # North wall (y: 8.0 to 8.24, x: 0 to 10)
    producer.register_wall_run(
        document_id="doc-arch",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="1",
        system_id="SYS_EXTERIOR_PERIMETER",
        run_id="WALL_NORTH",
        wall_type=WALL_TYPE_EXTERNAL,
        thickness_m=0.24,
        length_m=10.0,
        centerline_pts=((0.0, 8.12), (10.0, 8.12)),
        face_a_ids=("w_n_ext",),
        face_b_ids=("w_n_int",),
        polygon_pts=((0.0, 8.0), (10.0, 8.0), (10.0, 8.24), (0.0, 8.24)),
        embedded_opening_ids=("W01",),
        junction_ids=("J_NW", "J_NE"),
    )

    # South wall (y: 0 to 0.24, x: 0 to 10)
    producer.register_wall_run(
        document_id="doc-arch",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="1",
        system_id="SYS_EXTERIOR_PERIMETER",
        run_id="WALL_SOUTH",
        wall_type=WALL_TYPE_EXTERNAL,
        thickness_m=0.24,
        length_m=10.0,
        centerline_pts=((0.0, 0.12), (10.0, 0.12)),
        face_a_ids=("w_s_ext",),
        face_b_ids=("w_s_int",),
        polygon_pts=((0.0, 0.0), (10.0, 0.0), (10.0, 0.24), (0.0, 0.24)),
        embedded_opening_ids=("D01",),
        junction_ids=("J_SW", "J_SE"),
    )

    authority = producer.authority()
    sel = _make_selector()
    res = authority.resolve(sel)

    assert res.status == EvidenceResolutionStatus.CANDIDATE.value
    assert SOURCE_STRUCTURAL_WALL_SYSTEM_CANDIDATE in res.reason_codes
    assert WALL_RUN_CONTINUITY_PROVEN in res.reason_codes
    assert PAIRED_FACES_PROVEN in res.reason_codes
    assert WALL_THICKNESS_CORROBORATED in res.reason_codes
    assert OPENINGS_EMBEDDED in res.reason_codes
    assert JUNCTIONS_INTEGRATED in res.reason_codes
    assert res.total_runs == 2
    assert res.total_length_m == 20.0
    assert res.total_footprint_m2 == pytest.approx(4.8, rel=1e-3)

    rec = res.records[0]
    assert rec.opening_count == 2
    assert rec.junction_count == 4
    assert rec.wkb_hex is not None

    geom = wkb.loads(bytes.fromhex(rec.wkb_hex))
    assert geom.is_valid
    assert geom.area == pytest.approx(4.8, rel=1e-3)


def test_out_of_bounds_thickness_fails_closed():
    producer = SourceStructuralWallSystemProducer.create()
    producer.register_wall_run(
        document_id="doc-arch",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="1",
        system_id="SYS_BAD_THICK",
        run_id="WALL_BAD",
        wall_type=WALL_TYPE_INTERNAL,
        thickness_m=0.02,  # 20 mm: impossible structural wall thickness (< 70 mm min)
        length_m=5.0,
        centerline_pts=((0.0, 0.01), (5.0, 0.01)),
        face_a_ids=("f1",),
        face_b_ids=("f2",),
        polygon_pts=((0.0, 0.0), (5.0, 0.0), (5.0, 0.02), (0.0, 0.02)),
    )
    authority = producer.authority()
    res = authority.resolve(_make_selector(system_id="SYS_BAD_THICK"))

    assert res.status == EvidenceResolutionStatus.ABSTAINED.value
    assert WALL_THICKNESS_OUT_OF_BOUNDS in res.reason_codes
    assert res.resolution_mode == "abstain_wall_system_defect_remains"


def test_invalid_collinear_polygon_fails_closed():
    producer = SourceStructuralWallSystemProducer.create()
    producer.register_wall_run(
        document_id="doc-arch",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="1",
        system_id="SYS_COLLINEAR",
        run_id="WALL_COLLINEAR",
        wall_type=WALL_TYPE_INTERNAL,
        thickness_m=0.10,
        length_m=5.0,
        centerline_pts=((0.0, 0.0), (5.0, 0.0)),
        face_a_ids=("f1",),
        face_b_ids=("f2",),
        polygon_pts=((0.0, 0.0), (2.5, 0.0), (5.0, 0.0)),  # Collinear points!
    )
    authority = producer.authority()
    res = authority.resolve(_make_selector(system_id="SYS_COLLINEAR"))

    assert res.status == EvidenceResolutionStatus.ABSTAINED.value
    assert WALL_GEOMETRY_INVALID in res.reason_codes
    assert WALL_SYSTEM_DISCONTINUOUS in res.reason_codes


def test_unregistered_system_returns_unavailable():
    producer = SourceStructuralWallSystemProducer.create()
    authority = producer.authority()
    res = authority.resolve(_make_selector(system_id="SYS_NON_EXISTENT"))
    assert res.status == EvidenceResolutionStatus.ABSTAINED.value
    assert SOURCE_STRUCTURAL_WALL_SYSTEM_UNAVAILABLE in res.reason_codes
