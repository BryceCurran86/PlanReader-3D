"""Representation-level invariants for Physical Opening Void V2.

TEST ONLY. These tests strengthen the validator foundation without inventing any
missing host, height, vertical-placement, completeness or unit authority.
"""
from __future__ import annotations

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_identity import (
    PhysicalEquivalenceClass,
    PhysicalWallIdentity,
    classify_physical_wall_pair,
)
from tests.physical_opening_void_geometry_support_v2 import (
    WallLocalRectFixture,
    canonical_rect_signature,
    frame_from_baseline,
    project_span_m,
    reverse_rect_u,
    rigid_transform_point,
    span_is_inside_frame,
)


def _identity(
    *,
    wall_id: str,
    candidate_identity_id: str,
    path: tuple[tuple[float, float], ...],
    primitive_ids: tuple[str, ...],
) -> PhysicalWallIdentity:
    return PhysicalWallIdentity(
        wall_candidate_id=wall_id,
        viewport_id="viewport-a",
        candidate_identity_id=candidate_identity_id,
        path_fingerprint=path,
        source_primitive_ids=primitive_ids,
        edge_ids=(f"edge-{wall_id}",),
        status=EvidenceResolutionStatus.CORROBORATED,
    )


def test_candidate_identity_difference_does_not_prove_distinct_physical_wall() -> None:
    """Candidate addressing must never substitute for publication equivalence."""
    path = ((0.0, 0.0), (500.0, 0.0))
    left = _identity(
        wall_id="wall-a",
        candidate_identity_id="candidate-address-a",
        path=path,
        primitive_ids=("primitive-shared",),
    )
    right = _identity(
        wall_id="wall-b",
        candidate_identity_id="candidate-address-b",
        path=path,
        primitive_ids=("primitive-shared",),
    )

    assert left.candidate_identity_id != right.candidate_identity_id
    assert classify_physical_wall_pair(left, right) == PhysicalEquivalenceClass.SAME_PHYSICAL_WALL


def test_same_path_different_provenance_remains_ambiguous_physical_equivalence() -> None:
    """Geometry equality alone cannot authorize a host/void representation collapse."""
    path = ((0.0, 0.0), (500.0, 0.0))
    left = _identity(
        wall_id="wall-a",
        candidate_identity_id="candidate-address-a",
        path=path,
        primitive_ids=("primitive-a",),
    )
    right = _identity(
        wall_id="wall-b",
        candidate_identity_id="candidate-address-b",
        path=path,
        primitive_ids=("primitive-b",),
    )

    assert (
        classify_physical_wall_pair(left, right)
        == PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE
    )


def test_wall_local_rectangle_rejects_zero_unknown_substitution() -> None:
    """An absent/unknown span cannot be represented as an authoritative zero-area void."""
    for coords in (
        (1.0, 1.0, 0.0, 2.1),
        (1.0, 1.9, 0.9, 0.9),
        (1.9, 1.0, 0.0, 2.1),
    ):
        try:
            WallLocalRectFixture(*coords)
        except ValueError:
            pass
        else:  # pragma: no cover - protects the intended fail-closed test fixture contract
            raise AssertionError("zero/inverted wall-local void must not be represented as valid geometry")


def test_reversed_baseline_has_stable_canonical_rect_serialization() -> None:
    rect = WallLocalRectFixture(u0=1.2, u1=2.1, z0=0.9, z1=3.0)
    reversed_rect = reverse_rect_u(rect, wall_length_m=5.0)

    assert canonical_rect_signature(rect, wall_length_m=5.0) == canonical_rect_signature(
        reversed_rect,
        wall_length_m=5.0,
    )


def test_rigid_drawing_transform_preserves_canonical_wall_local_rect() -> None:
    points_per_m = 100.0
    start = (20.0, 50.0)
    end = (520.0, 50.0)
    jamb_a = (140.0, 50.0)
    jamb_b = (230.0, 50.0)
    frame = frame_from_baseline(start, end, points_per_m=points_per_m)
    u0, u1 = project_span_m(frame, jamb_a, jamb_b)
    rect = WallLocalRectFixture(u0=u0, u1=u1, z0=0.9, z1=3.0)

    transformed = [
        rigid_transform_point(point, angle_rad=0.731, tx=81.0, ty=-24.0)
        for point in (start, end, jamb_a, jamb_b)
    ]
    transformed_frame = frame_from_baseline(
        transformed[0],
        transformed[1],
        points_per_m=points_per_m,
    )
    transformed_u0, transformed_u1 = project_span_m(
        transformed_frame,
        transformed[2],
        transformed[3],
    )
    transformed_rect = WallLocalRectFixture(
        u0=transformed_u0,
        u1=transformed_u1,
        z0=0.9,
        z1=3.0,
    )

    assert canonical_rect_signature(rect, wall_length_m=frame.wall_length_m) == canonical_rect_signature(
        transformed_rect,
        wall_length_m=transformed_frame.wall_length_m,
    )


def test_arbitrary_split_piece_frame_cannot_define_complete_opening_span() -> None:
    """A split wall candidate must not silently become the whole host coordinate frame."""
    points_per_m = 100.0
    jamb_left = (200.0, 0.0)
    jamb_right = (290.0, 0.0)

    whole = frame_from_baseline((0.0, 0.0), (500.0, 0.0), points_per_m=points_per_m)
    left_piece = frame_from_baseline((0.0, 0.0), (200.0, 0.0), points_per_m=points_per_m)
    right_piece = frame_from_baseline((290.0, 0.0), (500.0, 0.0), points_per_m=points_per_m)

    whole_span = project_span_m(whole, jamb_left, jamb_right)
    left_piece_span = project_span_m(left_piece, jamb_left, jamb_right)
    right_piece_span = project_span_m(right_piece, jamb_left, jamb_right)

    assert span_is_inside_frame(whole, whole_span)
    assert not span_is_inside_frame(left_piece, left_piece_span)
    assert not span_is_inside_frame(right_piece, right_piece_span)


def test_duplicate_observation_geometry_does_not_create_a_second_void_shape() -> None:
    """Repeated observation of one physical opening has one reference geometry signature."""
    first = WallLocalRectFixture(u0=1.2, u1=2.1, z0=0.9, z1=3.0)
    duplicate = WallLocalRectFixture(u0=1.2, u1=2.1, z0=0.9, z1=3.0)

    assert canonical_rect_signature(first, wall_length_m=5.0) == canonical_rect_signature(
        duplicate,
        wall_length_m=5.0,
    )
