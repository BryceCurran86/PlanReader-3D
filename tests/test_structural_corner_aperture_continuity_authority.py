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
    assert record.post_condition == CornerPostCondition.UNRESOLVED_CORNER_CONDITION
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
    assert record.post_condition == CornerPostCondition.UNRESOLVED_CORNER_CONDITION
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


def test_explicit_post_dimension_cannot_authenticate_physical_post(authority):
    for dimension in (0.0, 2.0, 5.0):
        record = authority.evaluate_corner_aperture(
            jamb_a=(200.0, 380.0), jamb_b=(260.0, 300.0),
            corner_vertex=(200.0, 300.0),
            host_wall_a_id="WALL_A", host_wall_b_id="WALL_B",
            post_dimension_pt=dimension, scale_ratio=0.01764,
        )
        assert record.classification == CornerApertureClassification.GEOMETRIC_CANDIDATE
        assert record.post_condition == CornerPostCondition.UNRESOLVED_CORNER_CONDITION
        assert record.status == EvidenceResolutionStatus.CANDIDATE
        assert record.first_remaining_gate == "original_source_corner_host_frame_unverified"
        assert not record.commercial_projection_allowed and not record.takeoff_eligible


def test_serialized_corner_geometry_preserves_subcentipoint_source_hypotheses(authority):
    kwargs = dict(
        jamb_a=(200.0, 380.0), jamb_b=(260.0, 300.0),
        corner_vertex=(200.0, 300.0),
        host_wall_a_id="WALL_A", host_wall_b_id="WALL_B",
        post_dimension_pt=0.0, scale_ratio=0.01764,
    )
    base = authority.evaluate_corner_aperture(**kwargs)
    shifted = authority.evaluate_corner_aperture(
        **(kwargs | {"jamb_a": (200.001, 380.0)})
    )
    assert base.contract_id != shifted.contract_id
    assert base.to_dict()["leg_a"]["terminal_jamb"] != shifted.to_dict()["leg_a"]["terminal_jamb"]
    assert shifted.to_dict()["leg_a"]["terminal_jamb"] == [200.001, 380.0]
    assert base.to_dict()["leg_a"]["axis_vector"] != shifted.to_dict()["leg_a"]["axis_vector"]
    assert base.to_dict()["total_girth_pt"] != shifted.to_dict()["total_girth_pt"]
    assert base.shadow_only and shifted.shadow_only
    assert not base.takeoff_eligible and not shifted.takeoff_eligible


def test_serialized_post_and_scale_receipts_do_not_round_into_same_values(authority):
    kwargs = dict(
        jamb_a=(200.0, 380.0), jamb_b=(260.0, 300.0),
        corner_vertex=(200.0, 300.0),
        host_wall_a_id="WALL_A", host_wall_b_id="WALL_B",
        post_dimension_pt=0.0, scale_ratio=0.01764,
    )
    base = authority.evaluate_corner_aperture(**kwargs)
    changed_post = authority.evaluate_corner_aperture(
        **(kwargs | {"post_dimension_pt": 0.001})
    )
    changed_scale = authority.evaluate_corner_aperture(
        **(kwargs | {"scale_ratio": 0.017640001})
    )
    assert base.contract_id != changed_post.contract_id
    assert base.to_dict()["post_dimension_pt"] == 0.0
    assert changed_post.to_dict()["post_dimension_pt"] == 0.001
    assert base.contract_id != changed_scale.contract_id
    assert base.to_dict()["total_girth_m"] != changed_scale.to_dict()["total_girth_m"]
    assert base.to_dict()["leg_a"]["leg_span_m"] != changed_scale.to_dict()["leg_a"]["leg_span_m"]
    for record in (base, changed_post, changed_scale):
        assert record.classification == CornerApertureClassification.GEOMETRIC_CANDIDATE
        assert record.post_condition == CornerPostCondition.UNRESOLVED_CORNER_CONDITION
        assert not record.takeoff_eligible and not record.commercial_projection_allowed


