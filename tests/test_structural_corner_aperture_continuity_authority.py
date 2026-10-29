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
        scale_ratio=0.01764,
    )
    assert (
        record.classification == CornerApertureClassification.GEOMETRIC_CANDIDATE
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
        scale_ratio=0.01764,
    )
    assert (
        record.classification == CornerApertureClassification.GEOMETRIC_CANDIDATE
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


def test_missing_scale_or_post_is_typed_abstention_with_null_metrics(authority):
    for changed in ({}, {"post_dimension_pt": 0.0}, {"scale_ratio": 0.01764}):
        kw = dict(
            jamb_a=(200.0, 380.0), jamb_b=(260.0, 300.0),
            corner_vertex=(200.0, 300.0),
            host_wall_a_id="WALL_A", host_wall_b_id="WALL_B",
        )
        kw.update(changed)
        record = authority.evaluate_corner_aperture(**kw)
        assert record.classification == CornerApertureClassification.ABSTAINED_UNVERIFIED_SOURCE
        assert record.status == EvidenceResolutionStatus.ABSTAINED
        assert record.first_remaining_gate == "original_source_scale_or_post_unverified"
        assert record.total_girth_m is None
        assert record.leg_a.leg_span_m is None
        assert record.leg_b.leg_span_m is None
        assert record.to_dict()["total_girth_m"] is None
        assert record.to_dict()["leg_a"]["leg_span_m"] is None
        assert record.shadow_only and not record.takeoff_eligible
        assert not record.commercial_projection_allowed


@pytest.mark.parametrize("field,bad", [
    ("scale_ratio", float("nan")), ("scale_ratio", float("inf")),
    ("scale_ratio", -1.0), ("scale_ratio", 0.0),
    ("scale_ratio", True), ("scale_ratio", 10**1000),
    ("post_dimension_pt", float("nan")),
    ("post_dimension_pt", float("inf")),
    ("post_dimension_pt", -1.0),
    ("post_dimension_pt", True),
    ("post_dimension_pt", 10**1000),
])
def test_nonfinite_and_untrusted_scale_or_post_rejected(authority, field, bad):
    kw = dict(
        jamb_a=(200.0, 380.0), jamb_b=(260.0, 300.0),
        corner_vertex=(200.0, 300.0),
        host_wall_a_id="WALL_A", host_wall_b_id="WALL_B",
        post_dimension_pt=0.0, scale_ratio=0.01764,
    )
    kw[field] = bad
    with pytest.raises(ValueError):
        authority.evaluate_corner_aperture(**kw)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), True, "bad", 10**1000, 2**53+1])
def test_invalid_or_lossy_jamb_coordinate_rejected(authority, bad):
    with pytest.raises(ValueError):
        authority.evaluate_corner_aperture(
            jamb_a=(bad, 380.0), jamb_b=(260.0, 300.0),
            corner_vertex=(200.0, 300.0),
            host_wall_a_id="WALL_A", host_wall_b_id="WALL_B",
            post_dimension_pt=0.0, scale_ratio=0.01764,
        )


def test_overflowed_geometry_and_hypothetical_metric_rejected(authority):
    for a, b, vertex, ratio in (
        ((-1e308, 0.0), (0.0, 1e308), (1e308, 0.0), 0.01764),
        ((200.0, 380.0), (260.0, 300.0), (200.0, 300.0), 1e308),
    ):
        with pytest.raises(ValueError):
            authority.evaluate_corner_aperture(
                jamb_a=a, jamb_b=b, corner_vertex=vertex,
                host_wall_a_id="WALL_A", host_wall_b_id="WALL_B",
                post_dimension_pt=0.0, scale_ratio=ratio,
            )


def test_rejected_corner_leg_has_no_hypothetical_metric_quantity(authority):
    record = authority.evaluate_corner_aperture(
        jamb_a=(200.0, 305.0), jamb_b=(260.0, 300.0),
        corner_vertex=(200.0, 300.0),
        host_wall_a_id="WALL_A", host_wall_b_id="WALL_B",
        post_dimension_pt=0.0, scale_ratio=0.01764,
    )
    assert record.classification == CornerApertureClassification.ABSTAINED_DEGENERATE_LEG
    assert record.total_girth_m is None
    assert record.leg_a.leg_span_m is None
    assert record.leg_b.leg_span_m is None
    assert record.to_dict()["total_girth_m"] is None


def test_full_precision_scale_post_and_jamb_identity(authority):
    kw = dict(
        jamb_a=(200.0, 380.0), jamb_b=(260.0, 300.0),
        corner_vertex=(200.0, 300.0),
        host_wall_a_id="WALL_A", host_wall_b_id="WALL_B",
        post_dimension_pt=0.0, scale_ratio=0.01764,
    )
    base = authority.evaluate_corner_aperture(**kw)
    assert base.classification == CornerApertureClassification.GEOMETRIC_CANDIDATE
    for change in (
        {"jamb_a": (200.001, 380.0)},
        {"post_dimension_pt": 0.001},
        {"scale_ratio": 0.018},
        {"host_wall_a_id": "OTHER"},
    ):
        assert authority.evaluate_corner_aperture(**(kw | change)).contract_id != base.contract_id
    swapped = kw | dict(
        jamb_a=kw["jamb_b"], jamb_b=kw["jamb_a"],
        host_wall_a_id=kw["host_wall_b_id"], host_wall_b_id=kw["host_wall_a_id"],
    )
    assert authority.evaluate_corner_aperture(**swapped).contract_id == base.contract_id
    assert base.leg_a.leg_id != base.leg_b.leg_id
    assert not base.takeoff_eligible and not base.commercial_projection_allowed


def test_subround_positive_metric_is_not_serialized_as_zero(authority):
    record = authority.evaluate_corner_aperture(
        jamb_a=(200.0, 380.0), jamb_b=(260.0, 300.0),
        corner_vertex=(200.0, 300.0),
        host_wall_a_id="WALL_A", host_wall_b_id="WALL_B",
        post_dimension_pt=0.0, scale_ratio=1e-8,
    )
    assert record.total_girth_m > 0
    assert record.to_dict()["total_girth_m"] > 0
    assert record.to_dict()["leg_a"]["leg_span_m"] > 0


def test_input_arguments_are_not_mutated_and_shadow_never_publishes(authority):
    a = [200.0, 380.0]
    b = [260.0, 300.0]
    vertex = [200.0, 300.0]
    kw = dict(
        jamb_a=a, jamb_b=b, corner_vertex=vertex,
        host_wall_a_id="WALL_A", host_wall_b_id="WALL_B",
        post_dimension_pt=0.0, scale_ratio=0.01764,
    )
    first = authority.evaluate_corner_aperture(**kw)
    second = authority.evaluate_corner_aperture(**kw)
    assert first == second
    assert a == [200.0, 380.0]
    assert b == [260.0, 300.0]
    assert vertex == [200.0, 300.0]
    assert first.to_dict()["commercial_projection_allowed"] is False
    assert first.to_dict()["takeoff_eligible"] is False
