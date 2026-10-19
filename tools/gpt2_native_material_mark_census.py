"""Native original-plan material-code census; read-only source evidence, never m2.

The bounded view box must come from an independently authenticated drawing
viewport. Supplying a box does not establish a room/floor relationship or a
material definition. In particular a schedule code outside the drawing box is
not a physical installed-finish occurrence.
"""
from __future__ import annotations

import hashlib
import math
import re

import fitz

_CODE = re.compile(r"[A-Z][A-Z0-9]{1,12}\Z")


def census_native_plan_material_words(
    pdf_bytes: bytes, *, expected_sha256: str, page_number: int,
    plan_view_bbox_pdf_pts: tuple[float, float, float, float],
    codes: tuple[str, ...], viewport_id: str,
) -> dict:
    """Retain exact native word addresses inside and outside one scoped view."""
    if type(pdf_bytes) is not bytes or not pdf_bytes:
        raise ValueError("original_pdf_bytes_required")
    if (
        type(expected_sha256) is not str
        or not re.fullmatch("[0-9a-f]{64}", expected_sha256)
        or hashlib.sha256(pdf_bytes).hexdigest() != expected_sha256
    ):
        raise ValueError("immutable_original_source_sha_mismatch")
    if type(page_number) is not int or page_number < 1:
        raise ValueError("source_page_number_required")
    if type(viewport_id) is not str or not viewport_id.strip():
        raise ValueError("authenticated_viewport_id_required")
    if (
        type(plan_view_bbox_pdf_pts) not in (tuple, list)
        or len(plan_view_bbox_pdf_pts) != 4
        or any(type(v) not in (int, float) or not math.isfinite(v)
               for v in plan_view_bbox_pdf_pts)
    ):
        raise ValueError("original_plan_view_bbox_invalid")
    x0, y0, x1, y1 = map(float, plan_view_bbox_pdf_pts)
    if x0 >= x1 or y0 >= y1:
        raise ValueError("original_plan_view_bbox_invalid")
    if (
        type(codes) not in (tuple, list) or not codes
        or len(codes) != len(set(codes))
        or any(type(code) is not str or not _CODE.fullmatch(code)
               for code in codes)
    ):
        raise ValueError("source_material_codes_invalid")
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if page_number > doc.page_count:
            raise ValueError("original_page_out_of_bounds")
        rows = doc.load_page(page_number - 1).get_text("words", sort=False)
    finally:
        doc.close()
    if len(rows) > 100000:
        raise ValueError("original_native_word_census_safety_cap")
    selected = set(codes)
    inside, crossing, outside = [], [], []
    seen_native_addresses = set()
    for word in rows:
        # Only unique producer-native block/line/word identity can be
        # carried to a future physical-owner receipt. Never silently
        # overwrite two different original source words with one address.
        if (
            not isinstance(word, (tuple, list)) or len(word) < 8
            or any(type(value) is not int or value < 0 for value in word[5:8])
        ):
            raise ValueError("malformed_original_source_word_address")
        native_address = (page_number, word[5], word[6], word[7])
        if native_address in seen_native_addresses:
            raise ValueError("duplicate_original_source_word_address")
        seen_native_addresses.add(native_address)
        if str(word[4]).strip() not in selected:
            continue
        bbox = tuple(float(v) for v in word[:4])
        if any(not math.isfinite(v) for v in bbox) or bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
            raise ValueError("malformed_original_source_word")
        source = {
            "material_code_untrusted": str(word[4]).strip(),
            "source_word_address": native_address,
            "native_bbox_pdf_pts": bbox,
            "original_text_source_only": True,
            "material_issuer_authenticated": False,
            "physical_floor_owner_authenticated": False,
            "metric_floor_finish_area_m2": None,
        }
        wholly_inside = (
            bbox[0] >= x0 and bbox[1] >= y0
            and bbox[2] <= x1 and bbox[3] <= y1
        )
        intersects = (
            bbox[0] < x1 and bbox[2] > x0
            and bbox[1] < y1 and bbox[3] > y0
        )
        # A partly clipped word cannot be counted as an owned plan finish
        # OR treated as an unrelated schedule/legend word.
        (inside if wholly_inside else crossing if intersects else outside).append(source)
    def stable(rows):
        return tuple(sorted(rows, key=lambda row: row["source_word_address"]))
    return {
        "status": "original_native_plan_word_candidates_only",
        "original_source_sha256": expected_sha256,
        "original_page_number": page_number,
        "source_viewport_id_unverified_by_census": viewport_id,
        "requested_codes": tuple(sorted(codes)),
        "within_supplied_plan_view": stable(inside),
        "boundary_crossing_plan_words": stable(crossing),
        "outside_supplied_plan_view": stable(outside),
        "viewport_word_membership_unambiguous": not crossing,
        "source_word_partition_complete": True,
        "cross_sheet_floor_correspondence_proven": False,
        "new_firm_floor_finish_quantities": 0,
    }
