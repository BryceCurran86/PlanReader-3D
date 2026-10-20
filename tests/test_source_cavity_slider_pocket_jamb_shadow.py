"""Unit tests for Producer-Owned Cavity Slider and Pocket Door Jamb Continuity Shadow Authority.

Tests positive, negative, and ambiguity scenarios.
"""

import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_cavity_slider_pocket_jamb_shadow import (
    CavitySliderEvidence,
    CavitySliderPocketJambShadowAuthority,
    PocketDoorLeafOperation,
)


def test_positive_single_sliding_cavity_door():
    authority = CavitySliderPocketJambShadowAuthority()
    # Continuous wall from x=0 to x=200 pt. Scale: 1 pt = 0.02 m => 4.0 m wall.
    # Clear opening: x=50 to x=91 pt (41 pt => 0.82 m clear door).
    # Pocket recess: x=91 to x=133 pt (42 pt => 0.84 m pocket).
    # Wall thickness: 0.09 m (standard 90mm stud).
    wall_pts = [(0.0, 100.0), (200.0, 100.0)]
    clear_span = ((50.0, 100.0), (91.0, 100.0))
    pocket_span = ((91.0, 100.0), (133.0, 100.0))

    evidence = authority.evaluate_cavity_slider(
        wall_id="WALL_INT_07",
        wall_centerline_pts=wall_pts,
        clear_opening_span=clear_span,
        pocket_recess_span=pocket_span,
        operation=PocketDoorLeafOperation.SINGLE_SLIDING,
        wall_thickness_m=0.09,
        scale_ratio=0.02,
    )

    assert evidence.status == EvidenceResolutionStatus.CORROBORATED
    assert evidence.retains_wall_continuity is True
    assert pytest.approx(evidence.clear_opening_width_m, rel=1e-2) == 0.82
    assert pytest.approx(evidence.pocket_length_m, rel=1e-2) == 0.84
    assert pytest.approx(evidence.total_frame_length_m, rel=1e-2) == 1.66
    assert evidence.commercial_projection_allowed is False
    assert evidence.takeoff_eligible is False


def test_negative_insufficient_pocket_length():
    authority = CavitySliderPocketJambShadowAuthority()
    # Clear opening: 41 pt => 0.82 m
    # Pocket: only 15 pt => 0.30 m (cannot fit 0.82m door leaf)
    wall_pts = [(0.0, 100.0), (200.0, 100.0)]
    clear_span = ((50.0, 100.0), (91.0, 100.0))
    pocket_span = ((91.0, 100.0), (106.0, 100.0))

    evidence = authority.evaluate_cavity_slider(
        wall_id="WALL_INT_07",
        wall_centerline_pts=wall_pts,
        clear_opening_span=clear_span,
        pocket_recess_span=pocket_span,
        operation=PocketDoorLeafOperation.SINGLE_SLIDING,
        wall_thickness_m=0.09,
        scale_ratio=0.02,
    )

    assert evidence.status == EvidenceResolutionStatus.ABSTAINED
    assert "insufficient" in evidence.notes


def test_negative_clear_opening_out_of_bounds():
    authority = CavitySliderPocketJambShadowAuthority()
    # Clear opening: 10 pt => 0.20 m (too narrow for door)
    wall_pts = [(0.0, 100.0), (200.0, 100.0)]
    clear_span = ((50.0, 100.0), (60.0, 100.0))
    pocket_span = ((60.0, 100.0), (70.0, 100.0))

    evidence = authority.evaluate_cavity_slider(
        wall_id="WALL_INT_07",
        wall_centerline_pts=wall_pts,
        clear_opening_span=clear_span,
        pocket_recess_span=pocket_span,
        operation=PocketDoorLeafOperation.SINGLE_SLIDING,
        wall_thickness_m=0.09,
        scale_ratio=0.02,
    )

    assert evidence.status == EvidenceResolutionStatus.ABSTAINED
    assert "outside physical bounds" in evidence.notes


def test_negative_incompatible_wall_thickness():
    authority = CavitySliderPocketJambShadowAuthority()
    wall_pts = [(0.0, 100.0), (200.0, 100.0)]
    clear_span = ((50.0, 100.0), (91.0, 100.0))
    pocket_span = ((91.0, 100.0), (133.0, 100.0))

    # Thickness 0.02 m (20mm) cannot house cavity frame
    evidence = authority.evaluate_cavity_slider(
        wall_id="WALL_INT_07",
        wall_centerline_pts=wall_pts,
        clear_opening_span=clear_span,
        pocket_recess_span=pocket_span,
        operation=PocketDoorLeafOperation.SINGLE_SLIDING,
        wall_thickness_m=0.02,
        scale_ratio=0.02,
    )

    assert evidence.status == EvidenceResolutionStatus.ABSTAINED
    assert "incompatible with cavity pocket framing" in evidence.notes


def test_positive_double_bi_parting_pocket():
    authority = CavitySliderPocketJambShadowAuthority()
    # Double bi-parting: 1.60 m clear opening, 1.64 m pocket total (two pockets)
    wall_pts = [(0.0, 100.0), (300.0, 100.0)]
    clear_span = ((70.0, 100.0), (150.0, 100.0))  # 80 pt => 1.60 m
    pocket_span = ((150.0, 100.0), (232.0, 100.0))  # 82 pt => 1.64 m

    evidence = authority.evaluate_cavity_slider(
        wall_id="WALL_INT_08",
        wall_centerline_pts=wall_pts,
        clear_opening_span=clear_span,
        pocket_recess_span=pocket_span,
        operation=PocketDoorLeafOperation.DOUBLE_BI_PARTING,
        wall_thickness_m=0.09,
        scale_ratio=0.02,
    )

    assert evidence.status == EvidenceResolutionStatus.CORROBORATED
    assert pytest.approx(evidence.clear_opening_width_m, rel=1e-2) == 1.60
