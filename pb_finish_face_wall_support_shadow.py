"""Report only (#4764 7225222738, C06/C08): is every edge of a finish-bearing room face on wall evidence?

See docs/engineering/claude_finish_face_wall_support_note_20261128.md. Wall evidence along an edge stretch is either a
second line of the SAME ink running 1.2 to 8 pt behind the line on that edge, with exactly one such position (three lines
are hatch, not a wall), or one of the layered builder's filled wall bars behind the edge. Ink that is paper white or the
owner's excluded green never counts; no other colour is excluded. A doorway closure given by the caller also covers its
stretch. Thicknesses, minimum length and tolerances are the layered builder's own. Nothing is promoted, closed, removed or
published, and no live path imports this.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from typing import Any

from shapely.geometry import Point, Polygon

from pb_layered_wall_doorway_room_ring_shadow import (
    NOISE_PT, _STROKE_PAIR_CLUSTER_PT, _STROKE_PAIR_THICK_MAX, _STROKE_PAIR_THICK_MIN, _axis_strokes,
    _collect_dark_painted_source_wall_strips, _opaque, _owner_excluded_green_ink, _visible_source_stroke_paint,
)
from pb_migration_contracts import EvidenceResolutionStatus

PAIRED, FILLED, CLOSURE = "paired", "filled", "closure"
_AROUND_PT = 2.0 * _STROKE_PAIR_THICK_MAX  # how far around the face paired strokes and bars are searched
_BLACK = (0.0, 0.0, 0.0)


def _paper_white(color: Any) -> bool:
    return isinstance(color, (tuple, list)) and len(color) == 3 and all(
        type(v) in (int, float) and v >= 0.995 for v in color)


def _near(row: Mapping[str, Any], region: tuple[float, float, float, float]) -> bool:
    rect = row.get("rect")
    if rect is None:
        return True
    x0, y0, x1, y1 = (float(v) for v in tuple(rect))  # a flat line has an empty rect: compare the numbers
    return not (x1 < region[0] or x0 > region[2] or y1 < region[1] or y0 > region[3])


def _ink_near(drawings: Sequence[Any], region: tuple[float, float, float, float]):
    """Visible wall-eligible paint near the face: stroke runs per ink colour, and the fills for the builder's bars.

    Lines are merged by the builder's own collinear rule (runs shorter than its 8 pt minimum are dropped). Rows are
    recoloured black only so the builder's collectors accept them; positions in the list are kept."""
    inks: dict[tuple[float, ...], list[dict | None]] = {}
    fills: list[dict | None] = [None] * len(drawings)
    for index, row in enumerate(drawings):
        if not (isinstance(row, Mapping) and row.get("items") and _near(row, region)):
            continue
        stroke, fill = row.get("color"), row.get("fill")
        if fill is not None and not _paper_white(fill):
            if not _owner_excluded_green_ink(fill) and _opaque(row):
                fills[index] = {**row, "color": None, "fill": _BLACK, "layer": ""}
        elif (stroke is not None and not _paper_white(stroke) and not _owner_excluded_green_ink(stroke)
              and _visible_source_stroke_paint(row)):
            ink = tuple(round(float(v), 3) for v in stroke)
            inks.setdefault(ink, [None] * len(drawings))[index] = {**row, "color": _BLACK, "fill": None, "layer": ""}
    return {ink: _axis_strokes(rows) for ink, rows in sorted(inks.items())}, fills


def _paired_stretches(runs, horizontal: bool, line: float, outward: float, start: float, end: float):
    """Stretches of an edge with a line of one ink on it and exactly one same-ink partner position behind it."""
    along = [(perp, lo, hi) for _index, is_horizontal, perp, lo, hi in runs if is_horizontal == horizontal
             and min(hi, end) > max(lo, start)]
    near = [(perp, lo, hi) for perp, lo, hi in along
            if -NOISE_PT * 2 <= (perp - line) * outward <= _STROKE_PAIR_CLUSTER_PT]
    if not near:
        return []
    face = max((perp - line) * outward for perp, _lo, _hi in near)
    behind = [(perp, lo, hi) for perp, lo, hi in along
              if _STROKE_PAIR_THICK_MIN <= (perp - line) * outward - face <= _STROKE_PAIR_THICK_MAX]
    cuts = sorted({start, end, *(v for _p, lo, hi in near + behind for v in (lo, hi) if start < v < end)})
    found = []
    for lo, hi in zip(cuts, cuts[1:]):
        middle = (lo + hi) / 2.0
        if not any(a <= middle <= b for _p, a, b in near):
            continue
        positions = sorted((perp - line) * outward for perp, a, b in behind if a <= middle <= b)
        if positions and positions[-1] - positions[0] <= _STROKE_PAIR_CLUSTER_PT:
            found.append((lo - start, hi - start))
    return found