def test_serialized_abstention_retains_exact_geometry_without_metric(authority):
    record = authority.evaluate_corner_aperture(
        jamb_a=(200.001, 380.0), jamb_b=(260.0, 300.0),
        corner_vertex=(200.0, 300.0),
        host_wall_a_id="WALL_A", host_wall_b_id="WALL_B",
        post_dimension_pt=0.001,
    )
    payload = record.to_dict()
    assert record.status == EvidenceResolutionStatus.ABSTAINED
    assert payload["leg_a"]["terminal_jamb"] == [200.001, 380.0]
    assert payload["post_dimension_pt"] == 0.001
    assert payload["total_girth_m"] is None
    assert payload["leg_a"]["leg_span_m"] is None
    assert payload["shadow_only"] and not payload["takeoff_eligible"]


def test_same_host_wall_cannot_create_dual_host_corner_candidate(authority):
    """Two orthogonal legs with one host identity must abstain, not mint girth."""
    kwargs = dict(
        jamb_a=(200.0, 380.0), jamb_b=(260.0, 300.0),
        corner_vertex=(200.0, 300.0),
        host_wall_a_id="SAME_WALL", host_wall_b_id="SAME_WALL",
        post_dimension_pt=0.0, scale_ratio=0.01764,
    )
    first = authority.evaluate_corner_aperture(**kwargs)
    reversed_legs = authority.evaluate_corner_aperture(**(
        kwargs | {"jamb_a": kwargs["jamb_b"], "jamb_b": kwargs["jamb_a"]}
    ))
    for record in (first, reversed_legs):
        assert record.classification == CornerApertureClassification.ABSTAINED_UNVERIFIED_SOURCE
        assert record.status == EvidenceResolutionStatus.ABSTAINED
        assert record.first_remaining_gate == "distinct_corner_host_walls_unverified"
        assert record.total_girth_m is None
        assert record.leg_a.leg_span_m is None
        assert record.leg_b.leg_span_m is None
        assert record.to_dict()["total_girth_m"] is None
        assert record.shadow_only and not record.takeoff_eligible
        assert not record.commercial_projection_allowed
        assert record.total_girth_pt == 140.0
    assert first.contract_id == reversed_legs.contract_id
    distinct = authority.evaluate_corner_aperture(**(
        kwargs | {"host_wall_b_id": "SECOND_WALL"}
    ))
    assert distinct.classification == CornerApertureClassification.GEOMETRIC_CANDIDATE
    assert distinct.total_girth_m is not None
    assert distinct.contract_id != first.contract_id


@pytest.mark.parametrize("field", ["jamb_a", "jamb_b", "corner_vertex"])
@pytest.mark.parametrize("huge", [float(2**53) + 2.0, -(float(2**53) + 2.0)])
def test_oversized_native_float_corner_points_rejected(authority, field, huge):
    kwargs = dict(
        jamb_a=(200.0, 380.0), jamb_b=(260.0, 300.0),
        corner_vertex=(200.0, 300.0),
        host_wall_a_id="WALL_A", host_wall_b_id="WALL_B",
        post_dimension_pt=0.0, scale_ratio=0.01764,
    )
    original_point = [huge, 300.0]
    with pytest.raises(ValueError, match=f"{field} requires finite real coordinates"):
        authority.evaluate_corner_aperture(**(kwargs | {field: original_point}))
    assert original_point == [huge, 300.0]


