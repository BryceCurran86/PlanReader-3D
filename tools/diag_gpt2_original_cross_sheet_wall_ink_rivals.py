"""All named original p11↔p7 native wall-ink rivals, without owner election."""
from __future__ import annotations

import hashlib
import math
import re

import fitz

from tools.diag_original_room_four_edge_source_ink_shadow import _line


def audit_original_cross_sheet_wall_ink_rivals(
    original_pdf_bytes: bytes, *, expected_sha256: str,
    finish_page_1_based: int, floor_page_1_based: int,
    finish_source_path_item_ids: tuple[str, ...],
    floor_source_path_item_ids: tuple[str, ...],
    source_translation_pdf_pts: tuple[float, float],
    maximum_candidate_pairs: int = 4096,
    maximum_native_paths: int = 120000,
) -> dict:
    if (type(original_pdf_bytes) is not bytes
            or type(expected_sha256) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
            or hashlib.sha256(original_pdf_bytes).hexdigest() != expected_sha256):
        raise ValueError("original_source_sha256_required")
    if (type(finish_page_1_based) is not int
            or type(floor_page_1_based) is not int
            or min(finish_page_1_based, floor_page_1_based) <= 0
            or finish_page_1_based == floor_page_1_based):
        raise ValueError("distinct_original_source_page_owners_required")
    for ids in (finish_source_path_item_ids, floor_source_path_item_ids):
        if (type(ids) not in (tuple, list) or not ids or len(ids) > 64
                or any(type(value) is not str or not value
                       or value != value.strip() for value in ids)
                or len(set(ids)) != len(ids)):
            raise ValueError("complete_bounded_original_path_id_universe_required")
    if (type(source_translation_pdf_pts) not in (tuple, list)
            or len(source_translation_pdf_pts) != 2
            or any(type(v) not in (int, float) or not math.isfinite(v)
                   for v in source_translation_pdf_pts)):
        raise ValueError("independent_original_source_translation_required")
    if (type(maximum_candidate_pairs) is not int or maximum_candidate_pairs <= 0
            or type(maximum_native_paths) is not int or maximum_native_paths <= 0
            or len(finish_source_path_item_ids) * len(floor_source_path_item_ids)
               > maximum_candidate_pairs):
        raise ValueError("bounded_original_wall_candidate_pairs_required")
    with fitz.open(stream=original_pdf_bytes, filetype="pdf") as document:
        if max(finish_page_1_based, floor_page_1_based) > len(document):
            raise ValueError("original_source_page_out_of_range")
        drawn = {
            page: document[page - 1].get_drawings()
            for page in (finish_page_1_based, floor_page_1_based)
        }
    if any(len(paths) > maximum_native_paths for paths in drawn.values()):
        raise ValueError("bounded_original_source_path_universe_required")
    finish = {
        identity: _line(drawn[finish_page_1_based], identity)
        for identity in finish_source_path_item_ids
    }
    floor = {
        identity: _line(drawn[floor_page_1_based], identity)
        for identity in floor_source_path_item_ids
    }
    dx, dy = map(float, source_translation_pdf_pts)
    def transformed(line):
        return sorted(
            (round(x + dx, 3), round(y + dy, 3))
            for x, y in line["ends"]
        )
    def same_ink_style(a, b):
        return (
            a["stroke_width"] == b["stroke_width"]
            and a["source_color"] == b["source_color"]
            and a["stroke_opacity"] == b["stroke_opacity"]
            and a["source_paint_type"] == b["source_paint_type"]
        )
    matrix = []
    for f_id in finish_source_path_item_ids:
        a = finish[f_id]
        transformed_ends = transformed(a)
        for floor_id in floor_source_path_item_ids:
            b = floor[floor_id]
            t0, t1 = transformed_ends
            u0, u1 = b["ends"]
            # Source line endpoint orientation may reverse. Native line
            # ancestry/physical wall role is NOT proved by ink coincidence.
            exact = transformed_ends == b["ends"]
            a_vert = t0[0] == t1[0]
            b_vert = u0[0] == u1[0]
            a_horiz = t0[1] == t1[1]
            b_horiz = u0[1] == u1[1]
            if a_vert and b_vert and t0[0] == u0[0]:
                overlap = max(0., min(t1[1], u1[1]) - max(t0[1], u0[1]))
            elif a_horiz and b_horiz and t0[1] == u0[1]:
                overlap = max(0., min(t1[0], u1[0]) - max(t0[0], u0[0]))
            else:
                overlap = 0.
            style = same_ink_style(a, b)
            candidate = (
                "exact_original_ink_equal" if exact and style
                else "partial_original_ink_interval_overlap"
                if overlap > 0 and style
                else "original_ink_style_conflict"
                if overlap > 0
                else "no_original_source_line_overlap"
            )
            matrix.append({
                "finish_original_path_item_id": f_id,
                "floor_original_path_item_id": floor_id,
                "original_source_comparison": candidate,
                "source_original_overlap_pdf_pts": overlap,
                "source_original_stroke_style_match": style,
                "source_finish_native_ink_pdf_pts": tuple(a["ends"]),
                "source_floor_native_ink_pdf_pts": tuple(b["ends"]),
                "cross_page_physical_structural_wall_equivalence_granted": False,
                "source_finished_wall_face_owner_granted": False,
            })
    return {
        "status": "original_native_cross_sheet_wall_ink_rivals_only",
        "original_source_sha256": expected_sha256,
        "finish_original_page": finish_page_1_based,
        "floor_original_page": floor_page_1_based,
        "independently_supplied_translation_pdf_pts": (dx, dy),
        "all_original_candidate_pairs": tuple(matrix),
        "original_candidate_universe_complete_within_supplied_path_ids": True,
        "source_registration_hypothesis_exhaustive": False,
        "physical_structural_wall_or_finished_face_elected": False,
        "new_firm_quantities": 0,
    }
