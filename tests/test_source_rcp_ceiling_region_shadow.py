"""Synthetic tests for pb_source_rcp_ceiling_region_shadow.

Verifies RCP ceiling polygon zone recovery, segregation of internal ceiling
linings (IPF1, GRID) from external overhead cladding (CL03, STP), and typed
negative conflict rejection. Zero private PDF or benchmark gold consumed.
"""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_rcp_ceiling_region_shadow import (
    SourceRcpCeilingRegionProducer,
    SourceRcpCeilingRegionSelector,
    ROLE_INTERNAL_CEILING_LINING,
    ROLE_EXTERNAL_OVERHEAD_CLADDING,
    ROLE_ANY,
    COMPETING_CEILING_MARKS_IN_ZONE,
    NO_CEILING_MARK_IN_ZONE,
    CEILING_ROLE_MISMATCH,
    EXTERNAL_CLADDING_VETOES_INTERNAL_CEILING,
    classify_material_role,
)


def sample_selector(code: str = "IPF1", role: str = ROLE_ANY) -> SourceRcpCeilingRegionSelector:
    return SourceRcpCeilingRegionSelector(
        document_id="doc-rcp-1",
        revision_id="rev-rcp-1",
        source_sha256="b" * 64,
        snapshot_id="snap-rcp-1",
        rcp_page_id="9",
        material_code=code,
        expected_role=role,
    )


# ==============================================================================
# Positive Tests
# ==============================================================================

def test_producer_initialization():
    prod = SourceRcpCeilingRegionProducer()
    assert prod._source is None

    with pytest.raises(TypeError, match="SourceVisibilityProducer"):
        SourceRcpCeilingRegionProducer(object())  # type: ignore


def test_positive_ipf1_internal_ceiling_recovery():
    selector = sample_selector("IPF1", ROLE_INTERNAL_CEILING_LINING)
    prod = SourceRcpCeilingRegionProducer()

    # Synthetic zone for Office/Airlock ceiling
    poly = ((100.0, 100.0), (300.0, 100.0), (300.0, 250.0), (100.0, 250.0))
    zones = [
        {
            "zone_id": "zone-office-ceiling",
            "polygon_pdf_pts": poly,
            "physical_room_id": "room-office",
            "canonical_room_id": "canonical-office",
        }
    ]
    marks = [
        {"id": "mark-ipf1-1", "x": 200.0, "y": 175.0, "code": "IPF1"}
    ]

    result = prod.evaluate_synthetic(
        selector=selector,
        zone_polygons=zones,
        marks=marks,
    )

    assert result.status == EvidenceResolutionStatus.CANDIDATE
    assert result.candidate_zone_count == 1
    rec = result.records[0]
    assert rec.status == EvidenceResolutionStatus.CANDIDATE
    assert rec.material_code == "IPF1"
    assert rec.ceiling_role == ROLE_INTERNAL_CEILING_LINING
    assert rec.area_pts2 == pytest.approx(200.0 * 150.0)
    assert rec.physical_room_id == "room-office"
    assert rec.canonical_room_id == "canonical-office"
    assert rec.source_mark_ids == ("mark-ipf1-1",)
    assert rec.commercial_projection_allowed is False
    assert rec.takeoff_eligible is False


def test_positive_grid_internal_ceiling_recovery():
    selector = sample_selector("GRID", ROLE_INTERNAL_CEILING_LINING)
    prod = SourceRcpCeilingRegionProducer()

    poly = ((400.0, 100.0), (700.0, 100.0), (700.0, 400.0), (400.0, 400.0))
    zones = [
        {
            "zone_id": "zone-shop-ceiling",
            "polygon_pdf_pts": poly,
            "physical_room_id": "room-shop",
            "canonical_room_id": "canonical-shop",
        }
    ]
    marks = [
        {"id": "mark-grid-1", "x": 550.0, "y": 250.0, "code": "GRID"}
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
    assert rec.material_code == "GRID"
    assert rec.ceiling_role == ROLE_INTERNAL_CEILING_LINING


def test_positive_cl03_external_overhead_cladding_recovery():
    selector = sample_selector("CL03", ROLE_EXTERNAL_OVERHEAD_CLADDING)
    prod = SourceRcpCeilingRegionProducer()

    # Exterior canopy / fascia band
    poly = ((50.0, 500.0), (800.0, 500.0), (800.0, 580.0), (50.0, 580.0))
    zones = [
        {
            "zone_id": "zone-canopy-cladding",
            "polygon_pdf_pts": poly,
            "physical_room_id": None,  # External unhosted
            "canonical_room_id": None,
        }
    ]
    marks = [
        {"id": "mark-cl03-1", "x": 400.0, "y": 540.0, "code": "CL03"}
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
    assert rec.physical_room_id is None


# ==============================================================================
# Negative & Ambiguity Tests
# ==============================================================================

def test_negative_external_cladding_vetoed_when_queried_as_internal_lining():
    # If a pipeline requests internal ceiling lining for CL03, it must abstain
    selector = sample_selector("CL03", ROLE_INTERNAL_CEILING_LINING)
    prod = SourceRcpCeilingRegionProducer()

    result = prod.evaluate_synthetic(
        selector=selector,
        zone_polygons=[],
        marks=[],
    )
    assert result.status == EvidenceResolutionStatus.ABSTAINED
    assert CEILING_ROLE_MISMATCH in result.reason_codes


def test_negative_competing_marks_in_same_zone_conflict():
    selector = sample_selector("IPF1", ROLE_ANY)
    prod = SourceRcpCeilingRegionProducer()

    poly = ((100.0, 100.0), (300.0, 100.0), (300.0, 250.0), (100.0, 250.0))
    zones = [{"zone_id": "zone-mixed", "polygon_pdf_pts": poly}]
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


def test_negative_no_marks_in_zone_abstains():
    selector = sample_selector("IPF1", ROLE_ANY)
    prod = SourceRcpCeilingRegionProducer()

    poly = ((100.0, 100.0), (300.0, 100.0), (300.0, 250.0), (100.0, 250.0))
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
    prod = SourceRcpCeilingRegionProducer()

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
    assert classify_material_role("CLD3") == ROLE_EXTERNAL_OVERHEAD_CLADDING
    assert classify_material_role("STP") == ROLE_EXTERNAL_OVERHEAD_CLADDING
    assert classify_material_role("SOFFIT") == ROLE_EXTERNAL_OVERHEAD_CLADDING
    assert classify_material_role("UNKNOWN") == "unclassified"
