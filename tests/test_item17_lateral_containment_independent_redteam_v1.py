"""Independent test-only validator for Item 17 lateral containment semantics.

TEST ONLY / DO NOT MERGE.

Exact production parent under review:
a027a493baca9bc87bfbdb6efff09c1aea43b8b1

Post-merge main containing that production parent:
8d8ff44ad095114a9f0f3b1d37de402ebb477225

This validator exists because frozen PR #469 contains one internally contradictory
geometry case: test_A_equal_scalar_area_non_equivalent_shapes_are_not_interchangeable
passes a void that protrudes beyond wall_5x6, while Section L of the same frozen file
requires partially outside/clipped openings to fail closed.

This suite does not modify #469. It independently validates the stated Item 17
production invariant: every authoritative opening void must be fully covered by the
authenticated gross-wall polygon; unsupported clipping is forbidden.
"""
from __future__ import annotations

import pytest
from shapely.geometry import box

from pb_net_wall_boolean_union_authority import subtract_void_union_from_wall_polygon


PRODUCTION_PARENT = "a027a493baca9bc87bfbdb6efff09c1aea43b8b1"
MERGED_MAIN_PARENT = "8d8ff44ad095114a9f0f3b1d37de402ebb477225"


def test_right_lateral_overrun_fails_closed_when_vertically_inset() -> None:
    gross = box(0.0, 0.0, 10.0, 3.0)
    opening = box(9.5, 1.0, 10.5, 2.0)
    assert not gross.covers(opening)
    with pytest.raises(ValueError, match="partially or completely outside gross wall"):
        subtract_void_union_from_wall_polygon(gross, (opening,))


def test_left_lateral_overrun_fails_closed_when_vertically_inset() -> None:
    gross = box(0.0, 0.0, 10.0, 3.0)
    opening = box(-0.5, 1.0, 0.5, 2.0)
    assert not gross.covers(opening)
    with pytest.raises(ValueError, match="partially or completely outside gross wall"):
        subtract_void_union_from_wall_polygon(gross, (opening,))


def test_tiny_lateral_overshoot_fails_closed_when_vertically_inset() -> None:
    gross = box(0.0, 0.0, 10.0, 3.0)
    opening = box(9.0, 1.0, 10.0 + 1e-12, 2.0)
    assert not gross.covers(opening)
    with pytest.raises(ValueError, match="partially or completely outside gross wall"):
        subtract_void_union_from_wall_polygon(gross, (opening,))


def test_frozen_469_scalar_shape_case_is_geometrically_outside_second_wall() -> None:
    """Document the exact contradictory frozen #469 geometry without editing it."""
    wall_10x3 = box(0.0, 0.0, 10.0, 3.0)
    wall_5x6 = box(0.0, 0.0, 5.0, 6.0)
    opening = box(4.5, 1.0, 5.5, 2.0)

    assert wall_10x3.covers(opening)
    assert not wall_5x6.covers(opening)

    # Valid on the first wall.
    result = subtract_void_union_from_wall_polygon(wall_10x3, (opening,))
    assert result.area == pytest.approx(wall_10x3.area - opening.area)

    # The same geometry is a lateral overrun on the second wall and must fail closed.
    with pytest.raises(ValueError, match="partially or completely outside gross wall"):
        subtract_void_union_from_wall_polygon(wall_5x6, (opening,))


def test_fully_contained_vertically_inset_opening_remains_valid() -> None:
    gross = box(0.0, 0.0, 10.0, 3.0)
    opening = box(1.0, 1.0, 3.0, 2.0)
    assert gross.covers(opening)
    result = subtract_void_union_from_wall_polygon(gross, (opening,))
    assert result.is_valid
    assert result.area == pytest.approx(28.0)


def test_boundary_touching_contained_door_remains_valid() -> None:
    gross = box(0.0, 0.0, 10.0, 3.0)
    opening = box(1.0, 0.0, 2.0, 2.0)
    assert gross.covers(opening)
    result = subtract_void_union_from_wall_polygon(gross, (opening,))
    assert result.is_valid
    assert result.area == pytest.approx(28.0)
