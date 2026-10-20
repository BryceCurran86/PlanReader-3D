"""Unit tests for Producer-Owned Wet-Area Floor Waste Fall and Hob Boundary Shadow Authority.

Tests positive, negative, and ambiguity scenarios.
"""

import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_wet_area_hob_waste_fall_shadow import (
    HobGeometryEvidence,
    HobKind,
    WetAreaHobWasteFallShadowAuthority,
    WetAreaTakeoffSummary,
)


def test_positive_raised_hob_evaluation():
    authority = WetAreaHobWasteFallShadowAuthority()
    # 50 pt long hob line. Scale: 1 pt = 0.02 m => 1.0 m long.
    # Hob dimensions: 0.10 m wide, 0.075 m high.
    pts = [(0.0, 0.0), (50.0, 0.0)]
    hob = authority.evaluate_hob(
        room_id="BATH_01",
        centerline_pts=pts,
        hob_kind=HobKind.RAISED_HOB,
        width_m=0.10,
        height_m=0.075,
        scale_ratio=0.02,
    )

    assert hob.status == EvidenceResolutionStatus.CANDIDATE
    assert hob.is_structural_wall is False
    assert pytest.approx(hob.length_m, rel=1e-3) == 1.0
    assert pytest.approx(hob.top_area_sqm, rel=1e-3) == 0.10  # 1.0 * 0.10
    assert pytest.approx(hob.vertical_face_area_sqm, rel=1e-3) == 0.15  # 2 * 1.0 * 0.075
    assert pytest.approx(hob.waterproofing_upturn_area_sqm, rel=1e-3) == 0.15  # 1.0 * 0.15
    assert hob.commercial_projection_allowed is False
    assert hob.takeoff_eligible is False


def test_positive_recessed_stepdown_evaluation():
    authority = WetAreaHobWasteFallShadowAuthority()
    # 45 pt long stepdown. Scale: 1 pt = 0.02 m => 0.9 m long.
    # Height: 0.02 m stepdown (1 vertical face).
    pts = [(10.0, 10.0), (55.0, 10.0)]
    hob = authority.evaluate_hob(
        room_id="ENSUITE_01",
        centerline_pts=pts,
        hob_kind=HobKind.RECESSED_STEPDOWN,
        width_m=0.05,
        height_m=0.02,
        scale_ratio=0.02,
    )

    assert hob.status == EvidenceResolutionStatus.CANDIDATE
    assert pytest.approx(hob.length_m, rel=1e-3) == 0.9
    assert pytest.approx(hob.vertical_face_area_sqm, rel=1e-3) == 0.018  # 1 * 0.9 * 0.02


def test_negative_excessive_height_is_structural_wall():
    authority = WetAreaHobWasteFallShadowAuthority()
    # Height = 2.4 m (full room height) -> NOT a hob!
    pts = [(0.0, 0.0), (50.0, 0.0)]
    hob = authority.evaluate_hob(
        room_id="BATH_01",
        centerline_pts=pts,
        hob_kind=HobKind.RAISED_HOB,
        width_m=0.10,
        height_m=2.40,
        scale_ratio=0.02,
    )

    assert hob.status == EvidenceResolutionStatus.ABSTAINED
    assert hob.is_structural_wall is True
    assert "exceeds hob limits" in hob.notes


def test_negative_degenerate_centerline():
    authority = WetAreaHobWasteFallShadowAuthority()
    pts = [(10.0, 10.0)]
    hob = authority.evaluate_hob(
        room_id="BATH_01",
        centerline_pts=pts,
        hob_kind=HobKind.RAISED_HOB,
        width_m=0.10,
        height_m=0.075,
        scale_ratio=0.02,
    )

    assert hob.status == EvidenceResolutionStatus.ABSTAINED
    assert "Degenerate" in hob.notes


def test_negative_length_out_of_bounds():
    authority = WetAreaHobWasteFallShadowAuthority()
    # 5 pt long => 0.10 m (below 0.30 m physical limit)
    pts = [(0.0, 0.0), (5.0, 0.0)]
    hob = authority.evaluate_hob(
        room_id="BATH_01",
        centerline_pts=pts,
        hob_kind=HobKind.RAISED_HOB,
        width_m=0.10,
        height_m=0.075,
        scale_ratio=0.02,
    )

    assert hob.status == EvidenceResolutionStatus.ABSTAINED
    assert "outside valid physical bounds" in hob.notes


def test_wet_area_takeoff_summary_computation():
    authority = WetAreaHobWasteFallShadowAuthority()
    pts = [(0.0, 0.0), (50.0, 0.0)]
    hob = authority.evaluate_hob(
        room_id="BATH_01",
        centerline_pts=pts,
        hob_kind=HobKind.RAISED_HOB,
        width_m=0.10,
        height_m=0.075,
        scale_ratio=0.02,
    )

    summary = authority.compute_wet_area_takeoff(
        room_id="BATH_01",
        floor_finish_code="FT2",
        room_gross_floor_area_sqm=5.0,
        shower_enclosure_area_sqm=1.0,
        hobs=[hob],
        shower_wall_perimeter_m=2.8,
        waterproof_upturn_height_m=0.15,
    )

    assert summary.status == EvidenceResolutionStatus.CANDIDATE
    assert pytest.approx(summary.main_floor_area_sqm, rel=1e-3) == 4.0
    assert pytest.approx(summary.shower_floor_area_sqm, rel=1e-3) == 1.0
    # Candidate hobs are not measurement authority and must not enter takeoff totals.
    assert pytest.approx(summary.hob_vertical_faces_sqm, rel=1e-3) == 0.0
    assert pytest.approx(summary.hob_top_faces_sqm, rel=1e-3) == 0.0
    assert pytest.approx(summary.total_tiling_area_sqm, rel=1e-3) == 5.0
    assert pytest.approx(summary.waterproofing_perimeter_upturn_sqm, rel=1e-3) == 0.42
    assert summary.commercial_projection_allowed is False
