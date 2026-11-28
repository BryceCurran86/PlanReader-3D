"""Curved wall candidates from paired concentric arcs (report only, default unwired; CL-R26).

Wall candidates are built from straight pieces only, so a curved wall is never
one. A curved wall drawn as two faces shows as two concentric arcs of one ink,
a wall's thickness apart, running over the same angles. This reads them from the
native Bezier curves and reports them; it creates no wall, id, room, host,
measurement or quantity and nothing imports it.

Abstains rather than choosing: a third concentric arc nearby (steps, hatch,
rings), and arcs that are a door swing (a straight leaf from the centre to an
arc end). Full circles (columns, tables) are never walls. Thickness limits are
the ring builder's.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from pb_layered_wall_doorway_room_ring_shadow import (
    _DARK_FILL_THICK_MAX,
    _STROKE_PAIR_THICK_MIN,
)
from pb_migration_contracts import EvidenceResolutionStatus

CURVED_WALL_PAIR_SHADOW_VERSION = "curved-wall-pair-1.0.0"
REASON_PAIR = "paired_concentric_arcs"
REASON_RINGS = "third_concentric_arc_nearby"
REASON_DOOR = "arc_is_a_door_swing"
# Geometry tolerances in points: fit error and "same centre" (the ring builder's pair cluster).
_FIT_PT = 0.8
_MIN_RADIUS_PT = 20.0
_MIN_OVERLAP_DEG = 30.0
_FULL_DEG = 330.0

Point = tuple[float, float]


def _xy(value: Any) -> Point:
    x, y = tuple(value)[:2]
    return float(x), float(y)


def _circle(a: Point, b: Point, c: Point) -> tuple[Point, float] | None:
    d = 2.0 * (a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1]))
    if abs(d) < 1e-9:
        return None
    sq = [p[0] * p[0] + p[1] * p[1] for p in (a, b, c)]
    x = (sq[0] * (b[1] - c[1]) + sq[1] * (c[1] - a[1]) + sq[2] * (a[1] - b[1])) / d
    y = (sq[0] * (c[0] - b[0]) + sq[1] * (a[0] - c[0]) + sq[2] * (b[0] - a[0])) / d
    return (x, y), math.hypot(a[0] - x, a[1] - y)


def _bezier(p: Sequence[Point], t: float) -> Point:
    u = 1.0 - t
    return tuple(u ** 3 * p[0][k] + 3 * u * u * t * p[1][k] + 3 * u * t * t * p[2][k] + t ** 3 * p[3][k]
                 for k in (0, 1))


def _sweep(centre: Point, start: Point, middle: Point, end: Point) -> tuple[float, float]:
    """(from, length) in degrees, counter-clockwise, of the arc start -> middle -> end."""
    angle = lambda p: math.degrees(math.atan2(p[1] - centre[1], p[0] - centre[0])) % 360.0
    a, m, b = angle(start), angle(middle), angle(end)
    if (m - a) % 360.0 <= (b - a) % 360.0:
        return a, (b - a) % 360.0
    return b, (a - b) % 360.0


def _fit(item: Sequence[Any]) -> dict | None:
    points = [_xy(item[i]) for i in range(1, 5)]
    found = _circle(points[0], _bezier(points, 0.5), points[3])
    if found is None:
        return None
    centre, radius = found
    if radius < _MIN_RADIUS_PT or any(
            abs(math.dist(_bezier(points, t), centre) - radius) > _FIT_PT for t in (0.25, 0.75)):
        return None
    start, length = _sweep(centre, points[0], _bezier(points, 0.5), points[3])
    return {"centre": centre, "radius": radius, "spans": [(start, length)], "ends": [points[0], points[3]]}


def _intervals(spans: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """Union on [0, 360) of (from, length) spans."""
    flat = []
    for start, length in spans:
        end = start + length
        flat.append((start, min(end, 360.0)))
        if end > 360.0:
            flat.append((0.0, end - 360.0))
    merged: list[list[float]] = []
    for lo, hi in sorted(flat):
        if merged and lo <= merged[-1][1] + 0.5:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    return [(lo, hi) for lo, hi in merged]


def _same_circle(a: dict, b: dict) -> bool:
    return math.dist(a["centre"], b["centre"]) <= _FIT_PT and abs(a["radius"] - b["radius"]) <= _FIT_PT


def _arcs(drawings: Sequence[Mapping[str, Any]]) -> tuple[list[dict], list[tuple[Point, Point]]]:
    """Whole arcs (same circle, same ink merged) and every straight stroke (for the door test)."""
    arcs: list[dict] = []
    strokes: list[tuple[Point, Point]] = []
    for index, row in enumerate(drawings):
        if not isinstance(row, Mapping) or row.get("color") is None:
            continue
        ink = tuple(round(float(v), 3) for v in row["color"])
        for item in row.get("items") or ():
            if item[0] == "l":
                strokes.append((_xy(item[1]), _xy(item[2])))
            if item[0] != "c":
                continue
            piece = _fit(item)
            if piece is None:
                continue
            for arc in arcs:
                if arc["ink"] == ink and _same_circle(arc, piece):
                    arc["spans"] += piece["spans"]
                    arc["ends"] += piece["ends"]
                    arc["paths"].add(index)
                    break
            else:
                arcs.append({**piece, "ink": ink, "paths": {index}})
    return arcs, strokes


def _door_swing(arc: dict, strokes: Sequence[tuple[Point, Point]]) -> bool:
    return any(
        math.dist(near, arc["centre"]) <= _FIT_PT and math.dist(far, end) <= _FIT_PT
        for a, b in strokes for near, far in ((a, b), (b, a)) for end in arc["ends"]
    )


def curved_wall_pairs(drawings: Sequence[Mapping[str, Any]]) -> list[dict]:
    """Report-only curved wall pairs, in a stable order. Inputs are never mutated."""
    arcs, strokes = _arcs(drawings)
    arcs.sort(key=lambda a: (round(a["centre"][0], 3), round(a["centre"][1], 3), round(a["radius"], 3), a["ink"]))
    for arc in arcs:
        arc["covered"] = _intervals(arc["spans"])
    found = []
    for i, inner in enumerate(arcs):
        for outer in arcs[i + 1:]:
            if inner["ink"] != outer["ink"] or math.dist(inner["centre"], outer["centre"]) > _FIT_PT:
                continue
            low, high = sorted((inner, outer), key=lambda a: a["radius"])
            thickness = high["radius"] - low["radius"]
            if not _STROKE_PAIR_THICK_MIN <= thickness <= _DARK_FILL_THICK_MAX:
                continue
            if any(sum(hi - lo for lo, hi in a["covered"]) >= _FULL_DEG for a in (low, high)):
                continue
            shared = [(max(a, c), min(b, d)) for a, b in low["covered"] for c, d in high["covered"]
                      if min(b, d) > max(a, c)]
            overlap = sum(hi - lo for lo, hi in shared)
            if overlap < _MIN_OVERLAP_DEG:
                continue
            status, reason = EvidenceResolutionStatus.CANDIDATE, REASON_PAIR
            if any(other is not low and other is not high and math.dist(other["centre"], low["centre"]) <= _FIT_PT
                   and low["radius"] - _DARK_FILL_THICK_MAX <= other["radius"] <= high["radius"] + _DARK_FILL_THICK_MAX
                   for other in arcs):
                status, reason = EvidenceResolutionStatus.ABSTAINED, REASON_RINGS
            elif _door_swing(low, strokes) or _door_swing(high, strokes):
                status, reason = EvidenceResolutionStatus.ABSTAINED, REASON_DOOR
            found.append({
                "status": status, "reason": reason, "centre_pt": low["centre"],
                "inner_radius_pt": low["radius"], "outer_radius_pt": high["radius"],
                "angle_intervals_deg": shared, "source_path_indices": sorted(low["paths"] | high["paths"]),
                "wall_authority": False, "version": CURVED_WALL_PAIR_SHADOW_VERSION,
            })
    found.sort(key=lambda r: (r["centre_pt"], r["inner_radius_pt"]))
    return found
