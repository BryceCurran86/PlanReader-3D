"""Original-native cavity-slider threshold witnesses; source-owned, never billable.

A printed CS token alone is NOT a door. Each accepted aperture requires two
unique original black wall-end hosts, white source jamb return(s) at both
ends and one real native sliding-leaf stroke. Pocket framing stays WALL.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
import re
from typing import Any

_WALL = "Enclosure_WallInternal"
_WIDTH = re.compile(r"^(?:6\d\d|7\d\d|8\d\d|9\d\d|1,?[0-4]\d\d)$")


@dataclass(frozen=True)
class NativeCavitySliderThreshold:
    cs_word_index: int
    width_word_index: int
    printed_width_mm: int
    horizontal: bool
    band_pdf_pts: tuple[float, float]
    clear_interval_pdf_pts: tuple[float, float]
    host_path_ids: tuple[int, int]
    jamb_path_ids: tuple[int, ...]
    leaf_path_id: int
    page_index: int
    physical_opening_authenticated: bool = False
    customer_quantity_authorized: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": "source_native_cavity_slider_threshold",
            "cs_word_index": self.cs_word_index,
            "width_word_index": self.width_word_index,
            "printed_width_mm": self.printed_width_mm,
            "horizontal": self.horizontal,
            "band_pdf_pts": list(self.band_pdf_pts),
            "clear_interval_pdf_pts": list(self.clear_interval_pdf_pts),
            "host_path_ids": list(self.host_path_ids),
            "jamb_path_ids": list(self.jamb_path_ids),
            "leaf_path_id": self.leaf_path_id,
            "page_index": self.page_index,
            "physical_opening_authenticated": False,
            "customer_quantity_authorized": False,
        }


def _box(r):
    try:
        q = tuple(float(v) for v in r.get("rect", ()))
        return q if len(q) == 4 and all(map(math.isfinite, q)) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _filled(r, white):
    if not isinstance(r, Mapping) or r.get("layer") != _WALL or r.get("type") != "f":
        return False
    c = r.get("fill")
    return (
        isinstance(c, (tuple, list)) and len(c) >= 3
        and (
            all(isinstance(v, (int, float)) and math.isfinite(v) and v >= .98 for v in c[:3])
            if white else
            all(isinstance(v, (int, float)) and math.isfinite(v) and v <= .02 for v in c[:3])
        )
    )


def _line(r):
    if not isinstance(r, Mapping) or r.get("layer") != _WALL or r.get("type") != "s":
        return None
    if r.get("fill") is not None:
        return None
    color = r.get("color")
    if not (isinstance(color, (tuple, list)) and len(color) >= 3
            and all(isinstance(v, (int, float)) and math.isfinite(v)
                    and 0 <= v <= .02 for v in color[:3])):
        return None
    items = r.get("items") or ()
    if len(items) != 1 or items[0][0] != "l":
        return None
    try:
        a, b = items[0][1:3]
        xy = lambda p: (float(p.x), float(p.y)) if hasattr(p, "x") else (float(p[0]), float(p[1]))
        a, b = xy(a), xy(b)
        return (a, b) if all(map(math.isfinite, (*a, *b))) else None
    except (TypeError, ValueError, IndexError, OverflowError):
        return None


def _word(row):
    try:
        if isinstance(row, Mapping):
            q = tuple(float(v) for v in (row.get("bbox_pdf_pts") or row["bbox"]))
            token = str(row["text"]).upper()
        else:
            q = tuple(float(v) for v in row[:4])
            token = str(row[4]).upper()
        if len(q) != 4 or not all(map(math.isfinite, q)) or q[0] > q[2] or q[1] > q[3]:
            return None
        return (q, token)
    except (ValueError, TypeError, KeyError, IndexError, OverflowError):
        return None


def _candidates(drawings, centre, width_mm, page_index, cs_index, width_index):
    dark = [(i, _box(r)) for i, r in enumerate(drawings) if _filled(r, False)]
    white = [(i, _box(r)) for i, r in enumerate(drawings) if _filled(r, True)]
    strokes = [(i, line) for i, r in enumerate(drawings)
               if (line := _line(r)) is not None]
    dark = [(i, b) for i, b in dark if b is not None]
    white = [(i, b) for i, b in white if b is not None]
    matches = []
    for horizontal in (True, False):
        def coords(b):
            return (b[0], b[2], b[1], b[3]) if horizontal else (b[1], b[3], b[0], b[2])
        nearby = []
        for i, b in dark:
            lo, hi, p0, p1 = coords(b)
            if not .65 <= p1 - p0 <= 4 or hi - lo < .6:
                continue
            if abs((lo + hi) / 2 - centre[not horizontal]) > 65:
                continue
            if abs((p0 + p1) / 2 - centre[horizontal]) > 25:
                continue
            nearby.append((i, lo, hi, p0, p1))
        for left in nearby:
            for right in nearby:
                if left[0] == right[0]:
                    continue
                low, high = left[2], right[1]
                span = high - low
                if not 14 <= span <= 52 or not .021 * width_mm <= span <= .043 * width_mm:
                    continue
                band = (max(left[3], right[3]), min(left[4], right[4]))
                if band[1] - band[0] < .65 * min(left[4] - left[3], right[4] - right[3]):
                    continue
                mid, cy = (low + high) / 2, (band[0] + band[1]) / 2
                xy = (mid, cy) if horizontal else (cy, mid)
                distance = math.hypot(xy[0] - centre[0], xy[1] - centre[1])
                if distance > 30:
                    continue
                endcaps = []
                for end in (low, high):
                    caps = []
                    for cap_id, b in white:
                        a, z, p0, p1 = coords(b)
                        if min(p1, band[1]) - max(p0, band[0]) < .25:
                            continue
                        if min(abs(a - end), abs(z - end)) <= .35 and z - a <= 3.5:
                            caps.append(cap_id)
                    if not 1 <= len(caps) <= 2:
                        break
                    endcaps.append(caps)
                if len(endcaps) != 2 or set(endcaps[0]) & set(endcaps[1]):
                    continue
                blocked = False
                for wall_id, b in dark:
                    if wall_id in (left[0], right[0]):
                        continue
                    a, z, p0, p1 = coords(b)
                    if (min(z, high - .5) - max(a, low + .5) > 1.0
                            and min(p1, band[1]) - max(p0, band[0]) > .6 * (band[1] - band[0])):
                        blocked = True
                        break
                if blocked:
                    continue
                leaves = []
                for leaf_id, line in strokes:
                    (x0, y0), (x1, y1) = line
                    a, z, p0, p1 = (x0, x1, y0, y1) if horizontal else (y0, y1, x0, x1)
                    if abs(p1 - p0) > .13 or abs((p0 + p1) / 2 - cy) > .14:
                        continue
                    overlap = max(0., min(max(a, z), high) - max(min(a, z), low))
                    if .35 * span <= overlap and .45 * span <= abs(z - a) <= 1.5 * span:
                        leaves.append(leaf_id)
                if len(leaves) != 1:
                    continue
                rec = NativeCavitySliderThreshold(
                    cs_index, width_index, width_mm, horizontal, band,
                    (low, high), (left[0], right[0]),
                    tuple(sorted(endcaps[0] + endcaps[1])),
                    leaves[0], page_index,
                )
                matches.append((distance, rec))
    return sorted(matches, key=lambda t: t[0])


def match_source_native_cavity_sliders(
    drawings: Sequence[Mapping[str, Any]],
    words: Sequence[Sequence[Any] | Mapping[str, Any]],
    *,
    page_index: int,
) -> tuple[NativeCavitySliderThreshold, ...]:
    """Return unique source-supported clear openings; not physical quantities."""
    if type(page_index) is not int or page_index < 0:
        raise ValueError("page_index must identify the original page")
    parsed = [_word(w) for w in words]
    proposals = []
    for cs_index, entry in enumerate(parsed):
        if entry is None or entry[1] != "CS":
            continue
        b = entry[0]
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        nearby = []
        for wi, w in enumerate(parsed):
            if w is None or not _WIDTH.fullmatch(w[1]):
                continue
            bw = w[0]
            wx, wy = (bw[0] + bw[2]) / 2, (bw[1] + bw[3]) / 2
            dist = math.hypot(wx - cx, wy - cy)
            if dist <= 17:
                nearby.append((dist, wi, int(w[1].replace(",", ""))))
        nearby.sort()
        if not nearby or (len(nearby) > 1 and nearby[1][0] - nearby[0][0] <= 1.):
            continue
        _, wi, mm = nearby[0]
        candidates = _candidates(drawings, (cx, cy), mm, page_index, cs_index, wi)
        if not candidates or (len(candidates) > 1 and candidates[1][0] - candidates[0][0] < 2.5):
            continue
        proposals.append(candidates[0][1])
    uses = {}
    for rec in proposals:
        for idx in (*rec.host_path_ids, *rec.jamb_path_ids, rec.leaf_path_id):
            uses[idx] = uses.get(idx, 0) + 1
    return tuple(r for r in proposals if all(
        uses[idx] == 1 for idx in (*r.host_path_ids, *r.jamb_path_ids, r.leaf_path_id)
    ))
