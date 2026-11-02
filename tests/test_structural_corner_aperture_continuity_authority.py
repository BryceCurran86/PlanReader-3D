"""Unit and regression tests for Structural Corner Aperture and Pier Miter Continuity Shadow Authority."""

from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_structural_corner_aperture_continuity_authority import (
    CornerApertureClassification,
    CornerPostCondition,
    StructuralCornerApertureContinuityAuthority,
)


@pytest.fixture
def authority() -> StructuralCornerApertureContinuityAuthority:
    return StructuralCornerApertureContinuityAuthority()


def test_positive_postless_butt_joint_corner_aperture(
    authority: StructuralCornerApertureContinuityAuthority,
) -> None:
    corner = (200.0, 300.0)
    jamb_a = (200.0, 380.0)  # L_A = 80 pt
    jamb_b = (260.0, 300.0)  # L_B = 60 pt

    record = authority.evaluate_corner_aperture(
        jamb_a=jamb_a,
        jamb_b=jamb_b,
        corner_vertex=corner,
        host_wall_a_id="WALL_SOUTH",
        host_wall_b_id="WALL_EAST",
        post_dimension_pt=0.0,
    )
    assert (
        record.classification == CornerApertureClassification.CORNER_APERTURE_CONFIRMED
    )
    assert record.post_condition == CornerPostCondition.POSTLESS_BUTT_JOINT
    assert record.total_girth_pt == pytest.approx(140.0, abs=0.01)
    assert record.diagonal_chord_pt == pytest.approx(
        100.0, abs=0.01
    )  # 3-4-5 right triangle
    assert record.corner_angle_deg == pytest.approx(90.0, abs=0.1)
    assert record.status == EvidenceResolutionStatus.CANDIDATE
    assert record.shadow_only is True
    assert record.commercial_projection_allowed is False


def test_positive_structural_corner_post(
    authority: StructuralCornerApertureContinuityAuthority,
) -> None:
    corner = (200.0, 300.0)
    jamb_a = (200.0, 380.0)
    jamb_b = (260.0, 300.0)

    record = authority.evaluate_corner_aperture(
        jamb_a=jamb_a,
        jamb_b=jamb_b,
        corner_vertex=corner,
        host_wall_a_id="WALL_SOUTH",
        host_wall_b_id="WALL_EAST",
        post_dimension_pt=5.0,  # 5 pt structural SHS post
    )
    assert (
        record.classification == CornerApertureClassification.CORNER_APERTURE_CONFIRMED
    )
    assert record.post_condition == CornerPostCondition.STRUCTURAL_CORNER_POST
    assert record.post_dimension_pt == pytest.approx(5.0, abs=0.01)
    assert record.status == EvidenceResolutionStatus.CANDIDATE


def test_non_orthogonal_angle_fails_closed(
    authority: StructuralCornerApertureContinuityAuthority,
) -> None:
    corner = (200.0, 300.0)
    jamb_a = (200.0, 380.0)
    jamb_b = (260.0, 360.0)  # angled leg (deviates by ~45 deg)

    record = authority.evaluate_corner_aperture(
        jamb_a=jamb_a,
        jamb_b=jamb_b,
        corner_vertex=corner,
        host_wall_a_id="WALL_SOUTH",
        host_wall_b_id="WALL_ANGLED",
    )
    assert (
        record.classification
        == CornerApertureClassification.ABSTAINED_NON_ORTHOGONAL_ANGLE
    )
    assert record.status == EvidenceResolutionStatus.ABSTAINED
    assert "outside orthogonal bounds" in record.notes


def test_degenerate_leg_span_fails_closed(
    authority: StructuralCornerApertureContinuityAuthority,
) -> None:
    corner = (200.0, 300.0)
    jamb_a = (200.0, 308.0)  # L_A = 8 pt (< 15 pt threshold)
    jamb_b = (260.0, 300.0)

    record = authority.evaluate_corner_aperture(
        jamb_a=jamb_a,
        jamb_b=jamb_b,
        corner_vertex=corner,
        host_wall_a_id="WALL_SOUTH",
        host_wall_b_id="WALL_EAST",
    )
    assert (
        record.classification == CornerApertureClassification.ABSTAINED_DEGENERATE_LEG
    )
    assert record.status == EvidenceResolutionStatus.ABSTAINED


