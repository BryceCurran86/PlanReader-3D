"""Source-owned exterior garage door continuity in a 2D footprint only.

Physical wall, frame, garage door, area and customer evidence remain separate.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pb_source_window_footprint_continuity import _rect

_EXTERIOR_WALL = re.compile(
    r"(?:wall.*extern|extern.*wall|wall.*exterior|exterior.*wall)", re.IGNORECASE
)
_GARAGE_TOKENS = frozenset(("panel", "lift", "door"))


@dataclass(frozen=True)
class GarageDoorFootprintBridge:
    start_host_path_id: int
    end_host_path_id: int
    jamb_cap_path_ids: tuple[int, int]
    bounds_pdf_pts: tuple[float, float, float, float]
    native_label_words: tuple[str, ...]
    axis: str
    page_index: int
    physical_wall_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": "source_garage_panel_lift_footprint_continuity_only",
            "start_host_path_id": self.start_host_path_id,
            "end_host_path_id": self.end_host_path_id,
            "jamb_cap_path_ids": list(self.jamb_cap_path_ids),
            "bounds_pdf_pts": list(self.bounds_pdf_pts),
            "native_label_words": list(self.native_label_words),
            "axis": self.axis,
            "page_index": self.page_index,
            "physical_wall_authenticated": False,
            "measurement_authorized": False,
        }


def _words(
    source_words: Sequence[Any],
) -> list[tuple[str, tuple[float, float, float, float]]]:
    out = []
    for row in source_words:
        try:
            if isinstance(row, Mapping):
                text, bounds = (
                    str(row["text"]),
                    tuple(float(v) for v in row["bbox_pdf_pts"]),
                )
            else:
                text, bounds = str(row[4]), tuple(float(v) for v in row[:4])
            if len(bounds) == 4 and all(math.isfinite(v) for v in bounds):
                out.append((text.strip().casefold(), bounds))
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return out


def detect_exterior_garage_door_footprint_bridges(
    drawings: Sequence[Mapping[str, Any] | object],
    source_words: Sequence[Any],
    *,
    page_index: int = -1,
) -> tuple[GarageDoorFootprintBridge, ...]:
    """A printed panel-lift door and two native anchored caps prove *topology*.

    Never infer wall material. No shortest-distance join, sheet label alone,
    or unhosted roller shutter can authorize a closed exterior footprint.
    """
    words = _words(source_words)
    if not _GARAGE_TOKENS.issubset({text for text, _ in words}):
        return ()
    faces: list[tuple[int, str, tuple[float, float, float, float]]] = []
    caps: list[tuple[int, str, tuple[float, float, float, float]]] = []
    for idx, item in enumerate(drawings):
        if not isinstance(item, Mapping):
            continue
        layer = str(item.get("layer") or "")
        if not _EXTERIOR_WALL.search(layer):
            continue
        rect = _rect(item)
        fill = item.get("fill")
        if rect is None or not isinstance(fill, (tuple, list)) or len(fill) < 3:
            continue
        tone = max(float(v) for v in fill[:3])
        width, height = rect[2] - rect[0], rect[3] - rect[1]
        # Grey source-painted jamb caps are genuine source ink; the
        # main wall bodies themselves must still be dark structural fill.
        if (
            tone < 0.3
            and min(width, height) >= 0.25
            and max(width, height) / min(width, height) > 4
        ):
            faces.append((idx, layer, rect))
        if tone < 0.65 and 0.2 <= min(width, height) <= 3:
            caps.append((idx, layer, rect))

    results: list[GarageDoorFootprintBridge] = []
    for a, layer, first in faces:
        for b, other_layer, second in faces:
            if a == b or layer != other_layer:
                continue
            # Orthogonal edges: only unique source-owned continuation
            # from two same-thickness, coplanar external wall faces.
            for axis in ("v", "h"):
                if axis == "v":
                    thick_a, thick_b = first[2] - first[0], second[2] - second[0]
                    if first[3] >= second[1]:
                        continue
                    gap = second[1] - first[3]
                    cross_delta = (
                        abs((first[0] + first[2]) - (second[0] + second[2])) / 2
                    )
                    bounds = (
                        max(first[0], second[0]),
                        first[3],
                        min(first[2], second[2]),
                        second[1],
                    )
                    mid = (bounds[0] + bounds[2]) / 2
                else:
                    thick_a, thick_b = first[3] - first[1], second[3] - second[1]
                    if first[2] >= second[0]:
                        continue
                    gap = second[0] - first[2]
                    cross_delta = (
                        abs((first[1] + first[3]) - (second[1] + second[3])) / 2
                    )
                    bounds = (
                        first[2],
                        max(first[1], second[1]),
                        second[0],
                        min(first[3], second[3]),
                    )
                    mid = (bounds[1] + bounds[3]) / 2
                if not (
                    15 < gap < 210
                    and 0.6 <= min(thick_a, thick_b) <= 9
                    and abs(thick_a - thick_b) < 0.4
                    and cross_delta < 0.35
                    and bounds[0] < bounds[2]
                    and bounds[1] < bounds[3]
                ):
                    continue
                margin = max(3, 2 * max(thick_a, thick_b))
                witnesses = {}
                for token, word in words:
                    if token not in _GARAGE_TOKENS:
                        continue
                    wx, wy = (word[0] + word[2]) / 2, (word[1] + word[3]) / 2
                    if axis == "v":
                        close = abs(wx - mid) < margin and bounds[1] <= wy <= bounds[3]
                    else:
                        close = abs(wy - mid) < margin and bounds[0] <= wx <= bounds[2]
                    if close:
                        witnesses.setdefault(token, []).append((wx, wy))
                if set(witnesses) != _GARAGE_TOKENS or any(
                    len(v) != 1 for v in witnesses.values()
                ):
                    continue

                # One source-painted transverse jamb cap at EACH endpoint,
                # separate from the two wall hosts. No geometrical guess.
                cap_by_end = []
                for edge in (
                    first[3] if axis == "v" else first[2],
                    second[1] if axis == "v" else second[0],
                ):
                    matches = []
                    for c, clayer, rect in caps:
                        if c in (a, b) or clayer != layer:
                            continue
                        if axis == "v":
                            cross = rect[2] - rect[0]
                            cap_along = rect[3] - rect[1]
                            centered = abs((rect[0] + rect[2]) / 2 - mid) < margin
                            anchored = rect[1] - 0.15 <= edge <= rect[3] + 0.15
                        else:
                            cross = rect[3] - rect[1]
                            cap_along = rect[2] - rect[0]
                            centered = abs((rect[1] + rect[3]) / 2 - mid) < margin
                            anchored = rect[0] - 0.15 <= edge <= rect[2] + 0.15
                        if (
                            anchored
                            and centered
                            and cross >= min(thick_a, thick_b)
                            and cap_along <= max(1.2, 0.8 * thick_a)
                        ):
                            matches.append(c)
                    cap_by_end.append(sorted(set(matches)))
                if len(cap_by_end[0]) != 1 or len(cap_by_end[1]) != 1:
                    continue
                if cap_by_end[0][0] == cap_by_end[1][0]:
                    continue
                # An unexpected third full-thickness wall bar within this
                # span means the host pair is not the physical door opening.
                competing = False
                for c, clayer, rect in faces:
                    if c in (a, b) or clayer != layer:
                        continue
                    if axis == "v":
                        overlap = min(bounds[3], rect[3]) - max(bounds[1], rect[1])
                        centered = abs((rect[0] + rect[2]) / 2 - mid) < 0.5
                        thick = rect[2] - rect[0]
                    else:
                        overlap = min(bounds[2], rect[2]) - max(bounds[0], rect[0])
                        centered = abs((rect[1] + rect[3]) / 2 - mid) < 0.5
                        thick = rect[3] - rect[1]
                    if overlap > 1 and centered and thick > 0.8 * min(thick_a, thick_b):
                        competing = True
                        break
                if competing:
                    continue
                results.append(
                    GarageDoorFootprintBridge(
                        start_host_path_id=a,
                        end_host_path_id=b,
                        jamb_cap_path_ids=(cap_by_end[0][0], cap_by_end[1][0]),
                        bounds_pdf_pts=bounds,
                        native_label_words=("panel", "lift", "door"),
                        axis=axis,
                        page_index=page_index,
                    )
                )
    # Ambiguous host chains must abstain rather than choose a longer door.
    unique = {(b.start_host_path_id, b.end_host_path_id): b for b in results}
    if len(unique) > 1:
        # One label group cannot authorize multiple overlapping door spans.
        # Multiple legitimate garage doors need separately scoped label groups.
        return ()
    return tuple(unique.values())