def test_inclusive_corner_source_coordinate_boundary_is_shadow_only(authority):
    limit = float(2**53)
    kwargs = dict(
        jamb_a=(limit, limit - 80.0),
        jamb_b=(limit - 60.0, limit),
        corner_vertex=(limit, limit),
        host_wall_a_id="WALL_A", host_wall_b_id="WALL_B",
        post_dimension_pt=None, scale_ratio=None,
    )
    before = dict(kwargs)
    first = authority.evaluate_corner_aperture(**kwargs)
    second = authority.evaluate_corner_aperture(**kwargs)
    assert kwargs == before
    assert first == second
    assert first.corner_vertex == (limit, limit)
    assert first.total_girth_pt == 140.0
    assert first.classification == CornerApertureClassification.ABSTAINED_UNVERIFIED_SOURCE
    assert first.first_remaining_gate == "original_source_scale_or_post_unverified"
    assert first.total_girth_m is None
    assert first.leg_a.leg_span_m is None
    assert first.leg_b.leg_span_m is None
    assert first.shadow_only and not first.takeoff_eligible
    assert not first.commercial_projection_allowed


def _source_identity_corner_kwargs():
    return dict(
        jamb_a=[200.0, 380.0],
        jamb_b=[260.0, 300.0],
        corner_vertex=[200.0, 300.0],
        host_wall_a_id="WALL_A",
        host_wall_b_id="WALL_B",
        context_label="CORNER_APERTURE",
        post_dimension_pt=0.0,
        scale_ratio=0.01764,
    )


def test_padded_corner_host_alias_cannot_evade_distinct_wall_gate(authority):
    """A padded spelling of the same physical wall must not mint two hosts."""
    kw = _source_identity_corner_kwargs()
    kw["host_wall_b_id"] = "WALL_A"
    same = authority.evaluate_corner_aperture(**kw)
    assert same.status is EvidenceResolutionStatus.ABSTAINED
    assert same.first_remaining_gate == "distinct_corner_host_walls_unverified"
    assert same.total_girth_m is None
    for alias in ("WALL_A ", " WALL_A", "\tWALL_A", "WALL_A\n"):
        before = tuple(kw["jamb_a"]), tuple(kw["jamb_b"]), tuple(kw["corner_vertex"])
        with pytest.raises(ValueError, match="exact printable source identity"):
            authority.evaluate_corner_aperture(**(kw | {"host_wall_b_id": alias}))
        assert before == (tuple(kw["jamb_a"]), tuple(kw["jamb_b"]),
                          tuple(kw["corner_vertex"]))
    assert same.shadow_only and not same.takeoff_eligible
    assert not same.commercial_projection_allowed


@pytest.mark.parametrize("field", [
    "host_wall_a_id", "host_wall_b_id", "context_label",
])
@pytest.mark.parametrize("bad", [
    "", " ", " WALL_A", "WALL_A ", "WALL\nA", "WALL\tA",
    "WALL\x00A", "WALL\u200bA", True, None, 123,
])
def test_corner_source_identity_must_be_exact_and_printable(
    authority, field, bad,
):
    kw = _source_identity_corner_kwargs()
    with pytest.raises(ValueError, match="exact printable source identity"):
        authority.evaluate_corner_aperture(**(kw | {field: bad}))
    assert kw["jamb_a"] == [200.0, 380.0]
    assert kw["jamb_b"] == [260.0, 300.0]
    assert kw["corner_vertex"] == [200.0, 300.0]


def test_distinct_exact_corner_hosts_keep_shadow_candidate_and_order_replay(
    authority,
):
    kw = _source_identity_corner_kwargs()
    first = authority.evaluate_corner_aperture(**kw)
    second = authority.evaluate_corner_aperture(**kw)
    swapped = authority.evaluate_corner_aperture(**(
        kw | dict(
            jamb_a=kw["jamb_b"], jamb_b=kw["jamb_a"],
            host_wall_a_id=kw["host_wall_b_id"],
            host_wall_b_id=kw["host_wall_a_id"],
        )
    ))
    assert first == second
    assert first.contract_id == swapped.contract_id
    assert first.classification is CornerApertureClassification.GEOMETRIC_CANDIDATE
    assert first.first_remaining_gate == "original_source_corner_host_frame_unverified"
    assert first.leg_a.host_wall_id != first.leg_b.host_wall_id
    assert first.to_dict()["leg_a"]["host_wall_id"] in ("WALL_A", "WALL_B")
    assert first.to_dict()["commercial_projection_allowed"] is False
    assert first.to_dict()["takeoff_eligible"] is False
    assert kw["jamb_a"] == [200.0, 380.0]
    assert kw["jamb_b"] == [260.0, 300.0]
    assert kw["corner_vertex"] == [200.0, 300.0]


