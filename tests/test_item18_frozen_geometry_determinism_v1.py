"""Supplemental Item 18 attacks for deterministic frozen Boolean replay.

TEST/REPLAY ONLY.  These tests do not change live geometry precision or mint
measurement authority.
"""
from __future__ import annotations

import pytest
from shapely.geometry import LineString, MultiPolygon, Polygon

from pb_net_wall_boolean_union_authority import union_wall_local_void_polygons
from tests.frozen_geometry_canonicalization_v1 import (
    GRID_SIZE_M,
    FrozenGeometryError,
    canonical_polygon_signature,
    frozen_geometry_hash,
    frozen_geometry_snapshot,
)


def _rectangle(x0: float, y0: float, x1: float, y1: float) -> Polygon:
    return Polygon(((x0, y0), (x1, y0), (x1, y1), (x0, y1)))


def test_same_polygon_hashes_identically_across_start_vertex_and_winding() -> None:
    canonical = Polygon(((0.0, 0.0), (2.0, 0.0), (2.0, 1.0), (0.0, 1.0)))
    shifted_reversed = Polygon(((2.0, 1.0), (2.0, 0.0), (0.0, 0.0), (0.0, 1.0)))

    assert frozen_geometry_hash(canonical) == frozen_geometry_hash(shifted_reversed)
    assert canonical_polygon_signature(canonical) == canonical_polygon_signature(shifted_reversed)


def test_sub_grid_micro_float_jitter_is_removed_only_at_snapshot_boundary() -> None:
    exact = _rectangle(0.0, 0.0, 2.0, 1.0)
    jittered = Polygon(
        (
            (0.00003, -0.00003),
            (2.00003, 0.00002),
            (1.99998, 1.00003),
            (-0.00002, 0.99998),
        )
    )

    # Live geometries remain different; only frozen serialization coalesces them.
    assert not exact.equals_exact(jittered, tolerance=0.0)
    assert frozen_geometry_hash(exact) == frozen_geometry_hash(jittered)


def test_negative_coordinates_round_to_nearest_tick_not_toward_zero() -> None:
    jittered = _rectangle(-2.00003, -1.00003, -0.99997, -0.49997)
    snapped = _rectangle(-2.0, -1.0, -1.0, -0.5)

    assert frozen_geometry_hash(jittered) == frozen_geometry_hash(snapped)

    signature = canonical_polygon_signature(jittered)
    exterior = signature[4][0][0]
    assert (-20_000, -10_000) in exterior
    assert (-10_000, -5_000) in exterior


def test_hole_winding_and_start_position_do_not_change_signature() -> None:
    shell_a = ((0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0))
    hole_a = ((1.0, 1.0), (1.0, 3.0), (3.0, 3.0), (3.0, 1.0))
    first = Polygon(shell_a, (hole_a,))

    shell_b = ((4.0, 4.0), (4.0, 0.0), (0.0, 0.0), (0.0, 4.0))
    hole_b = ((3.0, 3.0), (1.0, 3.0), (1.0, 1.0), (3.0, 1.0))
    second = Polygon(shell_b, (hole_b,))

    assert frozen_geometry_hash(first) == frozen_geometry_hash(second)


def test_multipart_component_order_is_canonical() -> None:
    left = _rectangle(0.0, 0.0, 1.0, 1.0)
    right = _rectangle(3.0, 0.0, 4.0, 1.0)

    first = MultiPolygon((left, right))
    second = MultiPolygon((right, left))

    assert frozen_geometry_hash(first) == frozen_geometry_hash(second)
    assert canonical_polygon_signature(first) == canonical_polygon_signature(second)


def test_boolean_union_hash_is_independent_of_input_order() -> None:
    a = _rectangle(0.0, 0.0, 1.5, 2.0)
    b = _rectangle(1.0, 0.0, 2.0, 2.0)
    c = _rectangle(3.0, 0.0, 4.0, 2.0)

    forward = union_wall_local_void_polygons((a, b, c))
    reverse = union_wall_local_void_polygons((c, b, a))

    assert forward.equals(reverse)
    assert frozen_geometry_hash(forward) == frozen_geometry_hash(reverse)


def test_snapshot_hash_contains_runtime_metadata_but_hash_does_not_depend_on_it() -> None:
    geometry = _rectangle(0.0, 0.0, 1.0, 1.0)
    snapshot = frozen_geometry_snapshot(geometry)

    assert snapshot["grid_size_m"] == GRID_SIZE_M
    assert snapshot["shapely_version"]
    assert snapshot["geos_version"]
    assert snapshot["sha256"] == frozen_geometry_hash(geometry)
    assert len(str(snapshot["sha256"])) == 64


def test_polygon_narrower_than_grid_fails_closed_after_precision_reduction() -> None:
    # 0.04 mm is narrower than the 0.1 mm replay grid and must not silently
    # disappear from a frozen snapshot.
    sliver = _rectangle(0.0, 0.0, 0.00004, 1.0)

    with pytest.raises(FrozenGeometryError, match="collapsed"):
        canonical_polygon_signature(sliver)


def test_non_polygonal_geometry_is_rejected_not_partially_serialized() -> None:
    line = LineString(((0.0, 0.0), (1.0, 1.0)))

    with pytest.raises(FrozenGeometryError, match="non_polygonal_geometry"):
        canonical_polygon_signature(line)


def test_quantization_never_changes_live_boolean_inputs() -> None:
    first = _rectangle(0.00003, 0.0, 1.00003, 1.0)
    second = _rectangle(0.50002, 0.0, 1.50002, 1.0)

    live_union = union_wall_local_void_polygons((first, second))
    bounds_before = tuple(live_union.bounds)
    _ = frozen_geometry_hash(live_union)

    # set_precision returns a new geometry; it must not mutate the live object.
    assert tuple(live_union.bounds) == bounds_before
    assert bounds_before[0] == pytest.approx(0.00003)
