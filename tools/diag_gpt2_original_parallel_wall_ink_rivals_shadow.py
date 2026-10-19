"""Exact SHA-native parallel wall-ink rival universe, no nearest-wall election.

Original page, path and paint evidence only. Never grants structural identity,
W4 room closure, finished face, material occurrence, metric or FIRM quantities.
"""
from __future__ import annotations

import hashlib
import math
import re

import fitz

_ID = re.compile(r"d(0|[1-9][0-9]*)i(0|[1-9][0-9]*)\\Z")


def audit_original_parallel_wall_ink_rivals(
    pdf_bytes: bytes, *, expected_sha256: str, page_1_based: int,
    reference_native_path_item_id: str,
    independently_supplied_viewport_pdf_pts: tuple[float, float, float, float],
    maximum_parallel_offset_pdf_pts: float,
    maximum_native_paths: int = 120000,
    maximum_rivals: int = 4096,
) -> dict:
    if type(pdf_bytes) is not bytes or not pdf_bytes:
        raise ValueError("original_pdf_bytes_required")
    if (type(expected_sha256) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
            or hashlib.sha256(pdf_bytes).hexdigest() != expected_sha256):
        raise ValueError("original_pdf_sha256_mismatch")
    if type(page_1_based) is not int or page_1_based < 1:
        raise ValueError("original_source_page_required")
    match = _ID.fullmatch(reference_native_path_item_id) if (
        type(reference_native_path_item_id) is str
    ) else None
    if match is None:
        raise ValueError("original_native_path_item_id_required")
    if (type(maximum_parallel_offset_pdf_pts) not in (int, float)
            or not math.isfinite(maximum_parallel_offset_pdf_pts)
            or maximum_parallel_offset_pdf_pts <= 0):
        raise ValueError("bounded_source_parallel_offset_required")
    if (type(maximum_native_paths) is not int or maximum_native_paths <= 0
            or type(maximum_rivals) is not int or maximum_rivals <= 0):
        raise ValueError("bounded_original_source_work_required")
    if (type(independently_supplied_viewport_pdf_pts) not in (tuple, list)
            or len(independently_supplied_viewport_pdf_pts) != 4
            or any(type(x) not in (float, int) or not math.isfinite(x)
                   for x in independently_supplied_viewport_pdf_pts)):
        raise ValueError("original_source_viewport_invalid")
    vx0, vy0, vx1, vy1 = map(float, independently_supplied_viewport_pdf_pts)
    if vx0 >= vx1 or vy0 >= vy1:
        raise ValueError("original_source_viewport_invalid")
    with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf:
        if page_1_based > len(pdf):
            raise ValueError("original_pdf_source_page_out_of_bounds")
        drawings = pdf[page_1_based - 1].get_drawings()
    if len(drawings) > maximum_native_paths:
        raise ValueError("original_native_paths_safety_cap")
    original_path, original_item = map(int, match.groups())
    if original_path >= len(drawings):
        raise ValueError("original_reference_path_not_found")
    src_path = drawings[original_path]
    if original_item >= len(src_path.get("items", ())):
        raise ValueError("original_reference_item_not_found")
    original = src_path["items"][original_item]
    if len(original) < 3 or original[0] != "l":
        raise ValueError("original_reference_must_be_single_line")
    reference = tuple(float(v) for p in original[1:3] for v in (p.x, p.y))
    ax, ay, bx, by = reference
    if not all(math.isfinite(v) for v in reference):
        raise ValueError("invalid_original_reference_line")
    axis = "vertical" if ax == bx else "horizontal" if ay == by else None
    if axis is None or reference[0:2] == reference[2:4]:
        raise ValueError("original_reference_axis_aligned_line_required")
    fixed = ax if axis == "vertical" else ay
    along = sorted((ay, by) if axis == "vertical" else (ax, bx))
    reference_color = src_path.get("color")
    reference_width = src_path.get("width")
    if (reference_color is None
            or type(reference_width) not in (int, float)
            or not math.isfinite(reference_width)
            or reference_width <= 0):
        raise ValueError("original_reference_painted_ink_required")

    def view_relation(line_fixed, segment, width):
        half = width / 2
        if axis == "vertical":
            painted = (line_fixed-half, segment[0]-half,
                       line_fixed+half, segment[1]+half)
        else:
            painted = (segment[0]-half, line_fixed-half,
                       segment[1]+half, line_fixed+half)
        inside = (
            painted[0] >= vx0 and painted[1] >= vy0
            and painted[2] <= vx1 and painted[3] <= vy1
        )
        outside = (
            painted[2] < vx0 or painted[0] > vx1
            or painted[3] < vy0 or painted[1] > vy1
        )
        return ("inside" if inside else "excluded" if outside
                else "straddles")

    rivals = []
    for path_no, record in enumerate(drawings):
        if record.get("color") != reference_color:
            continue
        width = record.get("width")
        if (type(width) not in (int, float)
                or not math.isfinite(width) or width <= 0):
            continue
        for item_no, element in enumerate(record.get("items", ())):
            if len(element) < 3 or element[0] != "l":
                continue
            x1, y1 = float(element[1].x), float(element[1].y)
            x2, y2 = float(element[2].x), float(element[2].y)
            if not all(math.isfinite(v) for v in (x1, y1, x2, y2)):
                continue
            if axis == "vertical":
                if x1 != x2:
                    continue
                candidate_fixed = x1
                segment = sorted((y1,y2))
            else:
                if y1 != y2:
                    continue
                candidate_fixed = y1
                segment = sorted((x1,x2))
            offset = candidate_fixed - fixed
            if abs(offset) > maximum_parallel_offset_pdf_pts:
                continue
            low, high = max(along[0],segment[0]),min(along[1],segment[1])
            if low >= high:
                continue
            rivals.append({
                "original_native_path_item_id": f"d{path_no}i{item_no}",
                "original_native_axis": axis,
                "original_fixed_coordinate_pdf_pts": candidate_fixed,
                "signed_parallel_offset_from_reference_pdf_pts": offset,
                "original_overlapping_interval_pdf_pts": (low,high),
                "original_stroke_width_pdf_pts": float(width),
                "original_painted_viewport_relation":
                    view_relation(candidate_fixed,segment,width),
                "source_physical_wall_role_granted": False,
                "source_finished_wall_face_role_granted": False,
            })
            if len(rivals) > maximum_rivals:
                raise ValueError("bounded_original_parallel_source_rivals_required")
    return {
        "status": "all_bounded_original_parallel_ink_rivals_unclassified",
        "original_source_sha256": expected_sha256,
        "original_source_page_1_based": page_1_based,
        "reference_original_native_path_item_id": reference_native_path_item_id,
        "original_reference_fixed_coordinate_pdf_pts": fixed,
        "source_viewport_bbox_supplied_not_owned_here": (vx0,vy0,vx1,vy1),
        "original_ink_rivals": tuple(sorted(
            rivals,
            key=lambda row: (
                row["signed_parallel_offset_from_reference_pdf_pts"],
                row["original_native_path_item_id"],
            ),
        )),
        "source_rival_universe_exhaustive_within_declared_search_band": True,
        "original_wall_or_finished_face_owner_elected": False,
        "new_firm_quantities": 0,
    }
