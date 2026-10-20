"""Unit tests for Producer-Owned Freezer D17 Insulated Wall Ends and EPX Floor Finish Shadow Authority.

Tests positive, negative, and conflicting finish scenarios.
"""

import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_freezer_d17_epx_floor_finish_shadow import (
    FreezerD17EpxFloorFinishShadowAuthority,
    FreezerD17OpeningEvidence,
    FreezerFloorTakeoffEvidence,
)


def test_positive_d17_opening_evaluation():
    authority = FreezerD17EpxFloorFinishShadowAuthority()
    # p7 jamb stops at x=476.16, 521.52; p11 jamb stops at x=553.92, 599.28.
    # 553.92 - 476.16 = +77.76 pt.
    # Clear opening = 521.52 - 476.16 = 45.36 pt. Scale: 1 pt = 0.02 m => 0.9072 m.
    evidence = authority.evaluate_d17_opening(
        jamb_left_p7=(476.16, 1175.12),
        jamb_right_p7=(521.52, 1175.12),
        jamb_left_p11=(553.92, 1175.12),
        jamb_right_p11=(599.28, 1175.12),
        wall_stroke_width_pt=0.96,
        filling_stroke_width_pt=0.48,
        scale_ratio=0.02,
    )

    assert evidence.status == EvidenceResolutionStatus.CANDIDATE
    assert pytest.approx(evidence.translation_dx_pt, rel=1e-3) == 77.76
    assert pytest.approx(evidence.clear_opening_width_pt, rel=1e-3) == 45.36
    assert pytest.approx(evidence.clear_opening_width_m, rel=1e-3) == 0.9072
    assert evidence.is_filling_stroke_vetoed_as_wall is True
    assert evidence.commercial_projection_allowed is False
    assert evidence.takeoff_eligible is False


def test_negative_rival_translation_rejected():
    authority = FreezerD17EpxFloorFinishShadowAuthority()
    # Rival translation dx = +43.92 pt (520.08 - 476.16 = 43.92)
    evidence = authority.evaluate_d17_opening(
        jamb_left_p7=(476.16, 1175.12),
        jamb_right_p7=(521.52, 1175.12),
        jamb_left_p11=(520.08, 1175.12),
        jamb_right_p11=(565.44, 1175.12),
        wall_stroke_width_pt=0.96,
        filling_stroke_width_pt=0.48,
        scale_ratio=0.02,
    )

    assert evidence.status == EvidenceResolutionStatus.ABSTAINED
    assert "rival candidate rejected" in evidence.notes


def test_negative_thin_wall_stroke_fails_closed():
    authority = FreezerD17EpxFloorFinishShadowAuthority()
    evidence = authority.evaluate_d17_opening(
        jamb_left_p7=(476.16, 1175.12),
        jamb_right_p7=(521.52, 1175.12),
        jamb_left_p11=(553.92, 1175.12),
        jamb_right_p11=(599.28, 1175.12),
        wall_stroke_width_pt=0.30,  # Too thin for insulated sandwich panel
        filling_stroke_width_pt=0.48,
        scale_ratio=0.02,
    )

    assert evidence.status == EvidenceResolutionStatus.ABSTAINED
    assert "insufficient for insulated sandwich panel" in evidence.notes


def test_positive_freezer_epx_floor_takeoff():
    authority = FreezerD17EpxFloorFinishShadowAuthority()
    # 250 pt x 250 pt room. Scale: 1 pt = 0.02 m => 5.0 m x 5.0 m = 25.0 m². Perimeter = 20.0 m.
    pts = [(100.0, 100.0), (350.0, 100.0), (350.0, 350.0), (100.0, 350.0)]
    takeoff = authority.compute_freezer_floor_takeoff(
        room_id="FREEZER",
        material_code="EPX",
        room_polygon_pts=pts,
        scale_ratio=0.02,
        coving_height_m=0.100,
    )

    assert takeoff.status == EvidenceResolutionStatus.CANDIDATE
    assert takeoff.material_code == "EPX"
    assert pytest.approx(takeoff.internal_floor_area_sqm, rel=1e-3) == 25.0
    assert pytest.approx(takeoff.perimeter_coving_length_m, rel=1e-3) == 20.0
    # Coving area = 20.0 * 0.100 = 2.0 m²
    assert pytest.approx(takeoff.coving_upturn_area_sqm, rel=1e-3) == 2.0
    assert takeoff.commercial_projection_allowed is False
    assert takeoff.takeoff_eligible is False


def test_negative_ft2_ft3_finish_vetoed_in_freezer():
    authority = FreezerD17EpxFloorFinishShadowAuthority()
    pts = [(100.0, 100.0), (350.0, 100.0), (350.0, 350.0), (100.0, 350.0)]

    # Attempting to assign FT2 tile to FREEZER fails closed
    t1 = authority.compute_freezer_floor_takeoff(
        room_id="FREEZER",
        material_code="FT2",
        room_polygon_pts=pts,
        scale_ratio=0.02,
    )
    assert t1.status == EvidenceResolutionStatus.ABSTAINED
    assert "Incompatible finish" in t1.notes

    # Attempting to assign FT3 vinyl to FREEZER fails closed
    t2 = authority.compute_freezer_floor_takeoff(
        room_id="FREEZER",
        material_code="FT3",
        room_polygon_pts=pts,
        scale_ratio=0.02,
    )
    assert t2.status == EvidenceResolutionStatus.ABSTAINED
    assert "Incompatible finish" in t2.notes


def test_omitted_coving_height_does_not_invent_one_hundred_mm():
    authority = FreezerD17EpxFloorFinishShadowAuthority()
    pts = [(0.0, 0.0), (50.0, 0.0), (50.0, 50.0), (0.0, 50.0)]
    takeoff = authority.compute_freezer_floor_takeoff(
        room_id="ROOM_01",
        material_code="RESIN",
        room_polygon_pts=pts,
        scale_ratio=0.02,
    )

    assert takeoff.status == EvidenceResolutionStatus.CANDIDATE
    assert pytest.approx(takeoff.coving_upturn_area_sqm, rel=1e-3) == 0.0


def test_negative_degenerate_polygon_fails_closed():
    authority = FreezerD17EpxFloorFinishShadowAuthority()
    t = authority.compute_freezer_floor_takeoff(
        room_id="FREEZER",
        material_code="EPX",
        room_polygon_pts=[(0.0, 0.0), (10.0, 0.0)],
        scale_ratio=0.02,
    )
    assert t.status == EvidenceResolutionStatus.ABSTAINED
    assert "Degenerate" in t.notes
