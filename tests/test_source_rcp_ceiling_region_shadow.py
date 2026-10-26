"""Production unit and regression tests for pb_source_rcp_ceiling_region_shadow (Item 16 & 17).

Tests physical boundary recovery of reflected ceiling plan zones, segregating internal
linings (IPF1, GRID) from external overhead cladding (CL03, STP), and typed
negative evidence for multi-mark conflicts.
"""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_rcp_ceiling_region_shadow import (
    CEILING_ROLE_MISMATCH,
    COMPETING_CEILING_MARKS_IN_ZONE,
    EXTERNAL_CLADDING_VETOES_INTERNAL_CEILING,
    NO_CEILING_MARK_IN_ZONE,
    ROLE_ANY,
    ROLE_EXTERNAL_OVERHEAD_CLADDING,
    ROLE_EXTERNAL_SIGNAGE_CLADDING,
    ROLE_INTERNAL_CEILING_LINING,
    SOURCE_RCP_CEILING_REGION_CANDIDATE,
    SOURCE_RCP_CEILING_REGION_UNAVAILABLE,
    SourceRcpCeilingRegionAuthority,
    SourceRcpCeilingRegionProducer,
    SourceRcpCeilingRegionRecord,
    SourceRcpCeilingRegionSelector,
    classify_material_role,
)

DOC_ID = "doc-a120-test"
REV_ID = "rev-01"
SHA256 = "e" * 64
SNAP_ID = "snap-01"
PAGE_ID = "9"


def sample_selector(code: str = "IPF1", role: str = ROLE_ANY) -> SourceRcpCeilingRegionSelector:
    return SourceRcpCeilingRegionSelector(
        document_id=DOC_ID,
        revision_id=REV_ID,
        source_sha256=SHA256,
        snapshot_id=SNAP_ID,
        rcp_page_id=PAGE_ID,
        material_code=code,
        expected_role=role,
    )


def sample_poly(offset_x: float = 0.0, offset_y: float = 0.0) -> tuple[tuple[float, float], ...]:
    return (
        (100.0 + offset_x, 100.0 + offset_y),
        (300.0 + offset_x, 100.0 + offset_y),
        (300.0 + offset_x, 250.0 + offset_y),
        (100.0 + offset_x, 250.0 + offset_y),
    )


def test_positive_internal_ceiling_lining_recovery():
    selector = sample_selector("IPF1", ROLE_INTERNAL_CEILING_LINING)
    prod = SourceRcpCeilingRegionProducer.create()

    poly = sample_poly()
    zones = [
        {
            "zone_id": "zone-pwd-ceiling",
            "polygon_pdf_pts": poly,
            "physical_room_id": "room-pwd",
            "canonical_room_id": "canon-pwd",
        }
    ]
    marks = [
        {"id": "mark-ipf1-1", "x": 200.0, "y": 175.0, "code": "IPF1"}
    ]

    result = prod.evaluate_and_publish(
        selector,
        zone_polygons=zones,
        marks=marks,
        scale_px_per_m=100.0,
    )

    assert result.status == EvidenceResolutionStatus.CANDIDATE
    assert len(result.records) == 1
    rec = result.records[0]
    assert rec.status == EvidenceResolutionStatus.CANDIDATE
    assert rec.material_code == "IPF1"
    assert rec.ceiling_role == ROLE_INTERNAL_CEILING_LINING
    assert rec.area_pts2 == 30000.0  # 200 * 150
    assert rec.area_m2 == 3.0  # 30000 / 10000
    assert rec.physical_room_id == "room-pwd"
    assert rec.canonical_room_id == "canon-pwd"
    assert rec.source_mark_ids == ("mark-ipf1-1",)
    assert SOURCE_RCP_CEILING_REGION_CANDIDATE in rec.reason_codes
    assert rec.commercial_projection_allowed is False
    assert rec.takeoff_eligible is False


