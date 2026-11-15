"""Source-native OUTER painted wall preflight; no image hull or site rectangle.

This stage runs before doorway / internal-wall tracing. A source-painted
closed perimeter can be a *candidate*, not a physical building wall until
source role and opening ownership are independently verified. Nothing issues
quantities and no guessed envelope filters inner walls.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Mapping, Sequence

from shapely.geometry import Polygon
from shapely.ops import unary_union

from pb_layered_wall_doorway_room_ring_shadow import (
    _collect_dark_painted_source_wall_strips,
    _collect_strips,
    _source_wall_ink_candidate_drawings,
)
from pb_next_wall_ring_preview import (
    _collect_stroke_pair_strips,
    _collect_source_heavy_stroke_strips,
    _collect_cavity_multi_face_strips,
    _collect_source_wide_face_pairs,
)
from pb_new_wall_graph_diagnostic import NativeWallGraphDiagnostic, inspect_native_wall_graph


@dataclass(frozen=True)
class SourceNativeOuterWallAttempt:
    status: str
    reason: str
    polygon_pdf_pts: tuple[tuple[float, float], ...] = ()
    source_wall_path_ids: tuple[int, ...] = ()
    physical_wall_authenticated: bool = False
    internal_wall_filter_authorized: bool = False
    measurement_authorized: bool = False
    source_wall_band_count: int = 0
    source_stroke_pair_band_count: int = 0
    source_heavy_stroke_band_count: int = 0
    source_cavity_multi_face_band_count: int = 0
    source_wide_face_pair_band_count: int = 0
    source_wall_path_count: int = 0
    graph: NativeWallGraphDiagnostic = field(default_factory=NativeWallGraphDiagnostic)


def attempt_source_native_outer_wall_first(
    drawings: Sequence[Mapping[str, Any]],
) -> SourceNativeOuterWallAttempt:
    """Find one joined perimeter in *source wall fills*, NOT the sheet bbox.

    Only accepts a continuous source-painted wall band with an interior hole.
    Requires all other painted structural wall bands be contained inside the
    candidate. Ambiguous outer candidates and separate wings fail closed.
    This is deliberately stricter than a raster contour or concave hull.
    """
    wall_ink, _n, _green = _source_wall_ink_candidate_drawings(drawings)
    named, _other = _collect_strips(wall_ink)
    dark = _collect_dark_painted_source_wall_strips(wall_ink)
    # Architectural walls can be two separate native ink strokes, not opaque
    # filled rectangles. The original preflight omitted them entirely.
    # Source paired faces are candidates, NEVER automatically physical walls.
    paired = _collect_stroke_pair_strips(wall_ink)
    # Preserve native thick-line paint. Those source strokes are physical
    # wall candidates, not inferred or double-line approximations.
    thick = _collect_source_heavy_stroke_strips(wall_ink)
    cavity = _collect_cavity_multi_face_strips(wall_ink)
    wide_pairs = _collect_source_wide_face_pairs(wall_ink)
    bars = named + dark + paired + thick + cavity + wide_pairs
    unique_bars = {}
    for bar in bars:
        if bar.polygon is None or bar.polygon.is_empty or not bar.polygon.is_valid:
            continue
        key = (
            int(bar.path_index),
            *(round(float(v), 4) for v in bar.polygon.bounds),
        )
        unique_bars[key] = bar
    bars = list(unique_bars.values())
    graph = inspect_native_wall_graph(bars)
    counts = dict(
        graph=graph,
        source_wall_band_count=len(bars),
        source_stroke_pair_band_count=len(paired),
        source_heavy_stroke_band_count=len(thick),
        source_cavity_multi_face_band_count=len(cavity),
        source_wide_face_pair_band_count=len(wide_pairs),
        source_wall_path_count=len({
            path for bar in bars for path in bar.native_path_indices()
        }),
    )
    if len(bars) < 4:
        return SourceNativeOuterWallAttempt(
            "ABSTAINED", "source_exterior_continuous_wall_band_not_found",
            **counts,
        )
    union = unary_union([bar.polygon for bar in bars])
    polygons = list(union.geoms) if hasattr(union, "geoms") else [union]
    # A true wall-band perimeter has an interior void. Open-ended lines,
    # dimension ticks and boxed landscape art cannot be promoted by hull.
    closed = [
        part for part in polygons
        if isinstance(part, Polygon)
        and part.is_valid
        and len(part.interiors) >= 1
        and len(part.exterior.coords) >= 5
    ]
    if len(closed) != 1:
        return SourceNativeOuterWallAttempt(
            "ABSTAINED", "source_exterior_perimeter_not_unique_and_closed",
            **counts,
        )
    outer = closed[0]
    if outer.area <= 0 or not math.isfinite(outer.area):
        return SourceNativeOuterWallAttempt(
            "ABSTAINED", "source_exterior_perimeter_not_finite",
            **counts,
        )
    # A single ROOM perimeter with other walls beyond it is not the outer
    # building boundary. Count every independent source-painted wall bar.
    if any(not outer.buffer(.05).covers(bar.polygon) for bar in bars):
        return SourceNativeOuterWallAttempt(
            "ABSTAINED", "source_exterior_other_wall_ink_outside_candidate",
            **counts,
        )
    points = tuple(
        (round(float(x), 3), round(float(y), 3))
        for x, y in list(outer.exterior.coords)[:-1]
    )
    sources = tuple(sorted({
        int(bar.path_index) for bar in bars
        if outer.boundary.distance(bar.polygon) <= 0.05
    }))
    if len(points) < 4 or len(sources) < 4:
        return SourceNativeOuterWallAttempt(
            "ABSTAINED", "source_exterior_wall_path_owners_incomplete",
            **counts,
        )
    return SourceNativeOuterWallAttempt(
        "CANDIDATE", "source_closed_painted_wall_ring_needs_exterior_role_authentication",
        points, sources,
        source_wall_band_count=counts["source_wall_band_count"],
        source_stroke_pair_band_count=counts["source_stroke_pair_band_count"],
        source_heavy_stroke_band_count=counts["source_heavy_stroke_band_count"],
        source_cavity_multi_face_band_count=counts["source_cavity_multi_face_band_count"],
        source_wide_face_pair_band_count=counts["source_wide_face_pair_band_count"],
        source_wall_path_count=counts["source_wall_path_count"],
        graph=graph,
    )