def _union_length(spans: list[tuple[float, float]], length: float) -> tuple[float, float]:
    """(covered length, longest uncovered stretch) of spans already clipped to [0, length]."""
    covered, longest_gap, reach = 0.0, 0.0, 0.0
    for lo, hi in sorted(spans):
        if lo > reach:
            longest_gap = max(longest_gap, lo - reach)
        covered += max(0.0, hi - max(lo, reach))
        reach = max(reach, hi)
    return covered, max(longest_gap, length - reach)


def face_wall_support(polygon: Sequence[tuple[float, float]], drawings: Sequence[Any], closures: Sequence[Any] = ()) -> dict:
    """Per edge of ``polygon``: the stretch on paired or filled wall evidence, on a given doorway closure, or neither."""
    points = [(float(x), float(y)) for x, y in polygon]
    if len(points) > 1 and points[0] == points[-1]:
        points = points[:-1]
    room = Polygon(points)
    if len(points) < 3 or not room.is_valid or room.area <= 0.0:
        return {"status": EvidenceResolutionStatus.ABSTAINED, "reason": "face_polygon_invalid", "edges": []}
    x0, y0, x1, y1 = room.bounds
    inks, fills = _ink_near(drawings, (x0 - _AROUND_PT, y0 - _AROUND_PT, x1 + _AROUND_PT, y1 + _AROUND_PT))
    bars = _collect_dark_painted_source_wall_strips(fills)
    edges = []
    for a, b in zip(points, points[1:] + points[:1]):
        length = math.dist(a, b)
        horizontal = abs(a[1] - b[1]) <= NOISE_PT * 2 < abs(a[0] - b[0])
        vertical = abs(a[0] - b[0]) <= NOISE_PT * 2 < abs(a[1] - b[1])
        stretches: dict[str, list[tuple[float, float]]] = {PAIRED: [], FILLED: [], CLOSURE: []}
        if horizontal or vertical:
            along, across = (0, 1) if horizontal else (1, 0)
            line = (a[across] + b[across]) / 2.0
            start, end = sorted((a[along], b[along]))
            probe = [0.0, 0.0]
            probe[along], probe[across] = (start + end) / 2.0, line + NOISE_PT
            room_above = room.covers(Point(*probe))  # the room lies towards larger ``across``

            def clip(lo: float, hi: float) -> tuple[float, float] | None:
                lo, hi = max(lo, start) - start, min(hi, end) - start
                return (lo, hi) if hi > lo else None

            outward = -1.0 if room_above else 1.0
            for runs in inks.values():
                stretches[PAIRED] += _paired_stretches(runs, horizontal, line, outward, start, end)
            for strip in bars:
                if not (strip.horizontal if horizontal else strip.vertical):
                    continue
                low, high = strip.band()
                near_face = high if room_above else low  # the bar must lie on the other side of the line
                if abs(near_face - line) <= _STROKE_PAIR_CLUSTER_PT and (span := clip(*strip.span())) is not None:
                    stretches[FILLED].append(span)
            for closure in closures:
                if closure.horizontal == horizontal and (closure.band[0] - _STROKE_PAIR_CLUSTER_PT <= line
                                                         <= closure.band[1] + _STROKE_PAIR_CLUSTER_PT):
                    if (span := clip(*closure.gap_interval)) is not None:
                        stretches[CLOSURE].append(span)
        every = [span for spans in stretches.values() for span in spans]
        covered, longest_gap = _union_length(every, length)
        edges.append({
            "length": length,
            **{kind: _union_length(spans, length)[0] for kind, spans in stretches.items()},
            "unsupported": max(0.0, length - covered),
            "longest_gap": longest_gap,
        })
    total = sum(edge["length"] for edge in edges)
    supported = all(edge["longest_gap"] <= _STROKE_PAIR_CLUSTER_PT for edge in edges)
    return {
        "status": EvidenceResolutionStatus.CANDIDATE if supported else EvidenceResolutionStatus.ABSTAINED,
        "reason": "every_edge_on_wall_evidence" if supported else "face_edge_without_wall_evidence",
        "edges": edges,
        "unsupported_share": sum(edge["unsupported"] for edge in edges) / total if total else 1.0,
    }
