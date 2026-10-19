"""Untrusted original native finish-code words inside a source-ink enclosure.

Composes an INDEPENDENT original two-page four-side painted-ink audit with
original native word evidence. This is a source-location candidate only:
not trusted glyph/clip ownership, not finished wall faces, not an area.
"""
from __future__ import annotations

import hashlib
import math
import re

import fitz

from tools.diag_original_room_four_edge_source_ink_shadow import (
    audit_source_painted_enclosure_correspondence_shadow,
)


def audit_original_painted_enclosure_finish_word_candidates(
    original_pdf_bytes: bytes, *, expected_sha256: str,
    floor_page_1_based: int, finish_page_1_based: int,
    original_side_pairs: dict[str, tuple[str, str]],
    expected_translation_pdf_pts: tuple[float, float],
    original_finish_code: str,
    max_native_words: int = 100000,
) -> dict:
    if (type(original_finish_code) is not str
            or not re.fullmatch(r"[A-Z][A-Z0-9]{1,11}", original_finish_code)
            or type(max_native_words) is not int or max_native_words <= 0):
        raise ValueError("source_original_finish_code_or_scan_bound_invalid")
    # Accept no caller-crafted 'confirmed' room receipt: recompute original
    # evidence from bytes, exact physical PDF pages and all native side IDs.
    source = audit_source_painted_enclosure_correspondence_shadow(
        original_pdf_bytes,
        expected_sha256=expected_sha256,
        floor_page_1_based=floor_page_1_based,
        finish_page_1_based=finish_page_1_based,
        original_side_pairs=original_side_pairs,
        expected_translation_pdf_pts=expected_translation_pdf_pts,
    )
    bounds = source["source_finish_painted_corner_evidence"][
        "original_source_ink_bbox_pdf_pts"
    ]
    if (type(bounds) not in (tuple, list) or len(bounds) != 4
            or any(type(v) not in (float, int) or not math.isfinite(v)
                   for v in bounds)):
        raise ValueError("original_source_painted_enclosure_invalid")
    x0, y0, x1, y1 = bounds
    # The upstream original source SHA was checked by the painted-ink audit.
    # This second read never accepts a synthetic code/word list.
    with fitz.open(stream=original_pdf_bytes, filetype="pdf") as original:
        if finish_page_1_based > len(original):
            raise ValueError("original_finish_source_page_unavailable")
        native = original[finish_page_1_based - 1].get_text(
            "words", sort=False
        )
    if len(native) > max_native_words:
        raise ValueError("bounded_original_native_finish_word_scan_required")
    all_words = []
    seen = set()
    for word in native:
        if str(word[4]).strip() != original_finish_code:
            continue
        source_id = (finish_page_1_based, int(word[5]),
                     int(word[6]), int(word[7]))
        if source_id in seen:
            raise ValueError("original_native_finish_word_duplicate_address")
        seen.add(source_id)
        rect = tuple(float(x) for x in word[:4])
        if not all(math.isfinite(x) for x in rect):
            raise ValueError("original_source_finish_word_bbox_nonfinite")
        a, b, c, d = rect
        inside = a >= x0 and b >= y0 and c <= x1 and d <= y1
        overlaps = a < x1 and c > x0 and b < y1 and d > y0
        all_words.append({
            "source_original_finish_word_address": source_id,
            "source_original_finish_code_untrusted": original_finish_code,
            "source_original_finish_word_bbox_pdf_pts": rect,
            "completely_inside_source_painted_enclosure": inside,
            "crosses_source_painted_enclosure_boundary":
                overlaps and not inside,
            "source_glyph_clip_integrity_authenticated": False,
            "source_physical_room_finish_owner_authenticated": False,
        })
    inside = tuple(row for row in all_words
                   if row["completely_inside_source_painted_enclosure"])
    crossing = tuple(row for row in all_words
                     if row["crosses_source_painted_enclosure_boundary"])
    outside = tuple(row for row in all_words
                    if not row["completely_inside_source_painted_enclosure"]
                    and not row["crosses_source_painted_enclosure_boundary"])
    candidate = len(inside) == 1 and not crossing
    return {
        "status": (
            "one_original_finish_word_inside_painted_enclosure_candidate"
            if candidate else
            "original_finish_word_inside_painted_enclosure_abstained"
        ),
        "first_remaining_authority_gate": (
            "source_glyph_clipping_physical_room_and_finished_face_unproven"
            if candidate else
            "original_printed_finish_code_room_ownership_not_unique"
        ),
        "original_source_sha256": expected_sha256,
        "original_floor_page_1_based": floor_page_1_based,
        "original_finish_page_1_based": finish_page_1_based,
        "source_original_finish_code_untrusted": original_finish_code,
        "source_original_ink_floor_finish_correspondence": source,
        "source_original_finish_code_words_inside_painted_enclosure": inside,
        "source_original_finish_code_words_crossing_painted_boundary": crossing,
        "source_other_same_code_original_word_competitors": outside,
        "source_original_full_finish_code_word_universe": tuple(all_words),
        "source_original_finish_occurrence_glyph_clip_authenticated": False,
        "source_cross_page_physical_room_equivalence_authenticated": False,
        "source_finished_wall_face_authenticated": False,
        "source_original_source_ink_polygon_is_finished_floor": False,
        "source_quantity_sealing_authority_granted": False,
        "new_firm_quantities": 0,
    }
