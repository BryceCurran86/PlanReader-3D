"""Typed evidence for white-filled panel walls (report only; CL-R04, MAX 7236084226).

Some walls are drawn as an opaque white strip between two lines of one ink. A
strip alone is not a wall: masks, equipment, table cells and boxes painted twice
look the same. Each distinct white rectangle a wall's thickness wide and at
least three times as long, drawn along both long sides, gets one record:

* paired faces: one ink draws both long sides; the line paths are kept;
* continuity: from each short end the strip, or a straight run of strips it
  continues into, must reach wall paint at a right angle (another such strip or
  a dark filled wall bar) or a dark bar in line with it;
* no text inside it (labelled boxes and door-tagged pieces abstain);
* not stacked: no white rectangle of the same length sits against one of its
  long sides (table rows);
* source identity: sha, page, fill path indices, face line path indices. No
  viewport is bound here (``viewport_id`` is None), so nothing distinguishes a
  plan from an elevation: binding a plan viewport comes before any use.

Nothing here counts as support, changes a face, publishes or measures.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pb_finish_face_wall_support_shadow import _ink_near, _paper_white
from pb_layered_wall_doorway_room_ring_shadow import (
    _DARK_FILL_THICK_MAX,
    _STROKE_PAIR_CLUSTER_PT,
    _STROKE_PAIR_THICK_MIN,
    _collect_dark_painted_source_wall_strips,
    _opaque,
)
from pb_migration_contracts import EvidenceResolutionStatus

PANEL_WALL_EVIDENCE_VERSION = "panel-wall-evidence-1.1.0"
REASON_CONTINUOUS = "paired_faces_continuous_both_ends"
REASON_OPEN_END = "one_end_open"
REASON_ISOLATED = "isolated_strip"
REASON_TEXT = "contains_text"
REASON_STACKED = "stacked_cells"
_EVERYWHERE = (-1e9, -1e9, 1e9, 1e9)
_TOL = _STROKE_PAIR_CLUSTER_PT

Rect = tuple[float, float, float, float]


def _horizontal(rect: Rect) -> bool:
    return rect[2] - rect[0] >= rect[3] - rect[1]


def _frame(rect: Rect, horizontal: bool) -> tuple[float, float, float, float]:
    """(along start, along end, across low, across high) of ``rect`` seen along a strip of this orientation."""
    x0, y0, x1, y1 = rect
    return (x0, x1, y0, y1) if horizontal else (y0, y1, x0, x1)


def _white_rects(drawings: Sequence[Any]) -> dict[Rect, tuple[int, ...]]:
    """Each distinct opaque white rectangle with the drawing indices that paint it."""
    found: dict[Rect, list[int]] = {}
    for index, row in enumerate(drawings):
        if not (isinstance(row, Mapping) and row.get("fill") is not None and _paper_white(row["fill"]) and _opaque(row)):
            continue
        for item in row.get("items") or ():
            if item[0] == "re":
                found.setdefault(tuple(round(float(v), 3) for v in tuple(item[1])), []).append(index)
    return {rect: tuple(sorted(set(paths))) for rect, paths in found.items()}


def _lines_and_fills(drawings: Sequence[Any]):
    """Wall-eligible ink lines with their drawing index, and the per-row fills for the dark bar collector."""
    inks: dict[tuple[float, ...], list[tuple[bool, float, float, float, int]]] = {}
    fills = []
    for index, row in enumerate(drawings):
        found, row_fills, _whites = _ink_near([row], _EVERYWHERE)
        fills.append(row_fills[0])
        for ink, lines in found.items():
            inks.setdefault(ink, []).extend((h, perp, a, b, index) for h, perp, a, b in lines)
    return dict(sorted(inks.items())), fills


def _paired_faces(inks: Mapping, horizontal: bool, low: float, high: float, start: float, end: float):
    """(ink, (low side line paths, high side line paths)) when one ink draws both long sides, or None."""
    for ink, lines in inks.items():
        faces = []
        for side in (low, high):
            spans = sorted((max(a, start), min(b, end), path) for h, perp, a, b, path in lines
                           if h == horizontal and abs(perp - side) <= _TOL and min(b, end) > max(a, start))
            total, reach = 0.0, start
            for a, b, _path in spans:
                total += max(0.0, b - max(a, reach))
                reach = max(reach, b)
            if total / (end - start) < 0.9:
                break
            faces.append(tuple(sorted({path for _a, _b, path in spans})))
        if len(faces) == 2:
            return ink, tuple(faces)
    return None


def _touches_end(strip: Rect, other: Rect, direction: int) -> bool:
    """``other`` runs at a right angle into the end square of ``strip`` (direction -1 start end, +1 far end)."""
    horizontal = _horizontal(strip)
    start, end, low, high = _frame(strip, horizontal)
    o_start, o_end, o_low, o_high = _frame(other, horizontal)
    thick = high - low
    near, far = (start - _TOL, start + thick) if direction < 0 else (end - thick, end + _TOL)
    return o_start <= far and o_end >= near and o_low <= high + _TOL and o_high >= low - _TOL


def _continues(strip: Rect, other: Rect, direction: int) -> bool:
    """``other`` lies in line with ``strip`` and carries it further past that end."""
    horizontal = _horizontal(strip)
    start, end, low, high = _frame(strip, horizontal)
    o_start, o_end, o_low, o_high = _frame(other, horizontal)
    if min(high, o_high) - max(low, o_low) < 0.5 * min(high - low, o_high - o_low):
        return False
    if direction < 0:
        return o_start < start - _TOL and o_end >= start - _TOL
    return o_end > end + _TOL and o_start <= end + _TOL


def _run_reaches_wall(first: int, direction: int, strips: Sequence[Rect], bars: Sequence[Rect]) -> bool:
    seen: set[int] = set()
    pending = [first]
    while pending:
        position = pending.pop()
        if position in seen:
            continue
        seen.add(position)
        strip = strips[position]
        across = _horizontal(strip)
        for i, other in enumerate(strips):
            if i != position and _horizontal(other) != across and _touches_end(strip, other, direction):
                return True
        for bar in bars:
            if (_horizontal(bar) != across and _touches_end(strip, bar, direction)) or (
                    _horizontal(bar) == across and _continues(strip, bar, direction)):
                return True
        pending += [i for i, other in enumerate(strips)
                    if i != position and _horizontal(other) == across and _continues(strip, other, direction)]
    return False


def _stacked(rect: Rect, whites: Sequence[Rect]) -> bool:
    """A white rectangle of the same length sits against one of the long sides: the shape of table rows."""
    horizontal = _horizontal(rect)
    start, end, low, high = _frame(rect, horizontal)
    for other in whites:
        o_start, o_end, o_low, o_high = _frame(other, horizontal)
        if other != rect and (abs(o_low - high) <= _TOL or abs(o_high - low) <= _TOL) and (
                abs(o_start - start) <= _TOL and abs(o_end - end) <= _TOL):
            return True
    return False


def typed_panel_walls(
    drawings: Sequence[Any], words: Sequence[Sequence[Any]], *, source_sha256: str, page_index: int,
) -> list[dict[str, Any]]:
    """One typed record per candidate strip, in a stable order. ``words`` are PyMuPDF word tuples (same frame)."""
    if type(source_sha256) is not str or len(source_sha256) != 64:
        raise ValueError("source_sha256 must be a 64-char digest")
    if type(page_index) is not int or page_index < 0:
        raise ValueError("page_index must be a non-negative int")
    inks, fills = _lines_and_fills(drawings)
    bars = [(s.x0, s.y0, s.x1, s.y1) for s in _collect_dark_painted_source_wall_strips(fills)]
    whites = _white_rects(drawings)
    strips: list[dict[str, Any]] = []
    for rect in sorted(whites):
        horizontal = _horizontal(rect)
        start, end, low, high = _frame(rect, horizontal)
        thick = high - low
        if not (_STROKE_PAIR_THICK_MIN <= thick <= _DARK_FILL_THICK_MAX and end - start >= 3.0 * thick):
            continue
        paired = _paired_faces(inks, horizontal, low, high, start + thick, end - thick)
        if paired is not None:
            strips.append({"rect": rect, "thickness": thick, "ink": paired[0], "faces": paired[1]})
    rects = [s["rect"] for s in strips]
    centres = [((float(w[0]) + float(w[2])) / 2.0, (float(w[1]) + float(w[3])) / 2.0) for w in words]
    records = []
    for position, strip in enumerate(strips):
        x0, y0, x1, y1 = strip["rect"]
        continuous = tuple(_run_reaches_wall(position, direction, rects, bars) for direction in (-1, 1))
        if any(x0 < x < x1 and y0 < y < y1 for x, y in centres):
            reason = REASON_TEXT
        elif _stacked(strip["rect"], tuple(whites)):
            reason = REASON_STACKED
        elif all(continuous):
            reason = REASON_CONTINUOUS
        else:
            reason = REASON_OPEN_END if any(continuous) else REASON_ISOLATED
        records.append({
            "status": EvidenceResolutionStatus.CANDIDATE if reason == REASON_CONTINUOUS
            else EvidenceResolutionStatus.ABSTAINED,
            "reason": reason, "rect_pdf_pts": strip["rect"], "thickness_pt": strip["thickness"],
            "face_ink": strip["ink"], "face_path_indices": strip["faces"],
            "fill_path_indices": whites[strip["rect"]], "ends_continuous": continuous,
            "source_sha256": source_sha256, "page_index": page_index, "viewport_id": None,
            "counts_as_support": False, "wall_authority": False, "version": PANEL_WALL_EVIDENCE_VERSION,
        })
    return records