def test_corner_host_identity_rejects_string_subclass(authority):
    class Impostor(str):
        pass

    kw = _source_identity_corner_kwargs()
    with pytest.raises(ValueError, match="exact printable source identity"):
        authority.evaluate_corner_aperture(**(
            kw | {"host_wall_a_id": Impostor("WALL_A")}
        ))


def test_public_corner_record_replacement_cannot_mint_post_or_commercial_authority(
    authority: StructuralCornerApertureContinuityAuthority,
) -> None:
    from dataclasses import replace

    common = dict(
        jamb_a=(200.0, 380.0), jamb_b=(260.0, 300.0),
        corner_vertex=(200.0, 300.0),
        host_wall_a_id="WALL_SOUTH", host_wall_b_id="WALL_EAST",
        post_dimension_pt=0.0,
    )
    candidate = authority.evaluate_corner_aperture(**common, scale_ratio=0.01764)
    abstained = authority.evaluate_corner_aperture(**common)
    assert candidate.classification is CornerApertureClassification.GEOMETRIC_CANDIDATE
    assert candidate.status is EvidenceResolutionStatus.CANDIDATE
    assert abstained.classification is CornerApertureClassification.ABSTAINED_UNVERIFIED_SOURCE
    assert abstained.status is EvidenceResolutionStatus.ABSTAINED
    assert replace(candidate) == candidate and replace(abstained) == abstained
    for changes in (
        {"classification": CornerApertureClassification.CORNER_APERTURE_CONFIRMED},
        {"status": EvidenceResolutionStatus.CORROBORATED},
        {"post_condition": CornerPostCondition.STRUCTURAL_CORNER_POST},
        {"commercial_projection_allowed": True},
        {"takeoff_eligible": True},
        {"shadow_only": False},
    ):
        with pytest.raises(ValueError, match="source-neutral corner"):
            replace(candidate, **changes)
    for changes in (
        {"first_remaining_gate": "none"},
        {"first_remaining_gate": "source_verified_by_caller"},
        {"status": EvidenceResolutionStatus.ABSTAINED},
    ):
        with pytest.raises(ValueError, match="classification and source gate conflict"):
            replace(candidate, **changes)
    for changes in (
        {"first_remaining_gate": "none"},
        {"status": EvidenceResolutionStatus.CANDIDATE},
        {"total_girth_m": 2.4696},
        {"leg_a": replace(abstained.leg_a, leg_span_m=1.0)},
    ):
        with pytest.raises(ValueError, match="classification and source gate conflict"):
            replace(abstained, **changes)
    for record in (candidate, abstained):
        assert record.post_condition is CornerPostCondition.UNRESOLVED_CORNER_CONDITION
        assert record.shadow_only is True
        assert record.takeoff_eligible is False
        assert record.commercial_projection_allowed is False
    assert authority.evaluate_corner_aperture(**common, scale_ratio=0.01764) == candidate


