"""Unit tests for Producer-Owned Wall Junction Corner Mass Deduction Authority.

Tests positive, negative, and edge-case boundary scenarios.
"""

import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_wall_junction_corner_mass_deduction_shadow import (
    JunctionKind,
    WallJunctionCornerMassDeductionShadowAuthority,
    WallJunctionDeductionEvidence,
)


def test_positive_t_junction_deduction():
    authority = WallJunctionCornerMassDeductionShadowAuthority()
    # Continuous through-wall 110mm brick (0.11m), abutting 90mm stud wall (0.09m).
    # Height = 2.7m.
    evidence = authority.evaluate_t_junction(
        through_wall_id="WALL_EXT_01",
        abutting_wall_id="WALL_INT_01",
        junction_point=(150.0, 200.0),
        through_wall_thickness_m=0.11,
        abutting_wall_thickness_m=0.09,
        wall_height_m=2.7,
    )

    assert evidence.status == EvidenceResolutionStatus.CORROBORATED
    assert evidence.junction_kind == JunctionKind.T_JUNCTION_ABUTMENT
    # Overlap area = 0.11 * 0.09 = 0.0099 m²
    assert pytest.approx(evidence.overlap_area_sqm, rel=1e-3) == 0.0099
    # Deducted volume = 0.0099 * 2.7 = 0.02673 m³
    assert pytest.approx(evidence.deducted_volume_cum, rel=1e-3) == 0.02673
    # Obscured face length = 0.09m
    assert pytest.approx(evidence.obscured_face_length_m, rel=1e-3) == 0.09
    # Obscured finish area = 0.09 * 2.7 = 0.243 m²
    assert pytest.approx(evidence.obscured_finish_area_sqm, rel=1e-3) == 0.243
    assert evidence.commercial_projection_allowed is False
    assert evidence.takeoff_eligible is False


def test_positive_l_junction_corner_deduction():
    authority = WallJunctionCornerMassDeductionShadowAuthority()
    # Two 90mm walls meeting at 90-degree corner. Height = 2.4m.
    evidence = authority.evaluate_l_junction(
        wall1_id="WALL_01",
        wall2_id="WALL_02",
        corner_point=(0.0, 0.0),
        wall1_thickness_m=0.09,
        wall2_thickness_m=0.09,
        wall_height_m=2.4,
    )

    assert evidence.status == EvidenceResolutionStatus.CORROBORATED
    assert evidence.junction_kind == JunctionKind.L_JUNCTION_CORNER
    # Overlap area = 0.09 * 0.09 = 0.0081 m²
    assert pytest.approx(evidence.overlap_area_sqm, rel=1e-3) == 0.0081
    # Deducted volume = 0.0081 * 2.4 = 0.01944 m³
    assert pytest.approx(evidence.deducted_volume_cum, rel=1e-3) == 0.01944
    assert pytest.approx(evidence.obscured_face_length_m, rel=1e-3) == 0.09


def test_negative_invalid_thickness_fails_closed():
    authority = WallJunctionCornerMassDeductionShadowAuthority()
    evidence = authority.evaluate_t_junction(
        through_wall_id="WALL_EXT_01",
        abutting_wall_id="WALL_INT_01",
        junction_point=(150.0, 200.0),
        through_wall_thickness_m=0.02,  # 20mm below threshold
        abutting_wall_thickness_m=0.09,
        wall_height_m=2.7,
    )

    assert evidence.status == EvidenceResolutionStatus.ABSTAINED
    assert "below physical threshold" in evidence.notes


def test_negative_invalid_height_fails_closed():
    authority = WallJunctionCornerMassDeductionShadowAuthority()
    evidence = authority.evaluate_t_junction(
        through_wall_id="WALL_EXT_01",
        abutting_wall_id="WALL_INT_01",
        junction_point=(150.0, 200.0),
        through_wall_thickness_m=0.11,
        abutting_wall_thickness_m=0.09,
        wall_height_m=-1.0,  # Negative height
    )

    assert evidence.status == EvidenceResolutionStatus.ABSTAINED
    assert "outside valid bounds" in evidence.notes


def test_negative_l_junction_zero_height_fails_closed():
    authority = WallJunctionCornerMassDeductionShadowAuthority()
    evidence = authority.evaluate_l_junction(
        wall1_id="WALL_01",
        wall2_id="WALL_02",
        corner_point=(0.0, 0.0),
        wall1_thickness_m=0.09,
        wall2_thickness_m=0.09,
        wall_height_m=0.0,
    )

    assert evidence.status == EvidenceResolutionStatus.ABSTAINED
