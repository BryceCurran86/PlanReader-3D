"""Read-only source-native figured-dimension vs wall-face *candidate* ledger.

A printed dimension stroke's endpoint may share an axial ordinate with a wall
face located far away; that is not a witness intersection or proof of finished
interior face. Never select first/nearest ink; preserve fixtures and competing
parallel faces. The caller-supplied region is not a complete room universe.
"""
from __future__ import annotations

import math
import re
from typing import Any

_SOURCE_ID = re.compile(r"^d(0|[1-9]\d*)i(0|[1-9]\d*)$", re.ASCII)


def _bbox(value):
    try:
        if isinstance(value, (str, bytes)):
            return None
        v = tuple(float(x) for x in value)
    except (ValueError, TypeError, OverflowError):
        return None
    if len(v) != 4 or not all(map(math.isfinite, v)) or v[2] <= v[0] or v[3] <= v[1]:
        return None
    return v


def _line(item):
    try:
        if item[0] != "l":
            return None
        a, b = item[1:3]
        v = tuple(float(x) for x in (a.x, a.y, b.x, b.y))
    except (TypeError, IndexError, AttributeError, ValueError, OverflowError):
        return None
    if not all(map(math.isfinite, v)) or v[:2] == v[2:]:
        return None
    if v[0] == v[2] and v[1] != v[3]:
        return v, "native_y"
    if v[1] == v[3] and v[0] != v[2]:
        return v, "native_x"
    return None


def _distance_point_to_segment(x, y, v):
    ax, ay, bx, by = v
    dx, dy = bx - ax, by - ay
    z = dx * dx + dy * dy
    if z <= 0:
        return math.hypot(x - ax, y - ay)
    t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / z))
    return math.hypot(x - (ax + t * dx), y - (ay + t * dy))


def audit_native_dimension_face_competitors(
    page: Any, *, source_dimension_line_id: str,
    candidate_region_bbox: object, max_original_lines: int = 120000,
):
    """Preserve all axis-normal source-native ink lines overlapping a region.

    No drawing-specific thresholds, target wall election, scalar measurement,
    structural ink role, valid room polygon or cross-sheet correspondence.
    """
    m = (_SOURCE_ID.fullmatch(source_dimension_line_id)
         if type(source_dimension_line_id) is str else None)
    if not m:
        raise ValueError("original_dimension_path_id_required")
    box = _bbox(candidate_region_bbox)
    if box is None:
        raise ValueError("valid_candidate_region_required")
    if type(max_original_lines) is not int or max_original_lines <= 0:
        raise ValueError("invalid_original_line_cap")
    drawings = page.get_drawings()
    index, item_index = map(int, m.groups())
    if index >= len(drawings):
        raise ValueError("original_dimension_source_path_unavailable")
    items = drawings[index].get("items", ())
    if item_index >= len(items):
        raise ValueError("original_dimension_source_item_unavailable")
    dimension = _line(items[item_index])
    if dimension is None:
        return {
            "status": "not_a_native_axis_dimension_line",
            "quantity_granted": False,
            "dimension_authority_granted": False,
            "source_wall_face_authority_granted": False,
        }
    segment, axis = dimension
    ends = ((segment[0], segment[1]), (segment[2], segment[3]))
    normal_axis = "native_x" if axis == "native_y" else "native_y"
    original = []
    line_count = 0
    for source_path, drawing in enumerate(drawings):
        for source_item, item in enumerate(drawing.get("items", ())):
            parsed = _line(item)
            if parsed is None:
                continue
            line_count += 1
            if line_count > max_original_lines:
                return {
                    "status": "source_candidate_scope_exceeded_cap",
                    "source_candidate_universe_complete": False,
                    "quantity_granted": False,
                    "dimension_authority_granted": False,
                    "source_wall_face_authority_granted": False,
                }
            v, line_axis = parsed
            if line_axis != normal_axis:
                continue
            # Only an ROI inventory. Source roles and completeness remain unknown.
            if (max(v[0], v[2]) < box[0] or min(v[0], v[2]) > box[2]
                    or max(v[1], v[3]) < box[1] or min(v[1], v[3]) > box[3]):
                continue
            original.append((
                f"d{source_path}i{source_item}", v,
                drawing.get("color"), drawing.get("width"),
            ))
    per_endpoint = []
    for end in ends:
        rows = []
        for primitive, v, color, width in original:
            delta = v[1] - end[1] if axis == "native_y" else v[0] - end[0]
            rows.append({
                "original_source_primitive_id": primitive,
                "source_line_pdf_pts": list(v),
                "original_native_axis_offset_pdf_pts": delta,
                "projected_dimension_coordinate_equal": delta == 0.0,
                "transverse_gap_pdf_pts": _distance_point_to_segment(*end, v),
                "source_stroke_color": color,
                "source_stroke_width_pdf_pts": width,
                "source_line_physical_wall_role_proven": False,
                "source_figure_witness_intersection_proven": False,
            })
        rows.sort(key=lambda r: (
            abs(r["original_native_axis_offset_pdf_pts"]),
            r["original_source_primitive_id"],
        ))
        per_endpoint.append({
            "source_dimension_line_endpoint_pdf_pts": list(end),
            "all_region_axis_normal_original_source_lines": rows,
            "physical_finished_wall_face_selected": False,
        })
    return {
        "status": "read_only_projected_endpoint_competitors",
        "source_dimension_line_id": source_dimension_line_id,
        "original_dimension_line_pdf_pts": list(segment),
        "source_dimension_line_axis": axis,
        "candidate_region_pdf_pts": list(box),
        "dimension_endpoints": per_endpoint,
        "source_candidate_universe_complete": False,
        "reason": "region_does_not_prove_completeness_or_structural_role",
        "source_original_lines_scanned": line_count,
        "quantity_granted": False,
        "dimension_authority_granted": False,
        "source_wall_face_authority_granted": False,
    }