def test_public_corner_numeric_record_replacements_fail_closed(authority):
    from dataclasses import replace

    kw = dict(
        jamb_a=(200.0, 380.0), jamb_b=(260.0, 300.0),
        corner_vertex=(200.0, 300.0),
        host_wall_a_id="WALL_A", host_wall_b_id="WALL_B",
        post_dimension_pt=0.0, scale_ratio=0.01764,
    )
    candidate = authority.evaluate_corner_aperture(**kw)
    abstained = authority.evaluate_corner_aperture(**(kw | {"scale_ratio": None}))
    for record in (candidate, abstained):
        assert replace(record) == record
        for field in ("corner_angle_deg", "total_girth_pt", "diagonal_chord_pt"):
            for bad in (float("nan"), float("inf"), -1.0):
                with pytest.raises(ValueError, match="numeric evidence"):
                    replace(record, **{field: bad})
        for bad in (float("nan"), float("inf"), -1.0):
            with pytest.raises(ValueError, match="numeric evidence"):
                replace(record, post_dimension_pt=bad)
        for bad in (float("nan"), float("inf"), float(2**53) + 2.0):
            with pytest.raises(ValueError, match="numeric evidence"):
                replace(record, corner_vertex=(bad, 300.0))
        for field in ("leg_a", "leg_b"):
            leg = getattr(record, field)
            for bad in (float("nan"), float("inf"), -1.0):
                with pytest.raises(ValueError, match="numeric evidence"):
                    replace(leg, leg_span_pt=bad)
            for bad in (float("nan"), float("inf"), 0.0, -1.0):
                with pytest.raises(ValueError, match="numeric evidence"):
                    replace(leg, leg_span_m=bad)
            for bad in (float("nan"), float("inf"), float(2**53) + 2.0):
                with pytest.raises(ValueError, match="numeric evidence"):
                    replace(leg, terminal_jamb=(bad, 300.0))
            with pytest.raises(ValueError, match="numeric evidence"):
                replace(leg, axis_vector=(2.0, 0.0))
        with pytest.raises(ValueError, match="numeric evidence"):
            replace(record, total_girth_pt=record.total_girth_pt + 100.0)
        with pytest.raises(ValueError, match="numeric evidence"):
            replace(record, diagonal_chord_pt=record.diagonal_chord_pt + 100.0)
    for bad in (float("nan"), float("inf"), 0.0, -1.0):
        with pytest.raises(ValueError, match="numeric evidence"):
            replace(candidate, total_girth_m=bad)
    assert abstained.total_girth_m is None
    assert candidate.shadow_only and not candidate.takeoff_eligible
    assert abstained.shadow_only and not abstained.commercial_projection_allowed
    assert authority.evaluate_corner_aperture(**kw) == candidate


@pytest.mark.parametrize("jamb_a,jamb_b", [
    ((200.0, 380.0), (260.0, 300.0)),
    ((140.0, 300.0), (200.0, 380.0)),
])
def test_corner_leg_direct_replacement_requires_owned_axis_and_span(
    authority, jamb_a, jamb_b,
):
    """Each nested leg must own its span and outward unit axis."""
    from dataclasses import replace

    kw = dict(
        jamb_a=jamb_a, jamb_b=jamb_b, corner_vertex=(200.0, 300.0),
        host_wall_a_id="WALL_A", host_wall_b_id="WALL_B",
        post_dimension_pt=0.0, scale_ratio=0.01764,
    )
    candidate = authority.evaluate_corner_aperture(**kw)
    abstained = authority.evaluate_corner_aperture(**(kw | {"scale_ratio": None}))
    assert candidate.status is EvidenceResolutionStatus.CANDIDATE
    assert abstained.status is EvidenceResolutionStatus.ABSTAINED
    assert replace(candidate) == candidate and replace(abstained) == abstained
    for record in (candidate, abstained):
        assert record.shadow_only and not record.takeoff_eligible
        assert not record.commercial_projection_allowed
        for leg in (record.leg_a, record.leg_b):
            assert replace(leg) == leg
            ax, ay = leg.axis_vector
            for changes in (
                {"axis_vector": (0.0, 0.0)},
                {"axis_vector": (0.5, 0.0)},
                {"axis_vector": (-ax, -ay)},
                {"axis_vector": (-ay, ax)},
                {"leg_span_pt": leg.leg_span_pt + 1.0},
            ):
                with pytest.raises(ValueError, match="corner leg .*geometry"):
                    replace(leg, **changes)
    assert authority.evaluate_corner_aperture(**kw) == candidate


