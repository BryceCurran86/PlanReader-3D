"""Pair a unique printed figure to its hosted opening, never to the host wall.

A millimetre drawn inside a door swing, cavity-slider pocket or the opening's
own dimension chain belongs to that opening. The same figure must not also be
used as a wall length. Ambiguous containment or conflicting millimetres abstain.
This is not a schedule width, FIRM quantity or customer row.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Sequence

from .dimension_index import STATUS_UNIQUE, inventory_page_dimensions
from collections import defaultdict

from .engine import NativePage, NativeWord, SourceConflict, _figured_mm
from .hash_chain import _FACE_PT

_SWING_KIND = "swing_doorway"
_LABEL_PAD_PT = 8.0


def _center(bbox: Sequence[float]) -> tuple[float, float]:
    return (bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0


def _inside(point: tuple[float, float], box: Sequence[float]) -> bool:
    x0, y0, x1, y1 = box
    lo_x, hi_x = sorted((x0, x1))
    lo_y, hi_y = sorted((y0, y1))
    return lo_x - _FACE_PT <= point[0] <= hi_x + _FACE_PT and (
        lo_y - _FACE_PT <= point[1] <= hi_y + _FACE_PT
    )


def _search_box(fill: dict[str, Any]) -> tuple[float, float, float, float] | None:
    """Wall-gap band plus the typical 90-degree swing/pocket square.

    Expand only in the thin (through-wall) direction by the gap length, so a
    figure inside the swing can pair without swallowing a neighbouring wall
    dimension along the host.
    """
    box = fill.get("bbox_pdf_pts") or []
    if len(box) != 4:
        return None
    x0, y0, x1, y1 = (float(value) for value in box)
    width, height = abs(x1 - x0), abs(y1 - y0)
    if width <= _FACE_PT and height <= _FACE_PT:
        return None
    thickness, gap = min(width, height), max(width, height)
    kind = str(fill.get("kind") or "")
    pad = gap if kind == _SWING_KIND else max(_LABEL_PAD_PT, thickness * 3.0)
    if width <= height:
        return (min(x0, x1) - pad, min(y0, y1), max(x0, x1) + pad, max(y0, y1))
    return (min(x0, x1), min(y0, y1) - pad, max(x0, x1), max(y0, y1) + pad)


def _gap_length(fill: dict[str, Any]) -> float | None:
    box = fill.get("bbox_pdf_pts") or []
    if len(box) != 4:
        return None
    x0, y0, x1, y1 = (float(value) for value in box)
    width, height = abs(x1 - x0), abs(y1 - y0)
    span = max(width, height)
    return span if span > _FACE_PT else None


def _figured_word(page: NativePage, ref: str) -> tuple[NativeWord, Decimal] | None:
    word = next((item for item in page.words if item.ref == ref), None)
    if word is None:
        return None
    try:
        millimetres = _figured_mm(word)
    except SourceConflict:
        return None
    if millimetres == 0:
        return None
    return word, millimetres


def _wall_length_not_opening(figure: Any, fill: dict[str, Any]) -> bool:
    """A unique dim-line much longer than the gap is the host wall, not the leaf."""
    if figure.geometry_status != STATUS_UNIQUE or figure.endpoint_stations is None:
        return False
    gap = _gap_length(fill)
    if gap is None:
        return False
    span = abs(figure.endpoint_stations[1] - figure.endpoint_stations[0])
    return span > gap * 1.5 + _FACE_PT


def pair_opening_figures(
    page: NativePage, fills: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach unique millimetre words to unique openings, or abstain."""
    index = inventory_page_dimensions(page)
    figures = {item.word_ref: item for item in index.figures}
    boxes = [(fill, _search_box(fill)) for fill in fills]
    claims: dict[str, list[tuple[str, Decimal]]] = {
        fill["closure_id"]: [] for fill, _box in boxes
    }
    for fill, box in boxes:
        claimed = claims[fill["closure_id"]]
        for ref in fill.get("native_opening_word_refs") or []:
            found = _figured_word(page, ref)
            if found is None:
                continue
            claimed.append((found[0].ref, found[1]))
        if box is None:
            continue
        for figure in index.figures:
            if _wall_length_not_opening(figure, fill):
                continue
            if not _inside(_center(figure.bbox), box):
                continue
            owners = [
                other
                for other, other_box in boxes
                if other_box is not None
                and _inside(_center(figure.bbox), other_box)
                and not _wall_length_not_opening(figure, other)
            ]
            if len(owners) != 1 or owners[0]["closure_id"] != fill["closure_id"]:
                continue
            claimed.append((figure.word_ref, figure.millimetres))
    owners: dict[str, set[str]] = defaultdict(set)
    for closure_id, claimed in claims.items():
        for ref, _mm in claimed:
            owners[ref].add(closure_id)
    shared = {ref for ref, closure_ids in owners.items() if len(closure_ids) > 1}
    pairs: list[dict[str, Any]] = []
    for fill, _box in boxes:
        claimed = [
            (ref, millimetres)
            for ref, millimetres in claims[fill["closure_id"]]
            if ref not in shared
        ]
        unique_refs = list(dict.fromkeys(ref for ref, _mm in claimed))
        millimetres = {mm for _ref, mm in claimed}
        payload = {
            "closure_id": fill["closure_id"],
            "paired_figure_word_refs": [],
            "paired_length_mm": None,
            "paired_dimension_line_refs": [],
            "pair_status": "NONE",
            "pair_reason": "no_unique_opening_figure",
            "opening_width_is_not_wall_length": True,
            "host_wall_authenticated": False,
            "physical_opening_authenticated": False,
            "commercial_publishable": False,
        }
        if not unique_refs:
            pairs.append(payload)
            continue
        if len(millimetres) != 1:
            payload["pair_status"] = "ABSTAIN"
            payload["pair_reason"] = "conflicting_figures_in_opening"
            payload["paired_figure_word_refs"] = unique_refs
            pairs.append(payload)
            continue
        millimetre = next(iter(millimetres))
        line_refs = []
        for ref in unique_refs:
            item = figures.get(ref)
            if item is not None:
                line_refs.extend(item.dimension_line_refs)
        payload["pair_status"] = "UNIQUE"
        payload["pair_reason"] = "unique_figure_owns_opening_not_host_wall"
        payload["paired_figure_word_refs"] = unique_refs
        payload["paired_length_mm"] = format(millimetre.normalize(), "f")
        payload["paired_dimension_line_refs"] = list(dict.fromkeys(line_refs))
        pairs.append(payload)
    return pairs
