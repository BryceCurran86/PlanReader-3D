"""Original-source hosted swing doors that keep a 2D exterior footprint continuous.

The virtual bridge is diagnostic topology ONLY. The native swing-arc source
and separate end-jamb cap source must agree with two genuine external wall
ends, on one viewport, before any span can be proposed.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping, Sequence
import math
import re
from typing import Any

from pb_source_window_footprint_continuity import (
    _EXTERIOR_WALL_LAYER,
    _NON_WALL_LAYER,
    _line,
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
        if 0 <= i < len(drawings) and isinstance(drawings[i], Mapping)
    }
    scopes.discard("")
    return len(scopes) <= 1


def _exact_native_cap_terminated_hosts(
    bridge: ExteriorSwingDoorFootprintBridge,
    drawings: Sequence[Mapping[str, Any] | object],
) -> bool:
    """Require BOTH jambs to terminate at their original source wall ends.

    This is a tie breaker only when an arc already has several validated
    host interpretations. Do not pick a long perpendicular wall running
    past the jamb instead of the short, directly terminated wall host.
    A text, nearest-point snap or inferred segment cannot pass this gate.
    """
    ids = (
        bridge.first_host_path_id,
        bridge.second_host_path_id,
        *bridge.jamb_cap_path_ids,
    )
    if any(type(idx) is not int or idx < 0 or idx >= len(drawings) for idx in ids):
        return False
    if any(not isinstance(drawings[idx], Mapping) for idx in ids):
        return False
    rects = tuple(_rect(drawings[idx]) for idx in ids)
    if any(r is None for r in rects):
        return False
    left, right, cap_left, cap_right = rects
    if bridge.axis == "v":
        left_end, right_start = left[3], right[1]
        cap_a = (cap_left[1], cap_left[3])
        cap_b = (cap_right[1], cap_right[3])
    elif bridge.axis == "h":
        left_end, right_start = left[2], right[0]
        cap_a = (cap_left[0], cap_left[2])
        cap_b = (cap_right[0], cap_right[2])
    else:
        return False
    # Native near-contact allowance, not the 2.5 pt commercial snap.
    return (
        min(abs(left_end - v) for v in cap_a) <= 0.5
        and min(abs(right_start - v) for v in cap_b) <= 0.5
    )


def detect_exterior_swing_door_footprint_bridges(
    drawings: Sequence[Mapping[str, Any] | object],
    source_words: Sequence[Any] = (),
    *,
    page_index: int = -1,
    wall_layer_pattern: re.Pattern[str] | None = None,
    cap_across_tolerance_pt: float = 0.5,
    wall_bars: Sequence[Any] | None = None,
) -> tuple[ExteriorSwingDoorFootprintBridge, ...]:
    """One original cubic swing arc, two distinct wall hosts AND two jamb caps.

    Does not infer doors from a width label, a text-only schedule, or missing
    wall bars. Every wall/arc/cap is source-owned; if two candidate owner
    interpretations compete for one arc, neither is authorized. Windows and
    garage panel-lift openings use independent detectors.
    """
    if not (0.2 <= cap_across_tolerance_pt <= 1.0):
        raise ValueError("cap_across_tolerance_outside_source_range")
    wall_pattern = wall_layer_pattern or _EXTERIOR_WALL_LAYER
    has_any_layers = any(
        bool(str(r.get("layer") or "").strip())
        for r in drawings
        if isinstance(r, Mapping)
    )
    has_wall_layers = any(
        wall_pattern.search(str(r.get("layer") or ""))
        for r in drawings
        if isinstance(r, Mapping)
    )
    if not wall_bars and has_any_layers and not has_wall_layers:
        return ()
    walls: list[tuple[int, str, tuple[float, float, float, float]]] = []
    caps: list[tuple[int, str, tuple[float, float, float, float]]] = []
    arcs: list[tuple[int, str, tuple[float, float, float, float]]] = []

    if wall_bars:
        for bar in wall_bars:
            poly = getattr(bar, "polygon", None)
            if poly is None or poly.is_empty or not poly.is_valid:
                continue
            bb = tuple(float(v) for v in poly.bounds)
            dx, dy = bb[2] - bb[0], bb[3] - bb[1]
            if min(dx, dy) <= 16 and max(dx, dy) >= 0.7:
                pid = int(getattr(bar, "path_index", -1))
                layer = str(getattr(bar, "layer", "") or "")
                walls.append((pid, layer, bb))

    for idx, row in enumerate(drawings):
        if not isinstance(row, Mapping):
            continue
        layer = str(row.get("layer") or "")
        if has_wall_layers:
            is_wall = bool(wall_pattern.search(layer))
            is_opening = bool(re.search(r"(?:door|glaz|open|window)", layer, re.IGNORECASE))
            if not (is_wall or is_opening):
                continue
        elif _NON_WALL_LAYER.search(layer):
            continue
        ln = _line(row)
        if ln:
            d = math.dist(*ln)
            p0, p1 = ln
            dx, dy = abs(p0[0] - p1[0]), abs(p0[1] - p1[1])
            ln_bb = (min(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[0], p1[0]), max(p0[1], p1[1]))
            if 0.5 <= d <= 16.0 and (dx < 0.2 or dy < 0.2):
                caps.append((idx, layer, (ln_bb[0], ln_bb[1] - 0.2, ln_bb[2], ln_bb[3] + 0.2)))
        bounds = _rect(row)
        if bounds is None:
            continue
        fill = row.get("fill")
        if _is_quarter_swing_curve(row):
            arcs.append((idx, layer, bounds))
        if isinstance(fill, (tuple, list)) and len(fill) >= 3:
            tone = tuple(float(x) for x in fill[:3])
            if all(math.isfinite(x) for x in tone):
                dx, dy = bounds[2] - bounds[0], bounds[3] - bounds[1]
                if min(dx, dy) >= 0.22:
                    if max(tone) < 0.3:
                        if min(dx, dy) <= 16 and max(dx, dy) >= 0.7:
                            walls.append((idx, layer, bounds))
                    elif min(tone) > 0.35 and max(dx, dy) < 16:
                        caps.append((idx, layer, bounds))
    if not arcs or not walls or not caps:
        return ()
    window_labels = _words(source_words)

    matches: dict[int, list[ExteriorSwingDoorFootprintBridge]] = {}
    for arc_id, layer, arc in arcs:
        candidates: list[ExteriorSwingDoorFootprintBridge] = []
        for i, l1, a in walls:
            if has_wall_layers and l1 != layer and not bool(wall_pattern.search(l1)):
                continue
            for j, l2, b in walls:
                if i == j or (has_wall_layers and l2 != l1):
                    continue
                for axis in ("h", "v"):
                    if axis == "h":
                        if a[2] >= b[0]:
                            continue
                        gap = b[0] - a[2]
                        a_ortho = (a[3] - a[1]) > 1.2 * (a[2] - a[0])
                        b_ortho = (b[3] - b[1]) > 1.2 * (b[2] - b[0])
                        if not (a_ortho or b_ortho):
                            thick1, thick2 = a[3] - a[1], b[3] - b[1]
                            alignment = abs((a[1] + a[3]) - (b[1] + b[3])) / 2
                            bounds = (a[2], max(a[1], b[1]), b[0], min(a[3], b[3]))
                            max_thick_diff = 0.4
                            max_align = 0.35
                        elif b_ortho and not a_ortho:
                            thick1 = a[3] - a[1]
                            thick2 = b[2] - b[0]
                            spans_y = (b[1] <= a[3] + 1.0 and b[3] >= a[1] - 1.0)
                            alignment = 0.0 if spans_y else 999.0
                            bounds = (a[2], a[1], b[0], a[3])
                            max_thick_diff = 14.0
                            max_align = 0.5
                        elif a_ortho and not b_ortho:
                            thick1 = a[2] - a[0]
                            thick2 = b[3] - b[1]
                            spans_y = (a[1] <= b[3] + 1.0 and a[3] >= b[1] - 1.0)
                            alignment = 0.0 if spans_y else 999.0
                            bounds = (a[2], b[1], b[0], b[3])
                            max_thick_diff = 14.0
                            max_align = 0.5
                        else:
                            thick1 = a[2] - a[0]
                            thick2 = b[2] - b[0]
                            overlap_y = min(a[3], b[3]) - max(a[1], b[1])
                            alignment = 0.0 if overlap_y > 0 else 999.0
                            bounds = (a[2], min(a[1], b[1]), b[0], max(a[3], b[3]))
                            max_thick_diff = 14.0
                            max_align = 0.5
                        arc_len = arc[2] - arc[0]
                        insets = (arc[0] - bounds[0], bounds[2] - arc[2])
                        cross_near = min(
                            abs(arc[1] - a[1]),
                            abs(arc[1] - a[3]),
                            abs(arc[3] - a[1]),
                            abs(arc[3] - a[3]),
                            abs(arc[1] - b[1]),
                            abs(arc[1] - b[3]),
                            abs(arc[3] - b[1]),
                            abs(arc[3] - b[3]),
                        )
                        midpoint = (bounds[1] + bounds[3]) / 2
                    else:
                        if a[3] >= b[1]:
                            continue
                        gap = b[1] - a[3]
                        a_ortho = (a[2] - a[0]) > 1.2 * (a[3] - a[1])
                        b_ortho = (b[2] - b[0]) > 1.2 * (b[3] - b[1])
                        if not (a_ortho or b_ortho):
                            thick1, thick2 = a[2] - a[0], b[2] - b[0]
                            alignment = abs((a[0] + a[2]) - (b[0] + b[2])) / 2
                            bounds = (max(a[0], b[0]), a[3], min(a[2], b[2]), b[1])
                            max_thick_diff = 0.4
                            max_align = 0.35
                        elif b_ortho and not a_ortho:
                            thick1 = a[2] - a[0]
                            thick2 = b[3] - b[1]
                            spans_x = (b[0] <= a[2] + 1.0 and b[2] >= a[0] - 1.0)
                            alignment = 0.0 if spans_x else 999.0
                            bounds = (a[0], a[3], a[2], b[1])
                            max_thick_diff = 14.0
                            max_align = 0.5
                        elif a_ortho and not b_ortho:
                            thick1 = a[3] - a[1]
                            thick2 = b[2] - b[0]
                            spans_x = (a[0] <= b[2] + 1.0 and a[2] >= b[0] - 1.0)
                            alignment = 0.0 if spans_x else 999.0
                            bounds = (b[0], a[3], b[2], b[1])
                            max_thick_diff = 14.0
                            max_align = 0.5
                        else:
                            thick1 = a[3] - a[1]
                            thick2 = b[3] - b[1]
                            overlap_x = min(a[2], b[2]) - max(a[0], b[0])
                            alignment = 0.0 if overlap_x > 0 else 999.0
                            bounds = (min(a[0], b[0]), a[3], max(a[2], b[2]), b[1])
                            max_thick_diff = 14.0
                            max_align = 0.5
                        arc_len = arc[3] - arc[1]
                        insets = (arc[1] - bounds[1], bounds[3] - arc[3])
                        cross_near = min(
                            abs(arc[0] - a[0]),
                            abs(arc[0] - a[2]),
                            abs(arc[2] - a[0]),
                            abs(arc[2] - a[2]),
                            abs(arc[0] - b[0]),
                            abs(arc[0] - b[2]),
                            abs(arc[2] - b[0]),
                            abs(arc[2] - b[2]),
                        )
                        midpoint = (bounds[0] + bounds[2]) / 2
                    thick = min(thick1, thick2)
                    if (
                        not 10 <= gap <= 120
                        or not 0.7 <= thick <= 16
                        or abs(thick1 - thick2) > max_thick_diff
                        or alignment > max_align
                        or bounds[2] <= bounds[0]
                        or bounds[3] <= bounds[1]
                        or arc_len < gap * 0.75
                        or arc_len > gap * 1.15
                        or abs((gap - arc_len)) > 5.0
                        or not all(-2.5 <= z <= 1.5 * max(thick, 4.0) for z in insets)
                        or cross_near > max(0.5 * thick, 2.5)
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
                            if has_wall_layers and klayer != l1 and not bool(wall_pattern.search(klayer)):
                                continue
                            cap_edge_tol = 3.5 if (a_ortho or b_ortho) else 1.5
                            if axis == "h":
                                on_edge = (
                                    abs(c[0] - edge) < cap_edge_tol
                                    if endpoint == 0
                                    else abs(c[2] - edge) < cap_edge_tol
                                )
                                across = c[3] - c[1]
                                along = c[2] - c[0]
                                aligned = (
                                    abs(midpoint - (c[1] + c[3]) / 2) < 35.0
                                    if (a_ortho or b_ortho)
                                    else abs((c[1] + c[3]) - (a[1] + a[3])) / 2 < 0.6
                                )
                            else:
                                on_edge = (
                                    abs(c[1] - edge) < cap_edge_tol
                                    if endpoint == 0
                                    else abs(c[3] - edge) < cap_edge_tol
                                )
                                across = c[2] - c[0]
                                along = c[3] - c[1]
                                aligned = (
                                    abs(midpoint - (c[0] + c[2]) / 2) < 35.0
                                    if (a_ortho or b_ortho)
                                    else abs((c[0] + c[2]) - (a[0] + a[2])) / 2 < 0.6
                                )
                            max_across_diff = 4.0 if (a_ortho or b_ortho) else cap_across_tolerance_pt
                            if (
                                on_edge
                                and aligned
                                and abs(across - thick) <= max_across_diff
                                and along <= 2.5
                            ):
                                ids.append(k)
                        cap_pairs.append(sorted(set(ids)))
                    for end_idx in (0, 1):
                        if len(cap_pairs[end_idx]) > 1:
                            cap_objs = [c for k, _, c in caps if k in cap_pairs[end_idx]]
                            c_first = cap_objs[0]
                            if all(all(abs(c[x] - c_first[x]) < 0.1 for x in range(4)) for c in cap_objs):
                                cap_pairs[end_idx] = [cap_pairs[end_idx][0]]
                            else:
                                best_k = min(
                                    cap_pairs[end_idx],
                                    key=lambda k: abs(
                                        (([c for _k, _, c in caps if _k == k][0][3] - [c for _k, _, c in caps if _k == k][0][1])
                                         if axis == "h"
                                         else ([c for _k, _, c in caps if _k == k][0][2] - [c for _k, _, c in caps if _k == k][0][0]))
                                        - thick
                                    )
                                )
                                cap_pairs[end_idx] = [best_k]
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
        elif len(unique) > 1:
            # A long intersecting wall can mimic the short native host of
            # one exterior swing door. When exactly one of the otherwise
            # admissible candidates has both source jambs at its actual wall
            # terminations, retain that independently witnessed owner.
            # Multiple exact owners remain for the existing ambiguity gate.
            exact = [
                candidate for candidate in unique.values()
                if _exact_native_cap_terminated_hosts(candidate, drawings)
            ]
            if len(exact) == 1:
                matches[arc_id] = exact
                continue
            c_list = list(unique.values())
            # Group by opening locality: candidate bounds near the arc
            arc_cx = (arc[0] + arc[2]) / 2
            arc_cy = (arc[1] + arc[3]) / 2
            filtered = [
                c
                for c in c_list
                if (
                    c.axis == "h"
                    and abs((c.bounds_pdf_pts[0] + c.bounds_pdf_pts[2]) / 2 - arc_cx) < 20.0
                )
                or (
                    c.axis == "v"
                    and abs((c.bounds_pdf_pts[1] + c.bounds_pdf_pts[3]) / 2 - arc_cy) < 20.0
                )
            ]
            if filtered:
                ref_b = filtered[0].bounds_pdf_pts
                ref_axis = filtered[0].axis
                same_opening = all(
                    c.axis == ref_axis
                    and max(abs(c.bounds_pdf_pts[k] - ref_b[k]) for k in range(4)) < 15.0
                    for c in filtered
                )
                if same_opening:
                    arc_len = arc[2] - arc[0] if ref_axis == "h" else arc[3] - arc[1]
                    best = min(
                        filtered,
                        key=lambda c: abs(
                            (
                                c.bounds_pdf_pts[2] - c.bounds_pdf_pts[0]
                                if ref_axis == "h"
                                else c.bounds_pdf_pts[3] - c.bounds_pdf_pts[1]
                            )
                            - arc_len
                        ),
                    )
                    matches[arc_id] = [best]
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
