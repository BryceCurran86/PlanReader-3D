"""Tests for producer-owned external soffit and eaves shadow authority (Item 17)."""
from __future__ import annotations

import pytest
from shapely import wkb

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_external_soffit_eaves_shadow import (
    ROLE_EXTERNAL_OVERHEAD_CLADDING,
    SOFFIT_BOUNDARY_NOT_CLOSED,
    SOFFIT_INTERNAL_CEILING_CONFLICT,
    SOFFIT_INVALID_GEOMETRY,
    SOFFIT_OVERHANG_DISCREPANCY,
    SOFFIT_SCALE_NOT_CORROBORATED,
    SOFFIT_WALL_FACE_ANCHOR_MISSING,
    SOURCE_EXTERNAL_SOFFIT_CANDIDATE,
    SOURCE_EXTERNAL_SOFFIT_RESOLVED,
    SOURCE_EXTERNAL_SOFFIT_UNAVAILABLE,
    SourceExternalSoffitAuthority,
    SourceExternalSoffitProducer,
    SourceExternalSoffitRecord,
    SourceExternalSoffitSelector,
)


def _make_selector(
    *,
    doc="doc-maryborough",
    rev="rev-01",
    sha="a" * 64,
    snap="snap-01",
    page="9",
    tag="SOFFIT-NORTH",
    material="STP",
) -> SourceExternalSoffitSelector:
    return SourceExternalSoffitSelector(
        document_id=doc,
        revision_id=rev,
        source_sha256=sha,
        snapshot_id=snap,
        page_id=page,
        soffit_tag=tag,
        material_code=material,
    )


def test_source_external_soffit_producer_sealing():
    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceExternalSoffitProducer(object())

    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceExternalSoffitAuthority(object(), {})

    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceExternalSoffitRecord(
            record_id="rec-1",
            document_id="doc",
            revision_id="rev",
            source_sha256="sha",
            snapshot_id="snap",
            page_id="1",
            soffit_tag="SOFFIT-1",
            material_code="STP",
            material_description="Stramit Premier 300",
            material_role=ROLE_EXTERNAL_OVERHEAD_CLADDING,
            boundary_pts=((0.0, 0.0), (10.0, 0.0), (10.0, 1.0), (0.0, 1.0)),
            area_pt2=10.0,
            area_m2=1.0,
            perimeter_m=22.0,
            scale_px_per_m=50.0,
            figured_overhang_mm=450.0,
            measured_overhang_mm=450.0,
            wkb_hex=None,
            inner_wall_edge_ids=("w1",),
            outer_fascia_edge_ids=("f1",),
            reason_codes=(),
        )


def test_positive_soffit_eaves_resolution():
    producer = SourceExternalSoffitProducer.create()
    # 10 m wide eave with 450 mm (0.45 m) overhang:
    # Scale: 50.0 pt/m -> 0.45 m = 22.5 pt; 10 m = 500.0 pt
    pts = ((100.0, 100.0), (600.0, 100.0), (600.0, 122.5), (100.0, 122.5))
    producer.register_soffit_eaves_zone(
        document_id="doc-maryborough",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="9",
        soffit_tag="SOFFIT-NORTH",
        material_code="STP",
        material_description="STRAMIT PREMIER 300 SOFFIT CLADDING",
        boundary_pts=pts,
        inner_wall_edge_ids=("wall-north-face",),
        outer_fascia_edge_ids=("fascia-north",),
        scale_px_per_m=50.0,
        figured_overhang_mm=450.0,
    )
    authority = producer.authority()
    selector = _make_selector(tag="SOFFIT-NORTH", material="STP")
    result = authority.resolve(selector)

    assert result.status == EvidenceResolutionStatus.CORROBORATED.value
    assert SOURCE_EXTERNAL_SOFFIT_RESOLVED in result.reason_codes
    assert len(result.records) == 1
    rec = result.records[0]
    assert rec.material_role == ROLE_EXTERNAL_OVERHEAD_CLADDING
    assert rec.area_pt2 == 500.0 * 22.5
    # 500.0 * 22.5 / 2500 = 4.5 m2
    assert rec.area_m2 == 4.5
    assert rec.measured_overhang_mm == 450.0
    assert rec.status == EvidenceResolutionStatus.CANDIDATE.value
    assert rec.commercial_projection_allowed is False
    assert rec.takeoff_eligible is False

    # Check WKB deserialization
    geom = wkb.loads(bytes.fromhex(rec.wkb_hex))
    assert geom.geom_type == "Polygon"
    assert geom.is_valid
    assert abs(geom.area - rec.area_pt2) < 1e-6


