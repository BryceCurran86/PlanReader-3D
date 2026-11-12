"""Fail-closed, source-native height evidence from section FFL/FCL and RCP callouts.

Height evidence is not itself a room/ceiling-zone association, a finished wall
lining measurement, or a publication authority.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Sequence
import math
import re

from .engine import NativePage, NativeWord, NativeSegment, SourceConflict, _figured_mm

SECTION_FFL_FCL = "ffl_to_fcl_section"
RCP_MATERIAL_HEIGHT = "rcp_material_height_callout"
_RCP_MATERIAL = re.compile(r"(?:IPF\d{1,2}|GRID|FPB|WFPB|WPB|CLD|CL0[1-9]|IP)", re.I)


def _middle(word: NativeWord) -> tuple[float, float]:
    x0, y0, x1, y1 = word.bbox
    return (x0 + x1) / 2, (y0 + y1) / 2


def _maybe_height(word: NativeWord) -> Decimal | None:
    try:
        value = _figured_mm(word)
    except SourceConflict:
        return None
    return value if Decimal(1500) <= value <= Decimal(6000) else None


def _inside(word: NativeWord, viewport: Sequence[float] | None) -> bool:
    if viewport is None:
        return True
    if len(viewport) != 4 or any(
        type(value) not in (int, float) or not math.isfinite(value)
        for value in viewport
    ):
        raise SourceConflict("height_viewport_invalid")
    x0, y0, x1, y1 = viewport
    if x0 >= x1 or y0 >= y1:
        raise SourceConflict("height_viewport_invalid")
    return (x0 <= word.bbox[0] and word.bbox[2] <= x1
            and y0 <= word.bbox[1] and word.bbox[3] <= y1)


def _source_text_line(word: NativeWord) -> tuple[str, int] | None:
    # PyMuPDF source word refs are generated from a real text block/line.
    # A close-by figure on a different annotation line is NOT the same
    # height/material bubble (e.g. 1980 mm PWD equipment near IPF1).
    match = re.fullmatch(r"word:(b[0-9]+):l([0-9]+):w[0-9]+:i[0-9]+",word.ref)
    return (match.group(1), int(match.group(2))) if match else None


def _receipt(
    page: NativePage, kind: str, height: NativeWord, *,
    witness_word_refs: Sequence[str],
    dimension_segment_refs: Sequence[str] = (),
    material: NativeWord | None = None,
) -> dict[str, Any]:
    return {
        "source_sha256": page.source_sha256, "page_index": page.page_index,
        "height_source_kind": kind, "height_word_ref": height.ref,
        "height_mm": format(_figured_mm(height).normalize(), "f"),
        "witness_word_refs": list(witness_word_refs),
        "dimension_segment_refs": list(dimension_segment_refs),
        "material_word_ref": material.ref if material is not None else None,
        "material_code_candidate": material.text.strip().upper() if material else None,
        "status": "SOURCE_HEIGHT_EVIDENCE_REVIEW_REQUIRED",
        "wall_or_room_scope_authenticated": False,
        "ceiling_zone_authenticated": False,
        "height_to_internal_finish_authenticated": False,
        "commercial_publishable": False, "benchmark_credit": False,
    }


def section_ffl_fcl_heights(page: NativePage) -> list[dict[str, Any]]:
    """Require exact source vertical dimension ink whose ends have FCL/FFL text."""
    ffl = [word for word in page.words if word.text.strip().upper() == "FFL"]
    fcl = [word for word in page.words if word.text.strip().upper() == "FCL"]
    if not (ffl and fcl):
        return []
    vertical = [
        segment for segment in page.segments
        if segment.kind in ("line", "rect_edge")
        and abs(segment.x1 - segment.x2) <= .35
        and abs(segment.y1 - segment.y2) >= 55
    ]
    result: list[dict[str, Any]] = []
    for word in page.words:
        if _maybe_height(word) is None:
            continue
        wx, wy = _middle(word)
        witnesses: set[tuple[str, str, str]] = set()
        for line in vertical:
            lx = (line.x1 + line.x2) / 2
            lo, hi = sorted((line.y1, line.y2))
            if abs(wx - lx) > 9 or not lo + 5 < wy < hi - 5:
                continue
            low_labels = [
                a for a in ffl if abs(_middle(a)[0] - lx) <= 24
                and abs(_middle(a)[1] - hi) <= 13
            ]
            high_labels = [
                b for b in fcl if abs(_middle(b)[0] - lx) <= 24
                and abs(_middle(b)[1] - lo) <= 13
            ]
            for low in low_labels:
                for high in high_labels:
                    if _middle(high)[1] < wy < _middle(low)[1]:
                        witnesses.add((low.ref, high.ref, line.ref))
        if len(witnesses) == 1:
            low_ref, high_ref, dimension_line_ref = next(iter(witnesses))
            result.append(_receipt(
                page, SECTION_FFL_FCL, word,
                witness_word_refs=(low_ref, high_ref),
                dimension_segment_refs=(dimension_line_ref,),
            ))
    return result


def rcp_material_height_callouts(
    page: NativePage, *, viewport_pdf_pts: Sequence[float] | None = None,
) -> list[dict[str, Any]]:
    """Pair one source height with one material inside an oriented RCP callout.

    Word adjacency is a candidate, not proof of a single physical ceiling zone.
    Legend examples may also be candidates. A reviewed RCP-zone scope is
    required later, and the source PDF rotation is already in native coords.
    """
    materials = [
        word for word in page.words
        if _RCP_MATERIAL.fullmatch(word.text.strip()) and _inside(word, viewport_pdf_pts)
    ]
    heights = [
        word for word in page.words
        if _maybe_height(word) is not None and _inside(word, viewport_pdf_pts)
    ]
    proposed: dict[str, list[NativeWord]] = {}
    reverse: dict[str, list[str]] = {}
    for height in heights:
        hx, hy = _middle(height)
        matches: list[NativeWord] = []
        for material in materials:
            mx, my = _middle(material)
            # Native 90-degree rotated RCP: parallel text in adjacent columns.
            rotated_pair = 7 <= hx - mx <= 30 and abs(hy - my) <= 6
            # Unrotated RCP: numeric height directly under a material code.
            unrotated_pair = 7 <= hy - my <= 30 and abs(hx - mx) <= 6
            source_height = _source_text_line(height)
            source_material = _source_text_line(material)
            same_callout_lines = (
                source_height is not None and source_material is not None
                and source_height[0] == source_material[0]
                and abs(source_height[1] - source_material[1]) == 1
            )
            if same_callout_lines and (rotated_pair or unrotated_pair):
                matches.append(material)
                reverse.setdefault(material.ref, []).append(height.ref)
        proposed[height.ref] = matches
    return [
        _receipt(page, RCP_MATERIAL_HEIGHT, height,
                 witness_word_refs=(proposed[height.ref][0].ref,),
                 material=proposed[height.ref][0])
        for height in heights
        if len(proposed[height.ref]) == 1
        and len(reverse[proposed[height.ref][0].ref]) == 1
    ]


def height_evidence_inventory(
    page: NativePage, *, rcp_viewport_pdf_pts: Sequence[float] | None = None,
) -> dict[str, Any]:
    return {
        "source_sha256": page.source_sha256, "page_index": page.page_index,
        "section_ffl_fcl": section_ffl_fcl_heights(page),
        "rcp_material_callouts": rcp_material_height_callouts(
            page, viewport_pdf_pts=rcp_viewport_pdf_pts,
        ),
        "commercial_publishable": False, "benchmark_credit": False,
        "official_score": None,
    }


def validate_height_receipt(
    page: NativePage, claim: dict[str, Any], *,
    rcp_viewport_pdf_pts: Sequence[float] | None = None,
) -> dict[str, Any]:
    """Reconstruct claimant's chosen height from original native source refs."""
    if not isinstance(claim, dict) or (
        claim.get("source_sha256") != page.source_sha256
        or claim.get("page_index") != page.page_index
    ):
        raise SourceConflict("height_receipt_source_mismatch")
    kind = claim.get("height_source_kind")
    if kind == SECTION_FFL_FCL:
        choices = section_ffl_fcl_heights(page)
    elif kind == RCP_MATERIAL_HEIGHT:
        choices = rcp_material_height_callouts(
            page, viewport_pdf_pts=rcp_viewport_pdf_pts,
        )
    else:
        raise SourceConflict("height_source_kind_invalid")
    selected = [
        receipt for receipt in choices
        if all(receipt[field] == claim.get(field) for field in (
            "source_sha256", "page_index", "height_source_kind",
            "height_word_ref", "witness_word_refs",
            "dimension_segment_refs", "material_word_ref",
        ))
    ]
    if len(selected) != 1:
        raise SourceConflict("height_receipt_not_uniquely_source_owned")
    if "height_mm" in claim and claim["height_mm"] != selected[0]["height_mm"]:
        raise SourceConflict("height_receipt_value_mismatch")
    return selected[0]
