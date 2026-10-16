"""Read-only original-PDF coverage audit for a supplied F.07 viewport candidate.

Does not widen/elect viewports, authenticate material text, classify structural
walls, bind rooms or publish quantities. An out-of-box mark may be part of a
different view or schedule. Native line crossings have no physical role.
"""
from __future__ import annotations

import math
from typing import Any


def _bbox(values: object):
    try:
        if isinstance(values, (str, bytes)):
            return None
        a = tuple(float(v) for v in values)
    except (TypeError, ValueError, OverflowError):
        return None
    if len(a) != 4 or not all(math.isfinite(v) for v in a):
        return None
    if a[2] <= a[0] or a[3] <= a[1]:
        return None
    return a


def _line(item: object):
    try:
        if item[0] != "l":
            return None
        a, b = item[1:3]
        values = tuple(float(v) for v in (a.x, a.y, b.x, b.y))
    except (IndexError, AttributeError, TypeError, ValueError, OverflowError):
        return None
    return values if all(math.isfinite(v) for v in values) and values[:2] != values[2:] else None


def _position(source_bbox, bbox):
    if (bbox[0] >= source_bbox[0] and bbox[1] >= source_bbox[1]
            and bbox[2] <= source_bbox[2] and bbox[3] <= source_bbox[3]):
        return "fully_within_supplied_viewport"
    if (bbox[2] <= source_bbox[0] or bbox[0] >= source_bbox[2]
            or bbox[3] <= source_bbox[1] or bbox[1] >= source_bbox[3]):
        return "outside_supplied_viewport"
    return "straddles_supplied_viewport"


def _crossed_boundaries(pts, box):
    x0, y0, x1, y1 = pts
    xmin, ymin, xmax, ymax = box
    hits = []
    # Strict interior crossing, never a touching endpoint or close-by line.
    if x0 == x1 and y0 != y1 and xmin <= x0 <= xmax:
        if min(y0, y1) < ymin < max(y0, y1):
            hits.append("native_ymin")
        if min(y0, y1) < ymax < max(y0, y1):
            hits.append("native_ymax")
    if y0 == y1 and x0 != x1 and ymin <= y0 <= ymax:
        if min(x0, x1) < xmin < max(x0, x1):
            hits.append("native_xmin")
        if min(x0, x1) < xmax < max(x0, x1):
            hits.append("native_xmax")
    return hits


def audit_candidate_viewport_source_coverage(
    page: Any, *, viewport_bbox: object,
    raw_mark_tokens: tuple[str, ...] = (),
    max_native_segments: int = 120000,
):
    """Census all selected raw native words and bounded native line crossings.

    The *caller* supplies a candidate viewport; no viewport is inferred. Token
    filtering is lexical only: it keeps both in-plan marks and schedule/legend
    rivals. Not an alternative SourceMaterialSemanticProducer.
    """
    box = _bbox(viewport_bbox)
    if box is None:
        raise ValueError("invalid_supplied_candidate_viewport_bbox")
    if (not isinstance(raw_mark_tokens, tuple)
            or any(type(s) is not str or not s.strip() for s in raw_mark_tokens)):
        raise ValueError("explicit_raw_mark_tokens_required")
    if type(max_native_segments) is not int or max_native_segments < 1:
        raise ValueError("invalid_shadow_segment_cap")
    rows = []
    wanted = set(raw_mark_tokens)
    for word in page.get_text("words"):
        if len(word) < 8 or (wanted and word[4] not in wanted):
            continue
        original = _bbox(word[:4])
        if original is None:
            continue
        rows.append({
            "original_source_word_address": list(word[5:8]),
            "original_raw_literal_untrusted": str(word[4]),
            "source_word_bbox_pdf_pts": list(original),
            "candidate_location": _position(box, original),
            "source_material_occurrence_authenticated": False,
            "source_viewport_membership_proven": False,
        })
    rows.sort(key=lambda a: (tuple(a["original_source_word_address"]),
                             a["original_raw_literal_untrusted"],
                             tuple(a["source_word_bbox_pdf_pts"])))
    crossing = []
    count = 0
    for path_idx, drawing in enumerate(page.get_drawings()):
        for item_idx, item in enumerate(drawing.get("items", ())):
            pts = _line(item)
            if pts is None:
                continue
            count += 1
            if count > max_native_segments:
                return {
                    "status": "original_vector_scope_exceeds_shadow_cap",
                    "source_native_segments_visited": count,
                    "candidate_viewport_bbox_pdf_pts": list(box),
                    "raw_word_candidates": rows,
                    "source_crossing_primitive_candidates": [],
                    "source_crossing_universe_complete": False,
                    "view_authority_granted": False,
                    "material_occurrence_authority_granted": False,
                    "quantity_authority_granted": False,
                }
            sides = _crossed_boundaries(pts, box)
            if not sides:
                continue
            crossing.append({
                "original_source_primitive_id": f"d{path_idx}i{item_idx}",
                "native_segment_pdf_pts": list(pts),
                "candidate_crossed_bounds": sides,
                "source_stroke_color": drawing.get("color"),
                "source_stroke_width_pdf_pts": drawing.get("width"),
                "original_ink_role_authenticated": False,
                "proof_of_single_view_continuity": False,
            })
    crossing.sort(key=lambda r: r["original_source_primitive_id"])
    return {
        "status": "read_only_candidate_coverage_complete",
        "candidate_viewport_bbox_pdf_pts": list(box),
        "raw_word_candidates": rows,
        "raw_words_outside_count": sum(
            r["candidate_location"] == "outside_supplied_viewport" for r in rows
        ),
        "source_crossing_primitive_candidates": crossing,
        "source_native_segments_visited": count,
        "source_crossing_universe_complete": True,
        "view_authority_granted": False,
        "material_occurrence_authority_granted": False,
        "quantity_authority_granted": False,
        "candidate_not_physical_view_proof": True,
    }
