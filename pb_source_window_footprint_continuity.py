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

_WINDOW_CODE = re.compile(r"^(?:asw|aw|window|win|fgw|sgw)$", re.IGNORECASE)
_DOOR_CODE = re.compile(r"^(?:d[- ]?\d+[a-z]*|door|sgd|stacker)$", re.IGNORECASE)
_EXTERIOR_WALL_LAYER = re.compile(r"(?:wall.*extern|extern.*wall|wall.*exterior|exterior.*wall)", re.IGNORECASE)


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
        if len(nums) == 4 and all(math.isfinite(v) for v in nums):
            if nums[2] > nums[0] and nums[3] > nums[1]:
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
    walls: list[tuple[int, str, tuple[float, float, float, float]]] = []
    filled_rectangles: list[tuple[int, str, tuple[float, float, float, float]]] = []
    marker_lines: list[tuple[int, str, tuple[tuple[float, float], tuple[float, float]]]] = []
    for idx, row in enumerate(drawings):
        if not isinstance(row, Mapping):
            continue
        layer = str(row.get("layer") or "")
        if not _EXTERIOR_WALL_LAYER.search(layer):
            continue
        bounds = _rect(row)
        fill = row.get("fill")
        if bounds and isinstance(fill, (tuple, list)) and len(fill) >= 3:
            if max(float(v) for v in fill[:3]) < 0.3:
                filled_rectangles.append((idx, layer, bounds))
                dx, dy = bounds[2]-bounds[0], bounds[3]-bounds[1]
                if max(dx, dy) > 4*min(dx, dy) and min(dx, dy) >= 0.3:
                    walls.append((idx, layer, bounds))
        ln = _line(row)
        if ln and 0.5 <= math.dist(*ln) <= 16:
            marker_lines.append((idx, layer, ln))
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
                    if math.dist(first, other0) < .08 and .2 < math.dist(second, other1) < 3:
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
                        gap = second[0]-first[2]
                        thick1, thick2 = first[3]-first[1], second[3]-second[1]
                        alignment = abs((first[1]+first[3])-(second[1]+second[3]))/2
                        offset = min(abs(my-first[1]),abs(my-first[3]),abs(my-second[1]),abs(my-second[3]))
                        bounds = (first[2],max(first[1],second[1]),second[0],min(first[3],second[3]))
                    else:
                        if first[3] >= my or second[1] <= my:
                            continue
                        gap = second[1]-first[3]
                        thick1, thick2 = first[2]-first[0], second[2]-second[0]
                        alignment = abs((first[0]+first[2])-(second[0]+second[2]))/2
                        offset = min(abs(mx-first[0]),abs(mx-first[2]),abs(mx-second[0]),abs(mx-second[2]))
                        bounds = (max(first[0],second[0]),first[3],min(first[2],second[2]),second[1])
                    if not 2 <= gap <= 160 or alignment > 0.3 or abs(thick1-thick2) > 0.3:
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
                if isinstance(drawings[k], Mapping)
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
    return tuple(sorted(results, key=lambda r:(r.page_index,r.left_host_path_id,r.right_host_path_id)))