def test_positive_external_cladding_recovery():
    selector = sample_selector("CL03", ROLE_EXTERNAL_OVERHEAD_CLADDING)
    prod = SourceRcpCeilingRegionProducer.create()

    poly = sample_poly()
    zones = [
        {
            "zone_id": "zone-canopy-1",
            "polygon_pdf_pts": poly,
            "physical_room_id": "soffit-east",
            "canonical_room_id": "canon-soffit-east",
        }
    ]
    marks = [
        {"id": "mark-cld3-1", "x": 150.0, "y": 150.0, "code": "CL03"}
    ]

    result = prod.evaluate_synthetic(
        selector=selector,
        zone_polygons=zones,
        marks=marks,
    )

    assert result.status == EvidenceResolutionStatus.CANDIDATE
    assert len(result.records) == 1
    rec = result.records[0]
    assert rec.status == EvidenceResolutionStatus.CANDIDATE
    assert rec.material_code == "CL03"
    assert rec.ceiling_role == ROLE_EXTERNAL_OVERHEAD_CLADDING
    assert rec.physical_room_id == "soffit-east"
    assert rec.source_mark_ids == ("mark-cld3-1",)


def test_external_cladding_vetoes_internal_ceiling_query():
    # Query expects internal ceiling lining, but code is external cladding CL03
    selector = sample_selector("CL03", ROLE_INTERNAL_CEILING_LINING)
    prod = SourceRcpCeilingRegionProducer.create()

    poly = sample_poly()
    zones = [{"zone_id": "zone-1", "polygon_pdf_pts": poly}]
    marks = [{"id": "m1", "x": 150.0, "y": 150.0, "code": "CL03"}]

    result = prod.evaluate_synthetic(
        selector=selector,
        zone_polygons=zones,
        marks=marks,
    )

    assert result.status == EvidenceResolutionStatus.ABSTAINED
    assert CEILING_ROLE_MISMATCH in result.reason_codes
    assert result.candidate_zone_count == 0


def test_internal_lining_vetoes_external_cladding_query():
    # Query expects external overhead cladding, but code is internal IPF1
    selector = sample_selector("IPF1", ROLE_EXTERNAL_OVERHEAD_CLADDING)
    prod = SourceRcpCeilingRegionProducer.create()

    poly = sample_poly()
    zones = [{"zone_id": "zone-1", "polygon_pdf_pts": poly}]
    marks = [{"id": "m1", "x": 150.0, "y": 150.0, "code": "IPF1"}]

    result = prod.evaluate_synthetic(
        selector=selector,
        zone_polygons=zones,
        marks=marks,
    )

    assert result.status == EvidenceResolutionStatus.ABSTAINED
    assert CEILING_ROLE_MISMATCH in result.reason_codes
    assert result.candidate_zone_count == 0


def test_negative_competing_ceiling_marks_in_single_zone():
    selector = sample_selector("IPF1", ROLE_ANY)
    prod = SourceRcpCeilingRegionProducer.create()

    poly = sample_poly()
    zones = [{"zone_id": "zone-conflict", "polygon_pdf_pts": poly}]
    # Both IPF1 and GRID placed inside the same unpartitioned zone
    marks = [
        {"id": "mark-ipf1", "x": 150.0, "y": 175.0, "code": "IPF1"},
        {"id": "mark-grid", "x": 250.0, "y": 175.0, "code": "GRID"},
    ]

    result = prod.evaluate_synthetic(
        selector=selector,
        zone_polygons=zones,
        marks=marks,
    )

    assert result.status == EvidenceResolutionStatus.CONFLICT
    assert len(result.records) == 1
    rec = result.records[0]
    assert rec.status == EvidenceResolutionStatus.CONFLICT
    assert COMPETING_CEILING_MARKS_IN_ZONE in rec.reason_codes