def test_internal_ceiling_material_conflict_vetoes_soffit():
    producer = SourceExternalSoffitProducer.create()
    pts = ((0.0, 0.0), (100.0, 0.0), (100.0, 20.0), (0.0, 20.0))
    # Trying to register an internal GRID or IPF1 ceiling as an external soffit
    producer.register_soffit_eaves_zone(
        document_id="doc-maryborough",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="9",
        soffit_tag="SOFFIT-CONFLICT",
        material_code="IPF1",
        material_description="Internal plasterboard ceiling",
        boundary_pts=pts,
        inner_wall_edge_ids=("w1",),
        outer_fascia_edge_ids=("f1",),
        scale_px_per_m=50.0,
    )
    authority = producer.authority()
    selector = _make_selector(tag="SOFFIT-CONFLICT", material="IPF1")
    result = authority.resolve(selector)

    assert result.status == EvidenceResolutionStatus.ABSTAINED.value
    assert SOFFIT_INTERNAL_CEILING_CONFLICT in result.reason_codes
    assert result.resolution_mode == "abstain_internal_ceiling_conflict"


def test_missing_wall_face_anchor_flags_warning():
    producer = SourceExternalSoffitProducer.create()
    pts = ((0.0, 0.0), (100.0, 0.0), (100.0, 20.0), (0.0, 20.0))
    # Empty inner_wall_edge_ids: no anchor to external wall face
    producer.register_soffit_eaves_zone(
        document_id="doc-maryborough",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="9",
        soffit_tag="SOFFIT-FLOATING",
        material_code="STP",
        material_description="Floating soffit without wall anchor",
        boundary_pts=pts,
        inner_wall_edge_ids=(),
        outer_fascia_edge_ids=("f1",),
        scale_px_per_m=50.0,
    )
    authority = producer.authority()
    selector = _make_selector(tag="SOFFIT-FLOATING", material="STP")
    result = authority.resolve(selector)

    assert result.status == EvidenceResolutionStatus.CANDIDATE.value
    assert SOFFIT_WALL_FACE_ANCHOR_MISSING in result.reason_codes


def test_invalid_non_closed_or_collinear_polygon():
    producer = SourceExternalSoffitProducer.create()
    # Collinear points: cannot form a valid 2D polygon
    pts = ((0.0, 0.0), (50.0, 0.0), (100.0, 0.0))
    producer.register_soffit_eaves_zone(
        document_id="doc-maryborough",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="9",
        soffit_tag="SOFFIT-COLLINEAR",
        material_code="STP",
        material_description="Invalid collinear eave",
        boundary_pts=pts,
        inner_wall_edge_ids=("w1",),
        outer_fascia_edge_ids=("f1",),
        scale_px_per_m=50.0,
    )
    authority = producer.authority()
    selector = _make_selector(tag="SOFFIT-COLLINEAR", material="STP")
    result = authority.resolve(selector)

    assert result.status == EvidenceResolutionStatus.CANDIDATE.value
    assert SOFFIT_INVALID_GEOMETRY in result.reason_codes
    assert SOFFIT_BOUNDARY_NOT_CLOSED in result.reason_codes


