"""Original-source hosted swing doors that keep a 2D exterior footprint continuous.

The virtual bridge is diagnostic topology ONLY. The native swing-arc source
and separate end-jamb cap source must agree with two genuine external wall
ends, on one viewport, before any span can be proposed.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping, Sequence
import math
from typing import Any

from pb_source_window_footprint_continuity import (
    _EXTERIOR_WALL_LAYER,
    _rect,
    _point,
    _words,
)


@dataclass(frozen=True)
class ExteriorSwingDoorFootprintBridge:
    first_host_path_id: int
    second_host_path_id: int
    swing_arc_path_id: int
    jamb_cap_path_ids: tuple[int, int]
    bounds_pdf_pts: tuple[float, float, float, float]
    axis: str
    page_index: int = -1
    physical_wall_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": "source_hosted_swing_door_footprint_continuity_only",
            "first_host_path_id": self.first_host_path_id,
            "second_host_path_id": self.second_host_path_id,
            "swing_arc_path_id": self.swing_arc_path_id,
            "jamb_cap_path_ids": list(self.jamb_cap_path_ids),
            "bounds_pdf_pts": list(self.bounds_pdf_pts),
            "axis": self.axis,
            "page_index": self.page_index,
            "physical_wall_authenticated": False,
            "measurement_authorized": False,
        }


def _is_quarter_swing_curve(row: Mapping[str, Any]) -> bool:
    items = row.get("items") or ()
    if len(items) != 1 or items[0][0] != "c" or len(items[0]) != 5:
        return False
    points = [_point(v) for v in items[0][1:]]
    if any(p is None for p in points):
        return False
    a, c1, c2, b = points
    if min(abs(a[0] - b[0]), abs(a[1] - b[1])) < 10:
        return False
    if abs(abs(a[0] - b[0]) - abs(a[1] - b[1])) > 2.5:
        return False
    is_horizontal_first = abs(c1[1] - a[1]) < 0.25 and abs(c2[0] - b[0]) < 0.25
    is_vertical_first = abs(c1[0] - a[0]) < 0.25 and abs(c2[1] - b[1]) < 0.25
    return is_horizontal_first or is_vertical_first


def _viewports(
    drawings: Sequence[Mapping[str, Any] | object], paths: tuple[int, ...]
) -> bool:
    scopes = {
        str(
            drawings[i].get("viewport_id")
            or drawings[i].get("source_viewport_id")
            or ""
        ).strip()
        for i in paths
        if isinstance(drawings[i], Mapping)
    }
    scopes.discard("")
    return len(scopes) <= 1


def detect_exterior_swing_door_footprint_bridges(
    drawings: Sequence[Mapping[str, Any] | object],
    source_words: Sequence[Any] = (),
    *,
    page_index: int = -1,
) -> tuple[ExteriorSwingDoorFootprintBridge, ...]:
    """One original cubic swing arc, two distinct wall hosts AND two jamb caps.

    Does not infer doors from a width label, a text-only schedule, or missing
    wall bars. Every wall/arc/cap is source-owned; if two candidate owner
    interpretations compete for one arc, neither is authorized. Windows and
    garage panel-lift openings use independent detectors.
    """
    walls: list[tuple[int, str, tuple[float, float, float, float]]] = []
    caps: list[tuple[int, str, tuple[float, float, float, float]]] = []
    arcs: list[tuple[int, str, tuple[float, float, float, float]]] = []
    for idx, row in enumerate(drawings):
        if not isinstance(row, Mapping):
            continue
        layer = str(row.get("layer") or "")
        if not _EXTERIOR_WALL_LAYER.search(layer):
            continue
        bounds = _rect(row)
        if bounds is None:
            continue
        fill = row.get("fill")
        if _is_quarter_swing_curve(row):
            arcs.append((idx, layer, bounds))
        if not isinstance(fill, (tuple, list)) or len(fill) < 3:
            continue
        tone = tuple(float(x) for x in fill[:3])
        if not all(math.isfinite(x) for x in tone):
            continue
        dx, dy = bounds[2] - bounds[0], bounds[3] - bounds[1]
        if min(dx, dy) < 0.22:
            continue
        if max(tone) < 0.3:
            # Short native jamb-side wall faces are authentic wall hosts too.
            if min(dx, dy) <= 8 and max(dx, dy) >= 1.0:
                walls.append((idx, layer, bounds))
        elif min(tone) > 0.35 and max(dx, dy) < 12:
            caps.append((idx, layer, bounds))
    if not arcs or not walls or not caps:
        return ()
    window_labels = _words(source_words)

    matches: dict[int, list[ExteriorSwingDoorFootprintBridge]] = {}
    for arc_id, layer, arc in arcs:
        candidates: list[ExteriorSwingDoorFootprintBridge] = []
        for i, l1, a in walls:
            if l1 != layer:
                continue
            for j, l2, b in walls:
                if i == j or l2 != layer:
                    continue
                for axis in ("h", "v"):
                    if axis == "h":
                        # B continues right of A, same source-painted wall band.
                        if a[2] >= b[0]:
                            continue
                        thick1, thick2 = a[3] - a[1], b[3] - b[1]
                        gap = b[0] - a[2]
                        alignment = abs((a[1] + a[3]) - (b[1] + b[3])) / 2
                        bounds = (a[2], max(a[1], b[1]), b[0], min(a[3], b[3]))
                        arc_len = arc[2] - arc[0]
                        insets = (arc[0] - bounds[0], bounds[2] - arc[2])
                        cross_near = min(
                            abs(arc[1] - a[1]),
                            abs(arc[1] - a[3]),
                            abs(arc[3] - a[1]),
                            abs(arc[3] - a[3]),
                        )
                        midpoint = (bounds[1] + bounds[3]) / 2
                    else:
                        if a[3] >= b[1]:
                            continue
                        thick1, thick2 = a[2] - a[0], b[2] - b[0]
                        gap = b[1] - a[3]
                        alignment = abs((a[0] + a[2]) - (b[0] + b[2])) / 2
                        bounds = (max(a[0], b[0]), a[3], min(a[2], b[2]), b[1])
                        arc_len = arc[3] - arc[1]
                        insets = (arc[1] - bounds[1], bounds[3] - arc[3])
                        cross_near = min(
                            abs(arc[0] - a[0]),
                            abs(arc[0] - a[2]),
                            abs(arc[2] - a[0]),
                            abs(arc[2] - a[2]),
                        )
                        midpoint = (bounds[0] + bounds[2]) / 2
                    thick = min(thick1, thick2)
                    if (
                        not 10 <= gap <= 120
                        or not 0.7 <= thick <= 8
                        or abs(thick1 - thick2) > 0.4
                        or alignment > 0.35
                        or bounds[2] <= bounds[0]
                        or bounds[3] <= bounds[1]
                        or arc_len < gap * 0.85
                        or arc_len > gap
                        or abs((gap - arc_len)) > 3.2
                        or not all(0.25 <= z <= 1.3 * thick for z in insets)
                        or cross_near > 0.5 * thick
                    ):
                        continue
                    # The source arc must swing away from the wall line rather
                    # than being a curved interior decorative drawing.
                    if axis == "h":
                        if arc[3] - arc[1] < 0.8 * gap:
                            continue
                    else:
                        if arc[2] - arc[0] < 0.8 * gap:
                            continue
                    # This is a DOOR (arc + hosted jambs), never a W/ASW
                    # gap incorrectly reclassified because a window word is
                    # printed at its center.
                    if any(
                        (
                            bounds[0] <= (r[0] + r[2]) / 2 <= bounds[2]
                            and min(abs(r[1] - midpoint), abs(r[3] - midpoint)) < 30
                        )
                        if axis == "h"
                        else (
                            bounds[1] <= (r[1] + r[3]) / 2 <= bounds[3]
                            and min(abs(r[0] - midpoint), abs(r[2] - midpoint)) < 30
                        )
                        for _code, r in window_labels
                    ):
                        continue
                    cap_pairs = []
                    for endpoint in (0, 1):
                        edge = (
                            (a[2] if endpoint == 0 else b[0])
                            if axis == "h"
                            else (a[3] if endpoint == 0 else b[1])
                        )
                        ids = []
                        for k, klayer, c in caps:
                            if klayer != layer:
                                continue
                            if axis == "h":
                                on_edge = (
                                    abs(c[0] - edge) < 0.2
                                    if endpoint == 0
                                    else abs(c[2] - edge) < 0.2
                                )
                                across = c[3] - c[1]
                                along = c[2] - c[0]
                                aligned = abs((c[1] + c[3]) - (a[1] + a[3])) / 2 < 0.4
                            else:
                                on_edge = (
                                    abs(c[1] - edge) < 0.2
                                    if endpoint == 0
                                    else abs(c[3] - edge) < 0.2
                                )
                                across = c[2] - c[0]
                                along = c[3] - c[1]
                                aligned = abs((c[0] + c[2]) - (a[0] + a[2])) / 2 < 0.4
                            if (
                                on_edge
                                and aligned
                                and abs(across - thick) < 0.5
                                and 0.25 <= along <= 1.5
                            ):
                                ids.append(k)
                        cap_pairs.append(sorted(set(ids)))
                    if len(cap_pairs[0]) != 1 or len(cap_pairs[1]) != 1:
                        continue
                    k1, k2 = cap_pairs[0][0], cap_pairs[1][0]
                    if k1 == k2 or not _viewports(drawings, (i, j, arc_id, k1, k2)):
                        continue
                    # Another real wall body inside the same lane contradicts
                    # the advertised uninterrupted opening span.
                    obstructed = False
                    for k, klayer, other in walls:
                        if k in (i, j) or klayer != layer:
                            continue
                        if axis == "h":
                            overlap = min(other[2], bounds[2]) - max(
                                other[0], bounds[0]
                            )
                            same_lane = (
                                abs((other[1] + other[3]) - (a[1] + a[3])) / 2 < 0.4
                            )
                            full = (other[3] - other[1]) >= 0.8 * thick
                        else:
                            overlap = min(other[3], bounds[3]) - max(
                                other[1], bounds[1]
                            )
                            same_lane = (
                                abs((other[0] + other[2]) - (a[0] + a[2])) / 2 < 0.4
                            )
                            full = (other[2] - other[0]) >= 0.8 * thick
                        if overlap > 0.4 and same_lane and full:
                            obstructed = True
                            break
                    if obstructed:
                        continue
                    candidates.append(
                        ExteriorSwingDoorFootprintBridge(
                            first_host_path_id=i,
                            second_host_path_id=j,
                            swing_arc_path_id=arc_id,
                            jamb_cap_path_ids=(k1, k2),
                            bounds_pdf_pts=bounds,
                            axis=axis,
                            page_index=page_index,
                        )
                    )
        # One native arc cannot grant two distinct door-boundary owners.
        unique = {
            (
                r.first_host_path_id,
                r.second_host_path_id,
                r.jamb_cap_path_ids,
                r.bounds_pdf_pts,
            ): r
            for r in candidates
        }
        if len(unique) == 1:
            matches[arc_id] = list(unique.values())
    # Two different arcs competing for a host pair are not silently accepted.
    owner_pair_counts: dict[tuple[int, int], int] = {}
    for candidates in matches.values():
        r = candidates[0]
        key = (r.first_host_path_id, r.second_host_path_id)
        owner_pair_counts[key] = owner_pair_counts.get(key, 0) + 1
    return tuple(
        sorted(
            (
                v[0]
                for v in matches.values()
                if owner_pair_counts[
                    (v[0].first_host_path_id, v[0].second_host_path_id)
                ]
                == 1
            ),
            key=lambda d: (d.first_host_path_id, d.second_host_path_id),
        )
    )