def test_negative_no_ceiling_mark_in_zone():
    selector = sample_selector("IPF1", ROLE_ANY)
    prod = SourceRcpCeilingRegionProducer.create()

    poly = sample_poly()
    zones = [{"zone_id": "zone-empty", "polygon_pdf_pts": poly}]
    # Marks outside the polygon
    marks = [
        {"id": "mark-outside", "x": 500.0, "y": 500.0, "code": "IPF1"}
    ]

    result = prod.evaluate_synthetic(
        selector=selector,
        zone_polygons=zones,
        marks=marks,
    )

    assert result.status == EvidenceResolutionStatus.ABSTAINED
    assert len(result.records) == 1
    rec = result.records[0]
    assert rec.status == EvidenceResolutionStatus.ABSTAINED
    assert NO_CEILING_MARK_IN_ZONE in rec.reason_codes


def test_negative_degenerate_polygons_ignored():
    selector = sample_selector("IPF1", ROLE_ANY)
    prod = SourceRcpCeilingRegionProducer.create()

    # Collinear line segment, not a polygon
    degenerate = ((10.0, 10.0), (20.0, 20.0), (30.0, 30.0))
    zones = [{"zone_id": "zone-degen", "polygon_pdf_pts": degenerate}]
    marks = [{"id": "m1", "x": 20.0, "y": 20.0, "code": "IPF1"}]

    result = prod.evaluate_synthetic(
        selector=selector,
        zone_polygons=zones,
        marks=marks,
    )

    assert result.candidate_zone_count == 0
    assert result.records == ()


def test_classify_material_role_helper():
    assert classify_material_role("IPF1") == ROLE_INTERNAL_CEILING_LINING
    assert classify_material_role("GRID") == ROLE_INTERNAL_CEILING_LINING
    assert classify_material_role("CL03") == ROLE_EXTERNAL_OVERHEAD_CLADDING
    assert classify_material_role("CLD3") == ROLE_EXTERNAL_SIGNAGE_CLADDING
    assert classify_material_role("STP") == ROLE_EXTERNAL_OVERHEAD_CLADDING
    assert classify_material_role("SOFFIT") == ROLE_EXTERNAL_OVERHEAD_CLADDING
    assert classify_material_role("UNKNOWN") == "unclassified"


def test_scale_calibrated_area_for_ipf1_grid_and_cl03():
    prod = SourceRcpCeilingRegionProducer.create()

    # 100 pt x 100 pt square = 10,000 pt2
    # At scale 100 pt/m, area_m2 = 10,000 / 10,000 = 1.0 m2
    poly = ((100.0, 100.0), (200.0, 100.0), (200.0, 200.0), (100.0, 200.0))
    zones = [{"zone_id": "zone-scale", "polygon_pdf_pts": poly}]

    # 1. IPF1 test
    sel_ipf1 = sample_selector("IPF1", ROLE_INTERNAL_CEILING_LINING)
    res_ipf1 = prod.evaluate_and_publish(
        sel_ipf1,
        zone_polygons=zones,
        marks=[{"id": "m-ipf1", "x": 150.0, "y": 150.0, "code": "IPF1"}],
        scale_px_per_m=100.0,
    )
    assert res_ipf1.status == EvidenceResolutionStatus.CANDIDATE
    assert res_ipf1.records[0].area_m2 == 1.0

    # 2. GRID test
    sel_grid = sample_selector("GRID", ROLE_INTERNAL_CEILING_LINING)
    res_grid = prod.evaluate_and_publish(
        sel_grid,
        zone_polygons=zones,
        marks=[{"id": "m-grid", "x": 150.0, "y": 150.0, "code": "GRID"}],
        scale_px_per_m=100.0,
    )
    assert res_grid.status == EvidenceResolutionStatus.CANDIDATE
    assert res_grid.records[0].area_m2 == 1.0

    # 3. CL03 external cladding test
    sel_cl03 = sample_selector("CL03", ROLE_EXTERNAL_OVERHEAD_CLADDING)
    res_cl03 = prod.evaluate_and_publish(
        sel_cl03,
        zone_polygons=zones,
        marks=[{"id": "m-cl03", "x": 150.0, "y": 150.0, "code": "CL03"}],
        scale_px_per_m=100.0,
    )
    assert res_cl03.status == EvidenceResolutionStatus.CANDIDATE
    assert res_cl03.records[0].area_m2 == 1.0


