"""Read-only original PDF painted native line versus a supplied source viewport.

This diagnostic does NOT authenticate viewport ownership, structural wall
roles, room identity, floor-finish material or metric takeoff. It preserves
original path-item ink and reports whether a stroke's painted envelope is
fully inside, fully outside, or straddling an independently owned viewport.
"""
from __future__ import annotations

import hashlib
import math
import re

import fitz

_NATIVE_ID = re.compile(r"d(0|[1-9][0-9]*)i(0|[1-9][0-9]*)\Z")


def audit_original_painted_stroke_view_membership(
    pdf_bytes: bytes, *, expected_sha256: str, page_1_based: int,
    source_native_path_item_id: str,
    supplied_source_viewport_bbox_pdf_pts: tuple[float, float, float, float],
    supplied_source_viewport_id: str,
    max_native_paths: int = 120000,
) -> dict:
    """Compare unmodified original ink with unmodified caller-issued crop."""
    if type(pdf_bytes) is not bytes or not pdf_bytes:
        raise ValueError("original_pdf_bytes_required")
    if (
        type(expected_sha256) is not str
        or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
        or hashlib.sha256(pdf_bytes).hexdigest() != expected_sha256
    ):
        raise ValueError("original_source_sha256_conflict")
    if type(page_1_based) is not int or page_1_based <= 0:
        raise ValueError("original_source_page_required")
    if (
        type(supplied_source_viewport_id) is not str
        or not supplied_source_viewport_id.strip()
        or supplied_source_viewport_id != supplied_source_viewport_id.strip()
    ):
        raise ValueError("original_source_viewport_identity_required")
    if (
        type(supplied_source_viewport_bbox_pdf_pts) not in (tuple, list)
        or len(supplied_source_viewport_bbox_pdf_pts) != 4
        or any(type(v) not in (int, float) or not math.isfinite(v)
               for v in supplied_source_viewport_bbox_pdf_pts)
    ):
        raise ValueError("original_viewport_bbox_invalid")
    vx0, vy0, vx1, vy1 = map(float, supplied_source_viewport_bbox_pdf_pts)
    if vx0 >= vx1 or vy0 >= vy1:
        raise ValueError("original_viewport_bbox_invalid")
    match = _NATIVE_ID.fullmatch(source_native_path_item_id) if (
        type(source_native_path_item_id) is str
    ) else None
    if match is None:
        raise ValueError("original_native_path_item_id_required")
    path_id, item_id = (int(n) for n in match.groups())
    if type(max_native_paths) is not int or max_native_paths <= 0:
        raise ValueError("bounded_original_native_paths_required")
    with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
        if page_1_based > len(document):
            raise ValueError("original_source_page_out_of_bounds")
        paths = document[page_1_based - 1].get_drawings()
    if len(paths) > max_native_paths:
        raise ValueError("original_native_paths_safety_cap")
    if path_id >= len(paths):
        raise ValueError("original_native_path_missing")
    path = paths[path_id]
    items = path.get("items", ())
    if item_id >= len(items):
        raise ValueError("original_native_path_item_missing")
    item = items[item_id]
    if len(item) < 3 or item[0] != "l":
        raise ValueError("original_source_single_line_item_required")
    a, b = item[1:3]
    x0, y0, x1, y1 = (float(a.x), float(a.y), float(b.x), float(b.y))
    if not all(math.isfinite(x) for x in (x0, y0, x1, y1)):
        raise ValueError("original_native_line_nonfinite")
    if (x0 == x1) == (y0 == y1):
        raise ValueError("original_axis_aligned_line_required")
    width = path.get("width")
    if (type(width) not in (int, float) or not math.isfinite(width)
            or width <= 0):
        raise ValueError("original_native_stroke_width_unavailable")
    half = float(width) / 2
    painted = (
        min(x0, x1) - half, min(y0, y1) - half,
        max(x0, x1) + half, max(y0, y1) + half,
    )
    wholly_inside = (
        painted[0] >= vx0 and painted[1] >= vy0
        and painted[2] <= vx1 and painted[3] <= vy1
    )
    sep_x = max(vx0 - painted[2], painted[0] - vx1, 0.0)
    sep_y = max(vy0 - painted[3], painted[1] - vy1, 0.0)
    outside = sep_x > 0 or sep_y > 0
    status = (
        "original_painted_stroke_inside_viewport"
        if wholly_inside else
        "original_painted_stroke_excluded_from_viewport"
        if outside else
        "original_painted_stroke_straddles_viewport"
    )
    return {
        "status": status,
        "original_source_sha256": expected_sha256,
        "original_source_page_1_based": page_1_based,
        "original_native_path_item_id": source_native_path_item_id,
        "supplied_source_viewport_id_not_authenticated_by_this_diagnostic":
            supplied_source_viewport_id,
        "supplied_viewport_bbox_unchanged_pdf_pts": (vx0, vy0, vx1, vy1),
        "source_line_endpoints_native_pdf_pts": ((x0, y0), (x1, y1)),
        "original_native_line_width_pdf_pts": float(width),
        "original_paint_bbox_native_pdf_pts": painted,
        "minimum_source_paint_to_viewport_gap_pdf_pts":
            math.hypot(sep_x, sep_y),
        "original_source_line_axis":
            "vertical" if x0 == x1 else "horizontal",
        "native_stroke_color_untrusted": path.get("color"),
        "source_physical_structural_wall_role_granted": False,
        "source_original_viewport_ownership_granted": False,
        "source_room_face_or_finish_owner_granted": False,
        "new_firm_quantities": 0,
    }


__all__ = ["audit_original_painted_stroke_view_membership"]