def test_excessive_post_dimension_fails_closed(
    authority: StructuralCornerApertureContinuityAuthority,
) -> None:
    corner = (200.0, 300.0)
    jamb_a = (200.0, 380.0)
    jamb_b = (260.0, 300.0)

    record = authority.evaluate_corner_aperture(
        jamb_a=jamb_a,
        jamb_b=jamb_b,
        corner_vertex=corner,
        host_wall_a_id="WALL_SOUTH",
        host_wall_b_id="WALL_EAST",
        post_dimension_pt=25.0,  # exceeds 15 pt max post dimension
    )
    assert (
        record.classification
        == CornerApertureClassification.ABSTAINED_EXCESSIVE_POST_DIMENSION
    )
    assert record.status == EvidenceResolutionStatus.ABSTAINED


def test_leg_order_invariance(
    authority: StructuralCornerApertureContinuityAuthority,
) -> None:
    corner = (200.0, 300.0)
    jamb_a = (200.0, 380.0)
    jamb_b = (260.0, 300.0)

    rec_fwd = authority.evaluate_corner_aperture(
        jamb_a=jamb_a,
        jamb_b=jamb_b,
        corner_vertex=corner,
        host_wall_a_id="WALL_SOUTH",
        host_wall_b_id="WALL_EAST",
    )
    rec_rev = authority.evaluate_corner_aperture(
        jamb_a=jamb_b,
        jamb_b=jamb_a,
        corner_vertex=corner,
        host_wall_a_id="WALL_EAST",
        host_wall_b_id="WALL_SOUTH",
    )
    assert rec_fwd.contract_id == rec_rev.contract_id
    assert rec_fwd.total_girth_pt == rec_rev.total_girth_pt
    assert rec_fwd.diagonal_chord_pt == rec_rev.diagonal_chord_pt


def test_metamorphic_rotation_and_translation_invariance(
    authority: StructuralCornerApertureContinuityAuthority,
) -> None:
    corner = (200.0, 300.0)
    jamb_a = (200.0, 380.0)  # L_A = 80
    jamb_b = (260.0, 300.0)  # L_B = 60

    base_rec = authority.evaluate_corner_aperture(
        jamb_a=jamb_a,
        jamb_b=jamb_b,
        corner_vertex=corner,
        host_wall_a_id="WALL_A",
        host_wall_b_id="WALL_B",
    )

    # Rotate by 90 degrees and translate by (+150, -50)
    # R(90): (x, y) -> (-y, x)
    def transform(p: tuple[float, float]) -> tuple[float, float]:
        rx = -p[1] + 150.0
        ry = p[0] - 50.0
        return rx, ry

    rot_corner = transform(corner)
    rot_jamb_a = transform(jamb_a)
    rot_jamb_b = transform(jamb_b)

    rot_rec = authority.evaluate_corner_aperture(
        jamb_a=rot_jamb_a,
        jamb_b=rot_jamb_b,
        corner_vertex=rot_corner,
        host_wall_a_id="WALL_A",
        host_wall_b_id="WALL_B",
    )
    assert rot_rec.total_girth_pt == pytest.approx(base_rec.total_girth_pt, abs=0.01)
    assert rot_rec.diagonal_chord_pt == pytest.approx(
        base_rec.diagonal_chord_pt, abs=0.01
    )
    assert rot_rec.corner_angle_deg == pytest.approx(base_rec.corner_angle_deg, abs=0.1)


def test_to_dict_schema_invariants(
    authority: StructuralCornerApertureContinuityAuthority,
) -> None:
    corner = (200.0, 300.0)
    jamb_a = (200.0, 380.0)
    jamb_b = (260.0, 300.0)

    record = authority.evaluate_corner_aperture(
        jamb_a=jamb_a,
        jamb_b=jamb_b,
        corner_vertex=corner,
        host_wall_a_id="WALL_SOUTH",
        host_wall_b_id="WALL_EAST",
    )
    d = record.to_dict()
    assert d["schema_version"] == "1.0.0"
    assert d["contract_id"] == record.contract_id
    assert d["shadow_only"] is True
    assert d["commercial_projection_allowed"] is False
    assert d["takeoff_eligible"] is False
    assert "leg_a" in d
    assert "leg_b" in d
    assert isinstance(d["corner_vertex"], list)