def test_zero_span_corner_leg_retains_abstention_but_cannot_forge_axis(authority):
    """A degenerate source leg has no unit axis and cannot be promoted."""
    from dataclasses import replace

    record = authority.evaluate_corner_aperture(
        jamb_a=(200.0, 300.0), jamb_b=(260.0, 300.0),
        corner_vertex=(200.0, 300.0),
        host_wall_a_id="WALL_A", host_wall_b_id="WALL_B",
        post_dimension_pt=0.0, scale_ratio=0.01764,
    )
    assert record.classification is CornerApertureClassification.ABSTAINED_DEGENERATE_LEG
    zero = next(leg for leg in (record.leg_a, record.leg_b) if leg.leg_span_pt == 0)
    assert zero.axis_vector == (0.0, 0.0)
    assert replace(zero) == zero
    with pytest.raises(ValueError, match="axis conflicts"):
        replace(zero, axis_vector=(1.0, 0.0))
    with pytest.raises(ValueError, match="conflicts with geometry"):
        replace(zero, leg_span_pt=1.0)
    assert record.total_girth_m is None
    assert record.shadow_only and not record.takeoff_eligible


@pytest.mark.parametrize("jamb_a,jamb_b", [
    ((200.0, 380.0), (260.0, 300.0)),
    ((60.0, 80.0), (-80.0, 60.0)),
])
def test_public_corner_angle_must_match_frozen_owned_axes(
    authority, jamb_a, jamb_b,
):
    """Finite 0..180 degrees is not proof of the actual owned leg angle."""
    from dataclasses import replace

    vertex = (200.0, 300.0) if jamb_a[0] == 200.0 else (0.0, 0.0)
    kw = dict(jamb_a=jamb_a, jamb_b=jamb_b, corner_vertex=vertex,
              host_wall_a_id="WALL_A", host_wall_b_id="WALL_B",
              post_dimension_pt=0.0, scale_ratio=0.01764)
    original = dict(kw)
    candidate = authority.evaluate_corner_aperture(**kw)
    abstained = authority.evaluate_corner_aperture(
        **(kw | {"scale_ratio": None}))
    assert candidate.status is EvidenceResolutionStatus.CANDIDATE
    assert abstained.status is EvidenceResolutionStatus.ABSTAINED
    for record in (candidate, abstained):
        assert replace(record) == record
        assert record.corner_angle_deg == pytest.approx(90.0)
        for forged_angle in (0.0, 75.0, 80.0, 105.0, 180.0):
            with pytest.raises(ValueError, match="leg angle"):
                replace(record, corner_angle_deg=forged_angle)
        assert record.shadow_only and not record.takeoff_eligible
        assert not record.commercial_projection_allowed
    swapped = authority.evaluate_corner_aperture(**(
        kw | dict(jamb_a=kw["jamb_b"], jamb_b=kw["jamb_a"],
                  host_wall_a_id=kw["host_wall_b_id"],
                  host_wall_b_id=kw["host_wall_a_id"])
    ))
    assert swapped == candidate
    assert kw == original
    assert authority.evaluate_corner_aperture(**kw) == candidate


def test_public_corner_zero_leg_abstention_keeps_producer_angle(authority):
    from dataclasses import replace

    kw = dict(jamb_a=(200.0, 300.0), jamb_b=(260.0, 300.0),
              corner_vertex=(200.0, 300.0),
              host_wall_a_id="WALL_A", host_wall_b_id="WALL_B",
              post_dimension_pt=0.0, scale_ratio=0.01764)
    record = authority.evaluate_corner_aperture(**kw)
    assert record.classification is CornerApertureClassification.ABSTAINED_DEGENERATE_LEG
    assert record.corner_angle_deg == pytest.approx(90.0)
    assert replace(record) == record
    with pytest.raises(ValueError, match="leg angle"):
        replace(record, corner_angle_deg=80.0)
    assert record.total_girth_m is None
    assert record.shadow_only and not record.commercial_projection_allowed
    assert authority.evaluate_corner_aperture(**kw) == record
