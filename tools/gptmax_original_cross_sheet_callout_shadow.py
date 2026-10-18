"""Opt-in exact native callout correspondence across immutable source sheets.

A repeated printed callout is an explicit source reference, NOT physical
opening equivalence, structural-host authority, dimensions, count or FIRM.
No nearest, first, label similarity, or guessed viewport is used.
"""
from __future__ import annotations

from hashlib import sha256
from math import isfinite
from pathlib import Path

import fitz


def _exact_spans(page, value: str) -> list[tuple[float, float, float, float]]:
    found = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", ()):
            for span in line.get("spans", ()):
                if span.get("text") == value:
                    found.append(tuple(span["bbox"]))
    return found


def original_cross_sheet_callout_shadow(
    pdf_path: str | Path, *, expected_sha256: str,
    plan_page_index: int, elevation_page_index: int,
    plan_sheet_title: str, elevation_sheet_title: str,
    plan_title_bbox: tuple[float, float, float, float],
    elevation_title_bbox: tuple[float, float, float, float],
    exact_callout: str,
) -> dict:
    """Authenticate one exact native text span on each of two named sheets.

    Explicit title-block bounding boxes must be supplied and authenticated.
    Even a unique pair does not prove a canonical physical-opening identity.
    """
    if (not isinstance(expected_sha256, str) or len(expected_sha256) != 64
            or any(c not in "0123456789abcdef" for c in expected_sha256)
            or type(plan_page_index) is not int or type(elevation_page_index) is not int
            or plan_page_index == elevation_page_index
            or min(plan_page_index, elevation_page_index) < 0
            or not all(isinstance(v, str) and v.strip() and v == v.strip()
                       for v in (plan_sheet_title, elevation_sheet_title, exact_callout))):
        raise ValueError("invalid source-owned cross-sheet callout request")
    for bbox in (plan_title_bbox, elevation_title_bbox):
        if (not isinstance(bbox, (list, tuple)) or len(bbox) != 4
                or not all(type(v) in (int, float) and isfinite(v) for v in bbox)
                or not bbox[0] < bbox[2] or not bbox[1] < bbox[3]):
            raise ValueError("invalid explicit title-block bbox")
    source = Path(pdf_path).read_bytes()
    if sha256(source).hexdigest() != expected_sha256:
        raise ValueError("immutable original PDF SHA mismatch")
    with fitz.open(stream=source, filetype="pdf") as doc:
        if max(plan_page_index, elevation_page_index) >= len(doc):
            raise ValueError("requested source page absent")
        pages = (doc[plan_page_index], doc[elevation_page_index])
        roles = ((plan_sheet_title, plan_title_bbox),
                 (elevation_sheet_title, elevation_title_bbox))
        for page, (title, title_bbox) in zip(pages, roles):
            titles = _exact_spans(page, title)
            if len(titles) != 1 or not fitz.Rect(title_bbox).contains(fitz.Rect(titles[0])):
                raise ValueError("original source sheet-title ownership unproven")
        callouts = [_exact_spans(page, exact_callout) for page in pages]
        base = dict(source_sha256=expected_sha256,
                    source_pages=(plan_page_index, elevation_page_index),
                    callout_occurrence_counts=tuple(map(len, callouts)),
                    same_physical_opening="ABSTAIN", canonical_host="ABSTAIN",
                    opening_frame="ABSTAIN", opening_area="ABSTAIN",
                    opening_count="ABSTAIN", new_firm_quantity=False)
        if any(len(matches) != 1 for matches in callouts):
            return dict(base, status="ABSTAIN_NONUNIQUE_OR_MISSING_EXACT_CALLOUT")
        return dict(base, status="EXACT_NATIVE_CALLOUT_CORRESPONDENCE_ONLY",
                    sheet_titles=(plan_sheet_title, elevation_sheet_title),
                    exact_source_callout=exact_callout,
                    source_callout_bboxes=(callouts[0][0], callouts[1][0]))
