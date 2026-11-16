"""Footprint-only exterior window continuity from original PDF vector owners.

A window aperture interrupts wall ink, not the 2D building boundary.
This module never authenticates a physical wall or issues material quantities.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from shapely.geometry import box

_WINDOW_CODE = re.compile(r"^(?:asw|aw|window|win|fgw|sgw|w[- ]?\d+[a-z]*|\d{1,2})$", re.IGNORECASE)
_DOOR_CODE = re.compile(
    r"^(?:d[- ]?\d+[a-z]*|door|sgd|assd[- ]?\d*|asd[- ]?\d*|sd[- ]?\d*|stacker)$",
    re.IGNORECASE,
)
_EXTERIOR_WALL_LAYER = re.compile(r"(?:wall.*extern|extern.*wall|wall.*exterior|exterior.*wall|\ba-wall\b|\ba-wall$)", re.IGNORECASE)
_NON_WALL_LAYER = re.compile(r"(?:dim|anno|text|grid|title|border|note)", re.IGNORECASE)


@dataclass(frozen=True)
class WindowFootprintBridge:
    left_host_path_id: int
    right_host_path_id: int
    marker_path_ids: tuple[int, int]
    label_text: str
    bounds_pdf_pts: tuple[float, float, float, float]
    axis: str
    page_index: int
    physical_wall_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "left_host_path_id": self.left_host_path_id,
            "right_host_path_id": self.right_host_path_id,
            "marker_path_ids": list(self.marker_path_ids),
            "label_text": self.label_text,
            "bounds_pdf_pts": list(self.bounds_pdf_pts),
            "axis": self.axis,
            "page_index": self.page_index,
            "kind": "exterior_window_footprint_continuity_only",
            "physical_wall_authenticated": False,
            "measurement_authorized": False,
        }


def _point(value: Any) -> tuple[float, float] | None:
    try:
        x, y = float(value.x), float(value.y)
        if math.isfinite(x) and math.isfinite(y):
            return x, y
    except (AttributeError, ValueError, TypeError):
        return None
    return None


def _rect(row: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    try:
        rect = row["rect"]
        nums = tuple(float(v) for v in rect)
        if (
            len(nums) == 4
            and all(math.isfinite(v) for v in nums)
            and nums[2] > nums[0]
            and nums[3] > nums[1]
        ):
            return nums
    except (KeyError, TypeError, ValueError):
        return None
    return None


def _line(row: Mapping[str, Any]) -> tuple[tuple[float, float], tuple[float, float]] | None:
    items = row.get("items", ())
    if len(items) != 1 or items[0][0] != "l" or len(items[0]) < 3:
        return None
    a, b = _point(items[0][1]), _point(items[0][2])
    if a is None or b is None or math.dist(a, b) < 0.5:
        return None
    return a, b


def _words(
    words: Sequence[Mapping[str, Any] | Sequence[Any]],
    *,
    pattern: re.Pattern[str] = _WINDOW_CODE,
) -> list[tuple[str, tuple[float, float, float, float]]]:
    out = []
    for word in words:
        try:
            if isinstance(word, Mapping):
                raw = str(word.get("text") or "")
                bounds = tuple(float(x) for x in word["bbox_pdf_pts"])
            else:
                raw = str(word[4])
                bounds = tuple(float(x) for x in word[:4])
            if pattern.fullmatch(raw.strip()) and len(bounds) == 4 and all(map(math.isfinite, bounds)):
                out.append((raw, bounds))
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return out


def detect_exterior_window_footprint_bridges(
    drawings: Sequence[Mapping[str, Any] | object],
    source_words: Sequence[Mapping[str, Any] | Sequence[Any]],
    *,
    page_index: int = -1,
    wall_bars: Sequence[Any] | None = None,
) -> tuple[WindowFootprintBridge, ...]:
    """Connect *source-verified* exterior ASW/window openings as topology only.

    Require two same-layer native host wall fills, a native paired window
    marker, and a uniquely associated printed window code. Internal joinery,
    blank gaps, dimension marks and competing host wall runs are never closed.
    """
    labels = _words(source_words)
    door_labels = _words(source_words, pattern=_DOOR_CODE)
    if not labels:
        return ()
    has_any_layers = any(
        bool(str(r.get("layer") or "").strip())
        for r in drawings
        if isinstance(r, Mapping)
    )
    has_wall_layers = any(
        _EXTERIOR_WALL_LAYER.search(str(r.get("layer") or ""))
        for r in drawings
        if isinstance(r, Mapping)
    )
    if not wall_bars and has_any_layers and not has_wall_layers:
        return ()
    walls: list[tuple[int, str, tuple[float, float, float, float]]] = []
    filled_rectangles: list[tuple[int, str, tuple[float, float, float, float]]] = []
    marker_lines: list[tuple[int, str, tuple[tuple[float, float], tuple[float, float]]]] = []
    frame_lines: list[tuple[int, str, tuple[tuple[float, float], tuple[float, float]]]] = []

    if wall_bars:
        for bar in wall_bars:
            poly = getattr(bar, "polygon", None)
            if poly is None or poly.is_empty or not poly.is_valid:
                continue
            bb = tuple(float(v) for v in poly.bounds)
            dx, dy = bb[2] - bb[0], bb[3] - bb[1]
            if min(dx, dy) >= 0.3 and max(dx, dy) > 1.2 * min(dx, dy):
                pid = int(getattr(bar, "path_index", -1))
                layer = str(getattr(bar, "layer", "") or "")
                walls.append((pid, layer, bb))
                filled_rectangles.append((pid, layer, bb))

    for idx, row in enumerate(drawings):
        if not isinstance(row, Mapping):
            continue
        layer = str(row.get("layer") or "")
        if has_wall_layers:
            if not _EXTERIOR_WALL_LAYER.search(layer):
                continue
        elif _NON_WALL_LAYER.search(layer):
            continue
        bounds = _rect(row)
        fill = row.get("fill")
        if (
            bounds
            and isinstance(fill, (tuple, list))
            and len(fill) >= 3
            and max(float(v) for v in fill[:3]) < 0.3
        ):
            filled_rectangles.append((idx, layer, bounds))
            dx, dy = bounds[2] - bounds[0], bounds[3] - bounds[1]
            # Genuine external wall ends beside windows can be short
            # jamb-side stubs (2-4 wall thicknesses). The actual window
            # marker + unique same-layer hosts + label remain mandatory;
            # this aspect gate must not erase those original wall owners.
            if max(dx, dy) > 2 * min(dx, dy) and min(dx, dy) >= 0.3:
                walls.append((idx, layer, bounds))
        ln = _line(row)
        if ln:
            d = math.dist(*ln)
            if 0.5 <= d <= 16:
                marker_lines.append((idx, layer, ln))
            if 2.0 <= d <= 160:
                p0, p1 = ln
                if abs(p0[1] - p1[1]) < 0.1 or abs(p0[0] - p1[0]) < 0.1:
                    frame_lines.append((idx, layer, ln))
    if not has_wall_layers and labels:
        marker_lines = [
            m for m in marker_lines
            if any(
                abs((m[2][0][0] + m[2][1][0]) / 2 - (w[0] + w[2]) / 2) < 60
                and abs((m[2][0][1] + m[2][1][1]) / 2 - (w[1] + w[3]) / 2) < 60
                for _, w in labels
            )
        ]
    results: list[WindowFootprintBridge] = []
    seen_hosts: set[tuple[int, int]] = set()
    for a_idx, (a_path, a_layer, (a0, a1)) in enumerate(marker_lines):
        for b_path, b_layer, (b0, b1) in marker_lines[a_idx+1:]:
            if a_layer != b_layer:
                continue
            # A pair of short native strokes sharing one endpoint: the
            # standard paired chevron witness, not arbitrary nearby ink.
            pair = None
            for first, second in ((a0, a1), (a1, a0)):
                for other0, other1 in ((b0, b1), (b1, b0)):
                    if math.dist(first, other0) < .08 and .2 < math.dist(second, other1) <= 16:
                        pair = (first, second, other1)
            if pair is None:
                continue
            tip, end1, end2 = pair
            mx, my = (tip[0]+end1[0]+end2[0])/3, (tip[1]+end1[1]+end2[1])/3
            delta_x, delta_y = abs(end1[0]-tip[0]), abs(end1[1]-tip[1])
            # A horizontal wall uses a mostly horizontal symbol; vertical
            # windows may be the rotated counterpart.
            axis = "h" if delta_x >= delta_y else "v"
            if axis == "h" and delta_x < 1:
                continue
            if axis == "v" and delta_y < 1:
                continue
            candidates: list[tuple[int, int, tuple[float, float, float, float], str]] = []
            for i, layer_i, first in walls:
                if layer_i != a_layer:
                    continue
                for j, layer_j, second in walls:
                    if i == j or layer_j != a_layer:
                        continue
                    if axis == "h":
                        if first[2] >= mx or second[0] <= mx:
                            continue
                        gap = second[0] - first[2]
                        first_ortho = (first[3] - first[1]) > 1.2 * (first[2] - first[0])
                        second_ortho = (second[3] - second[1]) > 1.2 * (second[2] - second[0])
                        if not (first_ortho or second_ortho):
                            thick1, thick2 = first[3] - first[1], second[3] - second[1]
                            alignment = abs((first[1] + first[3]) - (second[1] + second[3])) / 2
                            bounds = (first[2], max(first[1], second[1]), second[0], min(first[3], second[3]))
                            offset = min(abs(my - first[1]), abs(my - first[3]), abs(my - second[1]), abs(my - second[3]))
                            max_thick_diff = 0.6
                        elif second_ortho and not first_ortho:
                            thick1 = first[3] - first[1]
                            thick2 = second[2] - second[0]
                            spans_y = (second[1] <= first[3] + 1.0 and second[3] >= first[1] - 1.0)
                            alignment = 0.0 if spans_y else 999.0
                            bounds = (first[2], first[1], second[0], first[3])
                            offset = min(abs(my - first[1]), abs(my - first[3]))
                            max_thick_diff = 8.0
                        elif first_ortho and not second_ortho:
                            thick1 = first[2] - first[0]
                            thick2 = second[3] - second[1]
                            spans_y = (first[1] <= second[3] + 1.0 and first[3] >= second[1] - 1.0)
                            alignment = 0.0 if spans_y else 999.0
                            bounds = (first[2], second[1], second[0], second[3])
                            offset = min(abs(my - second[1]), abs(my - second[3]))
                            max_thick_diff = 8.0
                        else:
                            continue
                    else:
                        if first[3] >= my or second[1] <= my:
                            continue
                        gap = second[1] - first[3]
                        first_ortho = (first[2] - first[0]) > 1.2 * (first[3] - first[1])
                        second_ortho = (second[2] - second[0]) > 1.2 * (second[3] - second[1])
                        if not (first_ortho or second_ortho):
                            thick1, thick2 = first[2] - first[0], second[2] - second[0]
                            alignment = abs((first[0] + first[2]) - (second[0] + second[2])) / 2
                            bounds = (max(first[0], second[0]), first[3], min(first[2], second[2]), second[1])
                            offset = min(abs(mx - first[0]), abs(mx - first[2]), abs(mx - second[0]), abs(mx - second[2]))
                            max_thick_diff = 0.6
                        elif second_ortho and not first_ortho:
                            thick1 = first[2] - first[0]
                            thick2 = second[3] - second[1]
                            spans_x = (second[0] <= first[2] + 1.0 and second[2] >= first[0] - 1.0)
                            alignment = 0.0 if spans_x else 999.0
                            bounds = (first[0], first[3], first[2], second[1])
                            offset = min(abs(mx - first[0]), abs(mx - first[2]))
                            max_thick_diff = 8.0
                        elif first_ortho and not second_ortho:
                            thick1 = first[3] - first[1]
                            thick2 = second[2] - second[0]
                            spans_x = (first[0] <= second[2] + 1.0 and first[2] >= second[0] - 1.0)
                            alignment = 0.0 if spans_x else 999.0
                            bounds = (second[0], first[3], second[2], second[1])
                            offset = min(abs(mx - second[0]), abs(mx - second[2]))
                            max_thick_diff = 8.0
                        else:
                            continue
                    if not 2 <= gap <= 160 or alignment > 0.5 or abs(thick1 - thick2) > max_thick_diff:
                        continue
                    if offset > 4*max(thick1,thick2) or bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
                        continue
                    if not box(*bounds).buffer(3*max(thick1,thick2)).covers(box(mx,my,mx+.001,my+.001)):
                        continue
                    # Another native wall segment inside this proposed window
                    # span means these are not the two immediately adjoining
                    # hosts. It cannot be hidden behind a longer guessed gap.
                    intervening = False
                    for k, other_layer, other in filled_rectangles:
                        if k in (i, j) or other_layer != a_layer:
                            continue
                        if axis=="h":
                            overlaps = min(bounds[2],other[2])-max(bounds[0],other[0])
                            centered = abs((other[1]+other[3])-(first[1]+first[3]))/2 < .3
                        else:
                            overlaps = min(bounds[3],other[3])-max(bounds[1],other[1])
                            centered = abs((other[0]+other[2])-(first[0]+first[2]))/2 < .3
                        if overlaps > .3 and centered:
                            # A native *sash* may sit inside the aperture on
                            # the same CAD layer. It is not a through-wall:
                            # its cross-section is narrower than the host
                            # band and its ends stop within the opening.
                            # A full-thickness partition still vetoes closure.
                            cross_span = (
                                other[3]-other[1] if axis=="h"
                                else other[2]-other[0]
                            )
                            host_span = min(thick1,thick2)
                            if axis=="h":
                                inset = (
                                    other[0] > bounds[0]+.1*host_span
                                    and other[2] < bounds[2]-.1*host_span
                                    and other[1] >= first[1]-.2*host_span
                                    and other[3] <= first[3]+.2*host_span
                                )
                            else:
                                inset = (
                                    other[1] > bounds[1]+.1*host_span
                                    and other[3] < bounds[3]-.1*host_span
                                    and other[0] >= first[0]-.2*host_span
                                    and other[2] <= first[2]+.2*host_span
                                )
                            if cross_span < .8*host_span and inset:
                                continue
                            if any(
                                (
                                    abs((ln[0][1] + ln[1][1]) / 2 - (other[1] + other[3]) / 2) < 1.0
                                    and min(ln[0][0], ln[1][0]) <= other[0] + 1.0
                                    and max(ln[0][0], ln[1][0]) >= other[2] - 1.0
                                )
                                if axis == "h"
                                else (
                                    abs((ln[0][0] + ln[1][0]) / 2 - (other[0] + other[2]) / 2) < 1.0
                                    and min(ln[0][1], ln[1][1]) <= other[1] + 1.0
                                    and max(ln[0][1], ln[1][1]) >= other[3] - 1.0
                                )
                                for _, _, ln in frame_lines
                            ):
                                continue
                            intervening = True
                            break
                    if intervening:
                        continue
                    matching = [
                        raw for raw, w in labels
                        if (bounds[0]-1 <= (w[0]+w[2])/2 <= bounds[2]+1
                            and min(abs(w[1]-my),abs(w[3]-my)) < 35)
                        if axis=="h"
                    ] if axis=="h" else [
                        raw for raw, w in labels
                        if (bounds[1]-1 <= (w[1]+w[3])/2 <= bounds[3]+1
                            and min(abs(w[0]-mx),abs(w[2]-mx)) < 35)
                    ]
                    # A printed door/stacker callout occupying this same
                    # gap conflicts with the window label. Never resolve
                    # the identity by choosing the first word encountered.
                    # Only a door code clearly centered in THIS opening
                    # competes with its window label. Near-jamb DOOR notes
                    # can describe an adjacent opening (3Laurel original).
                    # Do not close the source window merely because such
                    # independent text occurs within the broad label radius.
                    label_margin = max(2.0, 0.15 * gap)
                    door_competitors = [
                        raw for raw, w in door_labels
                        if bounds[0]+label_margin <= (w[0]+w[2])/2 <= bounds[2]-label_margin
                        and min(abs(w[1]-my),abs(w[3]-my)) < 35
                    ] if axis == "h" else [
                        raw for raw, w in door_labels
                        if bounds[1]+label_margin <= (w[1]+w[3])/2 <= bounds[3]-label_margin
                        and min(abs(w[0]-mx),abs(w[2]-mx)) < 35
                    ]
                    if len(matching)==1 and not door_competitors:
                        candidates.append((i,j,bounds,matching[0]))
            # Select the two immediately adjacent native wall faces, not a
            # distant bar that happens to be collinear behind the window.
            # A tied or overlapping host remains ambiguous and fails closed.
            unique = {(i,j,bounds,label) for i,j,bounds,label in candidates}
            if not unique:
                continue
            ranked = sorted(
                unique,
                key=lambda item: (
                    round(item[2][2]-item[2][0] if axis=="h" else item[2][3]-item[2][1], 5),
                    item[0], item[1],
                ),
            )
            best_gap = (
                ranked[0][2][2]-ranked[0][2][0] if axis=="h"
                else ranked[0][2][3]-ranked[0][2][1]
            )
            close_rivals = [
                item for item in ranked
                if (item[2][2]-item[2][0] if axis=="h" else item[2][3]-item[2][1])
                <= best_gap + max(.3, .01*best_gap)
            ]
            if len(close_rivals) != 1:
                continue
            i,j,bounds,label = ranked[0]
            # A source page may contain distinct overlaid CAD viewports
            # sharing the same wall layer. Never join owners with explicit
            # contradictory viewport identities.
            scopes = {
                str(drawings[k].get("viewport_id")
                    or drawings[k].get("source_viewport_id") or "").strip()
                for k in (i, j, a_path, b_path)
                if 0 <= k < len(drawings) and isinstance(drawings[k], Mapping)
            }
            scopes.discard("")
            if len(scopes) > 1:
                continue
            if (i,j) in seen_hosts:
                continue
            seen_hosts.add((i,j))
            results.append(WindowFootprintBridge(
                left_host_path_id=i, right_host_path_id=j,
                marker_path_ids=tuple(sorted((a_path, b_path))),
                label_text=label, bounds_pdf_pts=bounds, axis=axis,
                page_index=page_index,
            ))

    # Parallel window frame line witness for standard residential plans
    # where windows are drawn as parallel frame/glazing lines across the gap.
    covered_labels = {r.label_text for r in results}
    unmatched_labels = [lbl for lbl in labels if lbl[0] not in covered_labels]
    for label_raw, label_bounds in unmatched_labels:
        lx = (label_bounds[0] + label_bounds[2]) / 2
        ly = (label_bounds[1] + label_bounds[3]) / 2
        cand_list = []
        for i, layer_i, first in walls:
            for j, layer_j, second in walls:
                if i == j or (has_wall_layers and layer_i != layer_j):
                    continue
                # Horizontal opening
                if first[2] < second[0]:
                    gap = second[0] - first[2]
                    thick1, thick2 = first[3] - first[1], second[3] - second[1]
                    first_is_vert = thick1 > 1.8 * (first[2] - first[0]) and thick1 >= 10.0
                    second_is_vert = thick2 > 1.8 * (second[2] - second[0]) and thick2 >= 10.0

                    if not first_is_vert and not second_is_vert:
                        alignment = abs((first[1] + first[3]) - (second[1] + second[3])) / 2
                        bounds = (first[2], max(first[1], second[1]), second[0], min(first[3], second[3]))
                        valid_geom = alignment <= 0.5 and abs(thick1 - thick2) <= 0.6
                    elif first_is_vert and not second_is_vert:
                        bounds = (first[2], second[1], second[0], second[3])
                        valid_geom = first[1] <= bounds[1] + 1.0 and first[3] >= bounds[3] - 1.0
                    elif not first_is_vert and second_is_vert:
                        bounds = (first[2], first[1], second[0], first[3])
                        valid_geom = second[1] <= bounds[1] + 1.0 and second[3] >= bounds[3] - 1.0
                    else:
                        valid_geom = False
                        bounds = (first[2], 0.0, second[0], 0.0)

                    if (
                        valid_geom
                        and 2.0 <= gap <= 160.0
                        and bounds[0] - 2.0 <= lx <= bounds[2] + 2.0
                        and min(abs(ly - bounds[1]), abs(ly - bounds[3])) < 35
                    ):
                        label_margin = max(2.0, 0.15 * gap)
                        door_comp = [
                            raw for raw, w in door_labels
                            if bounds[0] + label_margin <= (w[0] + w[2]) / 2 <= bounds[2] - label_margin
                            and min(abs(w[1] - ly), abs(w[3] - ly)) < 35
                        ]
                        if not door_comp:
                            flines = [
                                fl for fl in frame_lines
                                if (not has_wall_layers or fl[1] == layer_i)
                                and bounds[0] - 2.5 <= min(fl[2][0][0], fl[2][1][0])
                                and max(fl[2][0][0], fl[2][1][0]) <= bounds[2] + 2.5
                                and bounds[1] - 1.5 <= (fl[2][0][1] + fl[2][1][1]) / 2 <= bounds[3] + 1.5
                            ]
                            if flines:
                                min_x = min(min(fl[2][0][0], fl[2][1][0]) for fl in flines)
                                max_x = max(max(fl[2][0][0], fl[2][1][0]) for fl in flines)
                                total_len = sum(math.dist(*fl[2]) for fl in flines)
                                if (
                                    abs(min_x - bounds[0]) < 3.0
                                    and abs(max_x - bounds[2]) < 3.0
                                    and total_len >= 0.7 * gap
                                ):
                                    marker_ids = tuple(sorted(dict.fromkeys(fl[0] for fl in flines)))[:4]
                                    cand_list.append((i, j, bounds, label_raw, marker_ids, "h"))
                # Vertical opening
                if first[3] < second[1]:
                    gap = second[1] - first[3]
                    thick1, thick2 = first[2] - first[0], second[2] - second[0]
                    first_is_horiz = thick1 > 1.8 * (first[3] - first[1]) and thick1 >= 10.0
                    second_is_horiz = thick2 > 1.8 * (second[2] - second[0]) and thick2 >= 10.0

                    if not first_is_horiz and not second_is_horiz:
                        alignment = abs((first[0] + first[2]) - (second[0] + second[2])) / 2
                        bounds = (max(first[0], second[0]), first[3], min(first[2], second[2]), second[1])
                        valid_geom = alignment <= 0.5 and abs(thick1 - thick2) <= 0.6
                    elif first_is_horiz and not second_is_horiz:
                        bounds = (second[0], first[3], second[2], second[1])
                        valid_geom = first[0] <= bounds[0] + 1.0 and first[2] >= bounds[2] - 1.0
                    elif not first_is_horiz and second_is_horiz:
                        bounds = (first[0], first[3], first[2], second[1])
                        valid_geom = second[0] <= bounds[0] + 1.0 and second[2] >= bounds[2] - 1.0
                    else:
                        valid_geom = False
                        bounds = (0.0, first[3], 0.0, second[1])

                    if (
                        valid_geom
                        and 2.0 <= gap <= 160.0
                        and bounds[1] - 2.0 <= ly <= bounds[3] + 2.0
                        and min(abs(lx - bounds[0]), abs(lx - bounds[2])) < 35
                    ):
                        label_margin = max(2.0, 0.15 * gap)
                        door_comp = [
                            raw for raw, w in door_labels
                            if bounds[1] + label_margin <= (w[1] + w[3]) / 2 <= bounds[3] - label_margin
                            and min(abs(w[0] - lx), abs(w[2] - lx)) < 35
                        ]
                        if not door_comp:
                            flines = [
                                fl for fl in frame_lines
                                if (not has_wall_layers or fl[1] == layer_i)
                                and bounds[1] - 2.5 <= min(fl[2][0][1], fl[2][1][1])
                                and max(fl[2][0][1], fl[2][1][1]) <= bounds[3] + 2.5
                                and bounds[0] - 1.5 <= (fl[2][0][0] + fl[2][1][0]) / 2 <= bounds[2] + 1.5
                            ]
                            if flines:
                                min_y = min(min(fl[2][0][1], fl[2][1][1]) for fl in flines)
                                max_y = max(max(fl[2][0][1], fl[2][1][1]) for fl in flines)
                                total_len = sum(math.dist(*fl[2]) for fl in flines)
                                if (
                                    abs(min_y - bounds[1]) < 3.0
                                    and abs(max_y - bounds[3]) < 3.0
                                    and total_len >= 0.7 * gap
                                ):
                                    marker_ids = tuple(sorted(dict.fromkeys(fl[0] for fl in flines)))[:4]
                                    cand_list.append((i, j, bounds, label_raw, marker_ids, "v"))

        unique_cands = {(c[0], c[1], c[2], c[3], c[4], c[5]) for c in cand_list}
        if unique_cands:
            ranked = sorted(
                unique_cands,
                key=lambda c: (
                    c[2][2] - c[2][0] if c[5] == "h" else c[2][3] - c[2][1],
                    c[0],
                    c[1],
                ),
            )
            best_gap = ranked[0][2][2] - ranked[0][2][0] if ranked[0][5] == "h" else ranked[0][2][3] - ranked[0][2][1]
            close = [
                c for c in ranked
                if (c[2][2] - c[2][0] if c[5] == "h" else c[2][3] - c[2][1]) <= best_gap + 0.5
            ]
            if len(close) == 1:
                i, j, bounds, label_str, marker_ids, ax = close[0]
                if (i, j) not in seen_hosts:
                    seen_hosts.add((i, j))
                    results.append(WindowFootprintBridge(
                        left_host_path_id=i, right_host_path_id=j,
                        marker_path_ids=marker_ids, label_text=label_str,
                        bounds_pdf_pts=bounds, axis=ax, page_index=page_index,
                    ))

    # Repeated schedule codes (ASW/ASW/…) are distinct openings. Only collapse
    # candidates that claim the same aperture span: overlapping host gap on the
    # same axis. A wider collinear rival behind the same mark still loses to the
    # tighter immediately-adjacent hosts.
    deduped: list[WindowFootprintBridge] = []
    for bridge in sorted(
        results,
        key=lambda r: (
            r.bounds_pdf_pts[2] - r.bounds_pdf_pts[0]
            if r.axis == "h"
            else r.bounds_pdf_pts[3] - r.bounds_pdf_pts[1]
        ),
    ):
        b = bridge.bounds_pdf_pts
        lbl = bridge.label_text.upper()
        rival = False
        for kept in deduped:
            if kept.label_text.upper() != lbl or kept.axis != bridge.axis:
                continue
            kb = kept.bounds_pdf_pts
            if bridge.axis == "h":
                overlap = min(b[2], kb[2]) - max(b[0], kb[0])
                band = abs((b[1] + b[3]) - (kb[1] + kb[3])) / 2
            else:
                overlap = min(b[3], kb[3]) - max(b[1], kb[1])
                band = abs((b[0] + b[2]) - (kb[0] + kb[2])) / 2
            if overlap > 0.5 and band <= 2.0:
                rival = True
                break
        if not rival:
            deduped.append(bridge)
    return tuple(sorted(deduped, key=lambda r: (r.page_index, r.left_host_path_id, r.right_host_path_id)))
