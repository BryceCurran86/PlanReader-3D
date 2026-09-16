"""Metamorphic geometry invariants for future Physical Opening Void V2.

These tests validate the test-only reference math used by the red-team lane. They do
not substitute for production authority tests and do not manufacture missing
height/host/scale/vertical-placement evidence.
"""
from __future__ import annotations

import math

import pytest

from tests.physical_opening_void_geometry_support_v2 import (
    frame_from_baseline,
    project_span_m,
    reverse_frame,
    rigid_transform_point,
)


def test_translation_and_rotation_preserve_wall_local_opening_span() -> None:
    points_per_m = 100.0
    start = (10.0, 20.0)
    end = (510.0, 20.0)
    jamb_left = (210.0, 20.0)
    jamb_right = (300.0, 20.0)

    frame = frame_from_baseline(start, end, points_per_m=points_per_m)
    original = project_span_m(frame, jamb_left, jamb_right)
    assert original == pytest.approx((2.0, 2.9))

    angle = math.radians(37.0)
    transformed_start = rigid_transform_point(start, angle_rad=angle, tx=83.0, ty=-41.0)
    transformed_end = rigid_transform_point(end, angle_rad=angle, tx=83.0, ty=-41.0)
    transformed_left = rigid_transform_point(jamb_left, angle_rad=angle, tx=83.0, ty=-41.0)
    transformed_right = rigid_transform_point(jamb_right, angle_rad=angle, tx=83.0, ty=-41.0)

    transformed_frame = frame_from_baseline(
        transformed_start,
        transformed_end,
        points_per_m=points_per_m,
    )
    transformed = project_span_m(transformed_frame, transformed_left, transformed_right)
    assert transformed == pytest.approx(original)


def test_reversed_baseline_preserves_physical_span_and_maps_coordinates_deterministically() -> None:
    frame = frame_from_baseline((0.0, 0.0), (500.0, 0.0), points_per_m=100.0)
    forward = project_span_m(frame, (120.0, 0.0), (210.0, 0.0))
    reversed_frame = reverse_frame(frame)
    reversed_span = project_span_m(reversed_frame, (120.0, 0.0), (210.0, 0.0))

    assert forward == pytest.approx((1.2, 2.1))
    assert reversed_span == pytest.approx(
        (frame.wall_length_m - forward[1], frame.wall_length_m - forward[0])
    )
    assert reversed_span[1] - reversed_span[0] == pytest.approx(forward[1] - forward[0])


def test_authenticated_width_must_match_physical_jamb_span_before_positive_void() -> None:
    frame = frame_from_baseline((0.0, 0.0), (500.0, 0.0), points_per_m=100.0)
    span = project_span_m(frame, (120.0, 0.0), (210.0, 0.0))
    source_span_mm = (span[1] - span[0]) * 1000.0

    assert source_span_mm == pytest.approx(900.0)
    authenticated_width_mm = 900.0
    assert source_span_mm == pytest.approx(authenticated_width_mm)

    contradictory_width_mm = 1000.0
    assert source_span_mm != pytest.approx(contradictory_width_mm)


def test_height_must_match_authenticated_vertical_placement_span() -> None:
    z0_m = 0.9
    z1_m = 3.0
    authenticated_height_mm = 2100.0
    assert (z1_m - z0_m) * 1000.0 == pytest.approx(authenticated_height_mm)

    contradictory_height_mm = 2040.0
    assert (z1_m - z0_m) * 1000.0 != pytest.approx(contradictory_height_mm)


@pytest.mark.parametrize("bad_scale", [0.0, -1.0, float("inf"), float("nan")])
def test_wall_local_frame_rejects_missing_or_invalid_unit_mapping(bad_scale: float) -> None:
    with pytest.raises(ValueError):
        frame_from_baseline((0.0, 0.0), (100.0, 0.0), points_per_m=bad_scale)