def test_rcp_authority_lookup_and_sealed_construction():
    prod = SourceRcpCeilingRegionProducer.create()
    poly = ((100.0, 100.0), (200.0, 100.0), (200.0, 200.0), (100.0, 200.0))
    zones = [{"zone_id": "zone-pwd", "polygon_pdf_pts": poly}]
    sel = sample_selector("IPF1", ROLE_INTERNAL_CEILING_LINING)

    prod.evaluate_and_publish(
        sel,
        zone_polygons=zones,
        marks=[{"id": "m-pwd", "x": 150.0, "y": 150.0, "code": "IPF1"}],
        scale_px_per_m=100.0,
    )

    auth = prod.authority()
    res_known = auth.resolve(sel)
    assert res_known.status == EvidenceResolutionStatus.CANDIDATE
    assert len(res_known.records) == 1

    unknown_sel = sample_selector("UNKNOWN_CODE")
    res_unknown = auth.resolve(unknown_sel)
    assert res_unknown.status == EvidenceResolutionStatus.ABSTAINED
    assert SOURCE_RCP_CEILING_REGION_UNAVAILABLE in res_unknown.reason_codes

    with pytest.raises(TypeError, match="producer-owned"):
        SourceRcpCeilingRegionAuthority({})


def test_original_a120_cld3_signage_is_not_overhead_cl03_or_internal_lining():
    """Original CLD3 signage scope must not be imported into an RCP ceiling."""
    prod = SourceRcpCeilingRegionProducer.create()
    zone = [{"zone_id":"signage-cladding", "polygon_pdf_pts":sample_poly()}]
    marks = [{"id":"cld3-original", "x":175.0, "y":175.0, "code":"CLD3"}]
    for wrong_role in (ROLE_INTERNAL_CEILING_LINING,
                       ROLE_EXTERNAL_OVERHEAD_CLADDING):
        result=prod.evaluate_synthetic(
            selector=sample_selector("CLD3",wrong_role),
            zone_polygons=zone,marks=marks,scale_px_per_m=100.0)
        assert result.status is EvidenceResolutionStatus.ABSTAINED
        assert result.reason_codes == (CEILING_ROLE_MISMATCH,)
        assert result.records == ()
        assert result.candidate_zone_count == 0
    signage=prod.evaluate_synthetic(
        selector=sample_selector("CLD3",ROLE_EXTERNAL_SIGNAGE_CLADDING),
        zone_polygons=zone,marks=marks)
    assert signage.status is EvidenceResolutionStatus.CANDIDATE
    assert len(signage.records)==1
    record=signage.records[0]
    assert record.ceiling_role==ROLE_EXTERNAL_SIGNAGE_CLADDING
    assert record.material_code=="CLD3"
    assert record.area_m2 is None
    assert not record.commercial_projection_allowed
    assert not record.takeoff_eligible


def test_cld3_and_cl03_are_competing_original_material_codes_not_one_sku():
    result=SourceRcpCeilingRegionProducer.create().evaluate_synthetic(
        selector=sample_selector("CLD3",ROLE_ANY),
        zone_polygons=[{"zone_id":"mixed", "polygon_pdf_pts":sample_poly()}],
        marks=[
            {"id":"signage","x":150.0,"y":175.0,"code":"CLD3"},
            {"id":"overhead","x":250.0,"y":175.0,"code":"CL03"},
        ])
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert COMPETING_CEILING_MARKS_IN_ZONE in result.records[0].reason_codes
    assert not result.records[0].commercial_projection_allowed
    assert not result.records[0].takeoff_eligible
