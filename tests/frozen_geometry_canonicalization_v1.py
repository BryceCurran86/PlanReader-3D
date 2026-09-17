"""Deterministic polygon serialization for frozen geometry replay only.

This module is intentionally test/replay-only.  It does not alter production
geometry, establish authority, or change PlanReader measurement tolerances.

The live Boolean geometry path remains full precision.  At the frozen snapshot
boundary we snap metre coordinates to a 0.1 mm grid, convert them to integer
0.1 mm ticks, canonicalize winding/start position/component order, and hash an
integer-only geometry representation.  Collapsed, invalid, empty, or
non-polygonal results fail closed instead of being silently deleted.
"""
from __future__ import annotations

from hashlib import sha256
import json
import math
from typing import Iterable

import shapely
from shapely.errors import GEOSException
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry


GRID_SIZE_M = 1e-4
GRID_SIZE_MICROMETRES = 100
TICKS_PER_METRE = 10_000
SNAPSHOT_SCHEMA = "planreader_frozen_polygon_v1"

PointI = tuple[int, int]
RingI = tuple[PointI, ...]
PolygonI = tuple[RingI, tuple[RingI, ...]]


class FrozenGeometryError(ValueError):
    """Frozen replay geometry could not be represented without ambiguity."""


def _to_tick(value: float) -> int:
    """Convert an already-snapped metre coordinate to an integer grid tick."""
    number = float(value)
    if not math.isfinite(number):
        raise FrozenGeometryError("non_finite_coordinate")

    ticks = number * TICKS_PER_METRE
    nearest = int(round(ticks))
    tolerance = max(1e-7, math.ulp(max(abs(ticks), 1.0)) * 8.0)
    if not math.isclose(ticks, nearest, rel_tol=0.0, abs_tol=tolerance):
        raise FrozenGeometryError("coordinate_not_on_frozen_grid")
    return nearest


def _signed_area2(ring: RingI) -> int:
    """Return twice the signed area using integer-only arithmetic."""
    return sum(
        x1 * y2 - x2 * y1
        for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1])
    )


def _rotate_lexicographically(ring: RingI) -> RingI:
    """Choose a deterministic cyclic start, including repeated-minimum cases."""
    if not ring:
        raise FrozenGeometryError("empty_ring")
    return min(ring[index:] + ring[:index] for index in range(len(ring)))


def _canonical_ring(
    coords: Iterable[tuple[float, ...]],
    *,
    counter_clockwise: bool,
) -> RingI:
    points = [(_to_tick(coord[0]), _to_tick(coord[1])) for coord in coords]

    # Shapely closes linear rings by repeating the first coordinate.
    if len(points) >= 2 and points[0] == points[-1]:
        points.pop()

    # Quantization may create consecutive duplicates. They carry no topology.
    cleaned: list[PointI] = []
    for point in points:
        if not cleaned or point != cleaned[-1]:
            cleaned.append(point)

    ring: RingI = tuple(cleaned)
    if len(ring) < 3 or len(set(ring)) < 3:
        raise FrozenGeometryError("collapsed_ring")

    area2 = _signed_area2(ring)
    if area2 == 0:
        raise FrozenGeometryError("zero_area_ring")

    if (area2 > 0) != counter_clockwise:
        ring = tuple(reversed(ring))

    return _rotate_lexicographically(ring)


def _canonical_polygon(polygon: Polygon) -> PolygonI:
    if polygon.is_empty:
        raise FrozenGeometryError("empty_polygon")
    if not polygon.is_valid:
        raise FrozenGeometryError("invalid_polygon")
    if not math.isfinite(float(polygon.area)) or polygon.area <= 0.0:
        raise FrozenGeometryError("zero_area_polygon")

    exterior = _canonical_ring(polygon.exterior.coords, counter_clockwise=True)
    holes = tuple(
        sorted(
            _canonical_ring(interior.coords, counter_clockwise=False)
            for interior in polygon.interiors
        )
    )
    return exterior, holes


def canonical_polygon_signature(geometry: BaseGeometry) -> tuple[object, ...]:
    """Return a deterministic integer signature for Polygon/MultiPolygon geometry.

    ``geometry`` must be expressed in metres. Precision reduction is applied only
    here at the frozen replay boundary; callers must never feed this signature back
    into live extraction or use it to establish geometric/evidentiary authority.

    The returned/hashable payload contains no floating-point values: the grid is
    identified as 100 micrometres and every coordinate is an integer 0.1 mm tick.
    """
    if not isinstance(geometry, BaseGeometry):
        raise FrozenGeometryError("geometry_type_invalid")

    try:
        snapped = shapely.set_precision(
            geometry,
            grid_size=GRID_SIZE_M,
            mode="valid_output",
        )
    except GEOSException as exc:
        raise FrozenGeometryError("precision_reduction_failed") from exc

    if snapped is None or snapped.is_empty:
        raise FrozenGeometryError("geometry_collapsed_during_quantization")
    if not snapped.is_valid:
        raise FrozenGeometryError("geometry_invalid_after_quantization")

    if isinstance(snapped, Polygon):
        polygons = (_canonical_polygon(snapped),)
    elif isinstance(snapped, MultiPolygon):
        if not snapped.geoms:
            raise FrozenGeometryError("empty_multipolygon")
        polygons = tuple(sorted(_canonical_polygon(poly) for poly in snapped.geoms))
    else:
        # GeometryCollections/lines/points are rejected rather than partially
        # filtering them and accidentally changing the proposition being replayed.
        raise FrozenGeometryError(f"non_polygonal_geometry:{snapped.geom_type}")

    return (
        SNAPSHOT_SCHEMA,
        "metre",
        GRID_SIZE_MICROMETRES,
        TICKS_PER_METRE,
        polygons,
    )


def frozen_geometry_hash(geometry: BaseGeometry) -> str:
    """SHA-256 of the canonical integer snapshot, independent of ring ordering."""
    encoded = json.dumps(
        canonical_polygon_signature(geometry),
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return sha256(encoded).hexdigest()


def frozen_geometry_snapshot(geometry: BaseGeometry) -> dict[str, object]:
    """Return snapshot payload plus runtime metadata for replay diagnostics."""
    signature = canonical_polygon_signature(geometry)
    encoded = json.dumps(signature, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return {
        "schema": SNAPSHOT_SCHEMA,
        "coordinate_unit": "metre",
        "grid_size_m": GRID_SIZE_M,
        "grid_size_micrometres": GRID_SIZE_MICROMETRES,
        "ticks_per_metre": TICKS_PER_METRE,
        "signature": signature,
        "sha256": sha256(encoded).hexdigest(),
        # Runtime versions are diagnostic metadata, not part of the geometry hash.
        "shapely_version": shapely.__version__,
        "geos_version": shapely.geos_version_string,
    }


__all__ = [
    "GRID_SIZE_M",
    "GRID_SIZE_MICROMETRES",
    "TICKS_PER_METRE",
    "SNAPSHOT_SCHEMA",
    "FrozenGeometryError",
    "canonical_polygon_signature",
    "frozen_geometry_hash",
    "frozen_geometry_snapshot",
]
