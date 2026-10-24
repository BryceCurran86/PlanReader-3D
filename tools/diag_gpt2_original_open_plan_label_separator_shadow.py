"""Source-native local separator probe between two original printed label groups.

This read-only audit does NOT prove that two labels are the same physical room.
An absent line on one chosen probe is only local negative *ink* evidence.
It cannot manufacture open-plan finish boundaries or mint measured quantities.
"""
from __future__ import annotations

import hashlib
import math
import re

import fitz


def audit_original_label_between_ink_probe(
    pdf_bytes: bytes, *, expected_sha256: str, page_1_based: int,
    first_label_native_word_addresses: tuple[tuple[int, int, int], ...],
    second_label_native_word_addresses: tuple[tuple[int, int, int], ...],
    probe_line_pdf_pts: tuple[tuple[float, float], tuple[float, float]],
    minimum_stroke_width_pdf_pts: float = .45,
    max_original_paths: int = 120000,
    max_probe_ink_rivals: int = 10000,
) -> dict:
    if (type(pdf_bytes) is not bytes or not pdf_bytes
            or type(expected_sha256) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
            or hashlib.sha256(pdf_bytes).hexdigest() != expected_sha256):
        raise ValueError("original_separator_source_sha256_required")
    if type(page_1_based) is not int or page_1_based <= 0:
        raise ValueError("original_separator_page_invalid")
    ids = []
    for group in (first_label_native_word_addresses,
                  second_label_native_word_addresses):
        if (type(group) not in (tuple, list) or not group or len(group) > 16
                or any(type(word) not in (tuple, list) or len(word) != 3
                       or any(type(v) is not int or v < 0 for v in word)
                       for word in group)):
            raise ValueError("source_original_label_word_addresses_invalid")
        ids.extend(tuple(tuple(word) for word in group))
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate_original_label_word_addresses")
    if (type(probe_line_pdf_pts) not in (tuple, list)
            or len(probe_line_pdf_pts) != 2
            or any(type(pt) not in (tuple, list) or len(pt) != 2
                   or any(type(v) not in (int, float) or not math.isfinite(v)
                          for v in pt)
                   for pt in probe_line_pdf_pts)):
        raise ValueError("original_separator_probe_invalid")
    (ax, ay), (bx, by) = probe_line_pdf_pts
    vertical = ax == bx and ay != by
    horizontal = ay == by and ax != bx
    if not vertical and not horizontal:
        raise ValueError("source_separator_probe_must_be_axis_aligned")
    if (type(minimum_stroke_width_pdf_pts) not in (int, float)
            or not math.isfinite(minimum_stroke_width_pdf_pts)
            or minimum_stroke_width_pdf_pts <= 0
            or type(max_original_paths) is not int or max_original_paths <= 0
            or type(max_probe_ink_rivals) is not int
            or max_probe_ink_rivals <= 0):
        raise ValueError("bounded_original_separator_ink_required")
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        if page_1_based > len(doc):
            raise ValueError("original_separator_page_missing")
        page = doc[page_1_based - 1]
        paths = page.get_drawings()
        words = page.get_text("words", sort=False)
    if len(paths) > max_original_paths or len(words) > 100000:
        raise ValueError("original_separator_source_inventory_over_cap")
    word_by_id = {}
    for word in words:
        if len(word) < 8:
            raise ValueError("malformed_original_source_word")
        identity = tuple(word[5:8])
        if identity in word_by_id:
            raise ValueError("duplicate_original_source_word_address")
        word_by_id[identity] = word
    if any(identity not in word_by_id for identity in ids):
        raise ValueError("original_label_word_source_missing")
    first, second = (
        tuple(word_by_id[tuple(identity)] for identity in group)
        for group in (
            first_label_native_word_addresses,
            second_label_native_word_addresses,
        )
    )
    def label_box(group):
        return (min(w[0] for w in group), min(w[1] for w in group),
                max(w[2] for w in group), max(w[3] for w in group))
    first_box, second_box = label_box(first), label_box(second)
    fixed = float(ax if vertical else ay)
    lo, hi = sorted(map(float, (ay, by) if vertical else (ax, bx)))
    first_before = first_box[2 if vertical else 3] < fixed
    second_after = second_box[0 if vertical else 1] > fixed
    second_before = second_box[2 if vertical else 3] < fixed
    first_after = first_box[0 if vertical else 1] > fixed
    if (not ((first_before and second_after) or
             (second_before and first_after))
            or min(first_box[3 if vertical else 2],
                   second_box[3 if vertical else 2], hi)
            <= max(first_box[1 if vertical else 0],
                   second_box[1 if vertical else 0], lo)):
        raise ValueError("independent_source_labels_not_on_opposite_probe_sides")
    matches = []
    for path_id, record in enumerate(paths):
        if (record.get("color") != (0., 0., 0.)
                or type(record.get("width")) not in (float, int)
                or not math.isfinite(record["width"])
                or record["width"] < minimum_stroke_width_pdf_pts
                or record.get("stroke_opacity", 1.) != 1.
                or "".join(str(record.get("dashes") or "").split()) not in
                   ("[]0", "")):
            continue
        for item_id, item in enumerate(record.get("items", ())):
            if len(item) < 3 or item[0] != "l":
                continue
            a, b = item[1:3]
            q = (float(a.x),float(a.y),float(b.x),float(b.y))
            if not all(math.isfinite(v) for v in q):
                raise ValueError("invalid_original_native_ink_coordinate")
            if vertical:
                aligned = abs(q[0]-fixed) <= .001 and abs(q[2]-fixed) <= .001
                start,end = sorted((q[1],q[3]))
            else:
                aligned = abs(q[1]-fixed) <= .001 and abs(q[3]-fixed) <= .001
                start,end = sorted((q[0],q[2]))
            if not aligned:
                continue
            overlap = (max(lo,start), min(hi,end))
            if overlap[1] <= overlap[0]:
                continue
            matches.append({
                "original_native_path_item_id": f"d{path_id}i{item_id}",
                "source_ink_overlap_on_probe_pdf_pts": overlap,
                "source_stroke_width_pdf_pts": float(record["width"]),
                "structural_wall_role_authenticated": False,
            })
            if len(matches) > max_probe_ink_rivals:
                raise ValueError("original_separator_probe_ink_safety_cap")
    merged = []
    for row in sorted(matches, key=lambda r: r["source_ink_overlap_on_probe_pdf_pts"]):
        start,end = row["source_ink_overlap_on_probe_pdf_pts"]
        if merged and start <= merged[-1][1] + .001:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start,end))
    coverage_complete = (
        len(merged) == 1
        and merged[0][0] <= lo + .001
        and merged[0][1] >= hi - .001
    )
    return {
        "status": "source_original_local_separator_ink_probe_only",
        "original_source_sha256": expected_sha256,
        "original_page_1_based": page_1_based,
        "first_label_native_word_addresses": tuple(ids[:len(first)]),
        "second_label_native_word_addresses": tuple(ids[len(first):]),
        "original_label_text_candidates_untrusted": (
            tuple(str(w[4]) for w in first),
            tuple(str(w[4]) for w in second),
        ),
        "original_probe_line_pdf_pts": tuple(tuple(map(float,pt))
                                             for pt in probe_line_pdf_pts),
        "original_opaque_black_collinear_ink_candidates": tuple(matches),
        "original_probe_ink_interval_union_pdf_pts": tuple(merged),
        "probe_fully_covered_by_black_ink": coverage_complete,
        "no_qualifying_original_black_ink_on_this_probe": not matches,
        "original_probe_is_source_authentic_structural_separator": False,
        "two_original_labels_same_physical_room_proven": False,
        "open_plan_finish_zone_geometry_authenticated": False,
        "new_firm_quantities": 0,
    }
