"""Unit tests for Producer-Owned Multi-Level Floor Alignment and Vertical Void Shadow Authority.

Tests positive, negative, and ambiguity handling under strict evaluator separation.
"""

import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_multilevel_floor_vertical_void_shadow import (
    FloorLevelTakeoffAdjustment,
    LevelDatum,
    MultiLevelFloorVerticalVoidShadowAuthority,
    VerticalVoidEvidence,
    VoidKind,
)


def test_positive_stairwell_void():
    authority = MultiLevelFloorVerticalVoidShadowAuthority()
    level1 = LevelDatum(
        level_id="L01",
        name="Level 1",
        elevation_m=3.0,
        floor_to_floor_height_m=3.0,
        page_number=2,
    )
    authority.register_level(level1)

    # 200 pt x 100 pt stairwell. Scale: 1 pt = 0.02 m => 4.0 m x 2.0 m = 8.0 m²
    pts = [(100.0, 100.0), (300.0, 100.0), (300.0, 200.0), (100.0, 200.0)]
    void = authority.evaluate_vertical_void(
        level_id="L01",
        underlying_level_id="L00",
        polygon_pts=pts,
        corroborating_tokens=["STAIR VOID", "DIAGONAL_X"],
        scale_ratio=0.02,
    )

    assert void.status == EvidenceResolutionStatus.CANDIDATE
    assert void.void_kind == VoidKind.STAIRWELL
    assert pytest.approx(void.area_sqm, rel=1e-3) == 8.0
    assert pytest.approx(void.perimeter_m, rel=1e-3) == 12.0
    assert void.commercial_projection_allowed is False
    assert void.takeoff_eligible is False


def test_positive_service_riser_shaft():
    authority = MultiLevelFloorVerticalVoidShadowAuthority()
    # 30 pt x 30 pt riser. Scale: 1 pt = 0.02 m => 0.6 m x 0.6 m = 0.36 m²
    pts = [(50.0, 50.0), (80.0, 50.0), (80.0, 80.0), (50.0, 80.0)]
    void = authority.evaluate_vertical_void(
        level_id="L02",
        underlying_level_id="L01",
        polygon_pts=pts,
        corroborating_tokens=["HYDRAULIC RISER"],
        scale_ratio=0.02,
    )

    assert void.status == EvidenceResolutionStatus.CANDIDATE
    assert void.void_kind == VoidKind.SERVICE_RISER
    assert pytest.approx(void.area_sqm, rel=1e-3) == 0.36


def test_negative_self_intersecting_polygon_fails_closed():
    authority = MultiLevelFloorVerticalVoidShadowAuthority()
    # Bowtie self-intersecting polygon
    pts = [(0.0, 0.0), (100.0, 100.0), (100.0, 0.0), (0.0, 100.0)]
    void = authority.evaluate_vertical_void(
        level_id="L01",
        underlying_level_id="L00",
        polygon_pts=pts,
        corroborating_tokens=["VOID"],
        scale_ratio=0.02,
    )

    assert void.status == EvidenceResolutionStatus.ABSTAINED
    assert "self-intersecting" in void.notes


def test_negative_uncorroborated_void_fails_closed():
    authority = MultiLevelFloorVerticalVoidShadowAuthority()
    pts = [(100.0, 100.0), (300.0, 100.0), (300.0, 200.0), (100.0, 200.0)]
    void = authority.evaluate_vertical_void(
        level_id="L01",
        underlying_level_id="L00",
        polygon_pts=pts,
        corroborating_tokens=[],
        scale_ratio=0.02,
    )

    assert void.status == EvidenceResolutionStatus.ABSTAINED
    assert "Uncorroborated" in void.notes


def test_negative_micro_void_below_threshold_fails_closed():
    authority = MultiLevelFloorVerticalVoidShadowAuthority()
    # 5 pt x 5 pt => 0.1 m x 0.1 m = 0.01 m² (below 0.10 m² minimum)
    pts = [(0.0, 0.0), (5.0, 0.0), (5.0, 5.0), (0.0, 5.0)]
    void = authority.evaluate_vertical_void(
        level_id="L01",
        underlying_level_id="L00",
        polygon_pts=pts,
        corroborating_tokens=["DUCT RISER"],
        scale_ratio=0.02,
    )

    assert void.status == EvidenceResolutionStatus.ABSTAINED
    assert "below minimum threshold" in void.notes


def test_net_floor_area_deduction_calculation():
    authority = MultiLevelFloorVerticalVoidShadowAuthority()

    # Valid stairwell: 8.0 m²
    pts_stair = [(100.0, 100.0), (300.0, 100.0), (300.0, 200.0), (100.0, 200.0)]
    v1 = authority.evaluate_vertical_void(
        level_id="L01",
        underlying_level_id="L00",
        polygon_pts=pts_stair,
        corroborating_tokens=["STAIR VOID"],
        scale_ratio=0.02,
    )

    # Valid riser: 0.36 m²
    pts_riser = [(50.0, 50.0), (80.0, 50.0), (80.0, 80.0), (50.0, 80.0)]
    v2 = authority.evaluate_vertical_void(
        level_id="L01",
        underlying_level_id="L00",
        polygon_pts=pts_riser,
        corroborating_tokens=["RISER"],
        scale_ratio=0.02,
    )

    # Invalid uncorroborated void: should not be deducted
    v3 = authority.evaluate_vertical_void(
        level_id="L01",
        underlying_level_id="L00",
        polygon_pts=pts_stair,
        corroborating_tokens=[],
        scale_ratio=0.02,
    )

    # Gross floor area = 150.0 m²
    adj = authority.compute_level_net_floor_area(
        level_id="L01",
        gross_floor_area_sqm=150.0,
        voids=[v1, v2, v3],
    )

    assert adj.status == EvidenceResolutionStatus.CANDIDATE
    # Candidate voids are not measurement authority and must not be deducted.
    assert pytest.approx(adj.void_deductions_sqm, rel=1e-3) == 0.0
    assert pytest.approx(adj.net_floor_area_sqm, rel=1e-3) == 150.0
    assert len(adj.subtracted_void_ids) == 0
    assert adj.commercial_projection_allowed is False
