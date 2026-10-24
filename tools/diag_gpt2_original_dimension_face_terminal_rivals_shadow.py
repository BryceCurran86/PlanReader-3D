"""Original source printed-dimension terminal vs painted wall-face rivals.

This read-only SHA-native diagnostic is NOT a figured-dimension-to-finished-
face issuance. The original dimension may terminate at an outside wall face.
Every alternative source face remains unselected until a physical room ring,
wall role and source-native terminal ancestry are independently authenticated.
"""
from __future__ import annotations

import hashlib
import math
import re

import fitz

from tools.diag_original_room_four_edge_source_ink_shadow import _line


def audit_original_dimension_to_competing_wall_faces(
    original_pdf_bytes: bytes, *, expected_sha256: str,
    page_1_based: int, original_dimension_line_path_item_id: str,
    original_candidate_face_line_path_item_ids: tuple[str,...],
    maximum_terminal_face_offset_pdf_pts: float = 6.,
    maximum_native_paths: int = 120000,
) -> dict:
    if (
        type(original_pdf_bytes) is not bytes
        or type(expected_sha256) is not str
        or not re.fullmatch(r"[0-9a-f]{64}",expected_sha256)
        or hashlib.sha256(original_pdf_bytes).hexdigest() != expected_sha256
    ):
        raise ValueError("immutable_original_source_sha256_required")
    if type(page_1_based) is not int or page_1_based < 1:
        raise ValueError("original_source_page_required")
    if (type(original_dimension_line_path_item_id) is not str
            or not original_dimension_line_path_item_id.strip()):
        raise ValueError("original_dimension_native_path_required")
    if (
        type(original_candidate_face_line_path_item_ids) not in (tuple,list)
        or not original_candidate_face_line_path_item_ids
        or len(original_candidate_face_line_path_item_ids) > 256
        or any(type(i) is not str or not i or i != i.strip()
               for i in original_candidate_face_line_path_item_ids)
        or len(set(original_candidate_face_line_path_item_ids))
           != len(original_candidate_face_line_path_item_ids)
    ):
        raise ValueError("bounded_original_face_candidate_universe_required")
    if (
        type(maximum_terminal_face_offset_pdf_pts) not in (int,float)
        or not math.isfinite(maximum_terminal_face_offset_pdf_pts)
        or maximum_terminal_face_offset_pdf_pts <= 0
        or type(maximum_native_paths) is not int or maximum_native_paths <= 0
    ):
        raise ValueError("bounded_original_dimension_terminal_source_required")
    with fitz.open(stream=original_pdf_bytes,filetype="pdf") as pdf:
        if page_1_based > len(pdf):
            raise ValueError("original_source_page_out_of_range")
        drawings = pdf[page_1_based-1].get_drawings()
    if len(drawings)>maximum_native_paths:
        raise ValueError("bounded_original_native_source_paths_required")
    dimension = _line(drawings, original_dimension_line_path_item_id)
    dx0,dy0 = dimension["ends"][0]
    dx1,dy1 = dimension["ends"][1]
    axis = "vertical" if dx0 == dx1 else "horizontal" if dy0 == dy1 else None
    if axis is None or (dx0,dy0)==(dx1,dy1):
        raise ValueError("original_source_axis_aligned_dimension_required")
    terminals = tuple(sorted((dy0,dy1) if axis=="vertical" else (dx0,dx1)))
    candidates = tuple(
        (path_id, _line(drawings,path_id))
        for path_id in original_candidate_face_line_path_item_ids
    )
    indexed = []
    for face_id, face in candidates:
        (ax,ay),(bx,by) = face["ends"]
        perpendicular = ay == by if axis=="vertical" else ax == bx
        if not perpendicular:
            raise ValueError("original_wall_face_perpendicular_source_line_required")
        coord = ay if axis=="vertical" else ax
        min_distance = min(abs(coord-v) for v in terminals)
        if min_distance > maximum_terminal_face_offset_pdf_pts:
            continue
        indexed.append({
            "original_face_native_path_item_id":face_id,
            "original_face_coordinate_on_dimension_axis_pdf_pts":coord,
            "original_dimension_terminal_offsets_pdf_pts":
                tuple(coord-v for v in terminals),
            "nearest_original_figured_terminal_distance_pdf_pts":min_distance,
            "native_original_wall_face_ink_endpoints_pdf_pts":tuple(face["ends"]),
            "source_face_original_paint_width_pdf_pts":face["stroke_width"],
            "source_dimensional_terminal_ink_not_finished_face_proof":True,
            "physical_inside_finished_face_owner_granted":False,
        })
    return {
        "status":"original_figured_dimension_competing_painted_face_sources",
        "original_source_sha256":expected_sha256,
        "original_source_page_1_based":page_1_based,
        "original_dimension_native_path_item_id":original_dimension_line_path_item_id,
        "original_dimension_axis":axis,
        "original_dimension_terminal_coordinates_pdf_pts":terminals,
        "original_dimension_ink_length_pdf_pts":terminals[1]-terminals[0],
        "all_bounded_competing_original_face_sources":tuple(sorted(
            indexed, key=lambda row:(
                row["nearest_original_figured_terminal_distance_pdf_pts"],
                row["original_face_native_path_item_id"],
            )
        )),
        "original_dimension_witness_is_internal_finished_clear_span":False,
        "source_painted_face_elected_for_finished_floor":False,
        "physical_room_or_cross_sheet_identity_granted":False,
        "new_firm_quantities":0,
    }