def test_overhang_discrepancy_detection():
    producer = SourceExternalSoffitProducer.create()
    # Measured overhang is 450 mm (22.5 pt @ 50 pt/m), but figured is 600 mm
    pts = ((0.0, 0.0), (500.0, 0.0), (500.0, 22.5), (0.0, 22.5))
    producer.register_soffit_eaves_zone(
        document_id="doc-maryborough",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="9",
        soffit_tag="SOFFIT-DISCREPANCY",
        material_code="STP",
        material_description="STRAMIT SOFFIT",
        boundary_pts=pts,
        inner_wall_edge_ids=("w1",),
        outer_fascia_edge_ids=("f1",),
        scale_px_per_m=50.0,
        figured_overhang_mm=600.0,  # discrepancy!
    )
    authority = producer.authority()
    selector = _make_selector(tag="SOFFIT-DISCREPANCY", material="STP")
    result = authority.resolve(selector)

    assert result.status == EvidenceResolutionStatus.CANDIDATE.value
    assert SOFFIT_OVERHANG_DISCREPANCY in result.reason_codes


def test_uncalibrated_scale_flags_warning():
    producer = SourceExternalSoffitProducer.create()
    pts = ((0.0, 0.0), (100.0, 0.0), (100.0, 20.0), (0.0, 20.0))
    producer.register_soffit_eaves_zone(
        document_id="doc-maryborough",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="9",
        soffit_tag="SOFFIT-UNSCALED",
        material_code="STP",
        material_description="STRAMIT SOFFIT",
        boundary_pts=pts,
        inner_wall_edge_ids=("w1",),
        outer_fascia_edge_ids=("f1",),
        scale_px_per_m=None,  # uncalibrated
    )
    authority = producer.authority()
    selector = _make_selector(tag="SOFFIT-UNSCALED", material="STP")
    result = authority.resolve(selector)

    assert result.status == EvidenceResolutionStatus.CANDIDATE.value
    assert SOFFIT_SCALE_NOT_CORROBORATED in result.reason_codes
    assert result.records[0].area_m2 is None


def test_multi_soffit_run_segregation():
    producer = SourceExternalSoffitProducer.create()
    pts_north = ((0.0, 0.0), (200.0, 0.0), (200.0, 20.0), (0.0, 20.0))
    pts_south = ((0.0, 100.0), (200.0, 100.0), (200.0, 120.0), (0.0, 120.0))

    producer.register_soffit_eaves_zone(
        document_id="doc-maryborough",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="9",
        soffit_tag="SOFFIT-NORTH",
        material_code="STP",
        material_description="STRAMIT SOFFIT NORTH",
        boundary_pts=pts_north,
        inner_wall_edge_ids=("w-north",),
        outer_fascia_edge_ids=("f-north",),
        scale_px_per_m=50.0,
    )
    producer.register_soffit_eaves_zone(
        document_id="doc-maryborough",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="9",
        soffit_tag="SOFFIT-SOUTH",
        material_code="FCS1",
        material_description="FIBRE CEMENT SOFFIT SOUTH",
        boundary_pts=pts_south,
        inner_wall_edge_ids=("w-south",),
        outer_fascia_edge_ids=("f-south",),
        scale_px_per_m=50.0,
    )
    authority = producer.authority()

    res_north = authority.resolve(_make_selector(tag="SOFFIT-NORTH", material="STP"))
    assert res_north.status == EvidenceResolutionStatus.CORROBORATED.value
    assert res_north.records[0].material_code == "STP"

    res_south = authority.resolve(_make_selector(tag="SOFFIT-SOUTH", material="FCS1"))
    assert res_south.status == EvidenceResolutionStatus.CORROBORATED.value
    assert res_south.records[0].material_code == "FCS1"

    all_res = authority.all_results()
    assert len(all_res) == 2


def test_unregistered_selector_returns_unavailable():
    producer = SourceExternalSoffitProducer.create()
    authority = producer.authority()
    res = authority.resolve(_make_selector(tag="NON-EXISTENT"))
    assert res.status == EvidenceResolutionStatus.ABSTAINED.value
    assert SOURCE_EXTERNAL_SOFFIT_UNAVAILABLE in res.reason_codes
