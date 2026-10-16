"""Read-only two-axis source rectangle-cell contact witness for semantic frames.

The existing F.07 rectangle-table heuristic proves a dense 2-D lattice of
rectangle CENTRES, not physical adjacency of the original cell edges. Repeated
separate light fixtures or architectural hatches can pass that condition.

This module retains those originals and reports whether any same-size source
rectangle family actually forms a connected row/column CELL lattice. It never
rejects existing F.07 frames, cannot decide an external schedule title, cannot
classify line-only table layouts and grants no text/material/room authority.
"""
from __future__ import annotations

from collections import defaultdict
import math
from typing import Any, Sequence

# Sub-point geometric roundoff, not a wall/face snapping tolerance.
NATIVE_RECT_EDGE_CONTACT_TOL_PT = 0.01
MAX_SOURCE_RECTANGLE_CANDIDATES = 20000


def _rect(value):
    try:
        if isinstance(value, (str, bytes)):
            return None
        t = tuple(float(v) for v in value)
    except (TypeError, ValueError, OverflowError):
        return None
    if len(t) != 4 or not all(math.isfinite(v) for v in t):
        return None
    if t[2] <= t[0] or t[3] <= t[1]:
        return None
    return t


def _source_contact_axis(a, b, *, tolerance=NATIVE_RECT_EDGE_CONTACT_TOL_PT):
    """Strict edge support; point contact, gap and mere overlap never join."""
    if (min(abs(a[2] - b[0]), abs(b[2] - a[0])) <= tolerance
            and min(a[3], b[3]) - max(a[1], b[1]) > tolerance):
        return "native_x_shared_edge"
    if (min(abs(a[3] - b[1]), abs(b[3] - a[1])) <= tolerance
            and min(a[2], b[2]) - max(a[0], b[0]) > tolerance):
        return "native_y_shared_edge"
    return None


def _family_connected_cell_witness(rects, *, min_source_cell_count: int):
    parent = list(range(len(rects)))
    contacts = []
    def root(v):
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v
    for i, a in enumerate(rects):
        for j in range(i + 1, len(rects)):
            axis = _source_contact_axis(a, rects[j])
            if axis is None:
                continue
            ra, rb = root(i), root(j)
            if ra != rb:
                parent[rb] = ra
            contacts.append((i, j, axis))
    component_indices: dict[int,list[int]] = defaultdict(list)
    for k in range(len(rects)):
        component_indices[root(k)].append(k)
    components = []
    for root_id, indices in component_indices.items():
        member = set(indices)
        x_links = [pair for pair in contacts if pair[0] in member and pair[2] == "native_x_shared_edge"]
        y_links = [pair for pair in contacts if pair[0] in member and pair[2] == "native_y_shared_edge"]
        components.append({
            "source_rectangle_count": len(indices),
            "native_x_shared_edge_count": len(x_links),
            "native_y_shared_edge_count": len(y_links),
            "source_cell_centers_pdf_pts": [
                [(rects[i][0]+rects[i][2])/2,
                 (rects[i][1]+rects[i][3])/2]
                for i in indices
            ],
            "two_axis_source_connected_cell_lattice_candidate": (
                len(indices) >= min_source_cell_count
                and bool(x_links) and bool(y_links)
            ),
            "semantic_table_content_and_owner_proven": False,
        })
    return components


def audit_source_rect_cell_lattice(
    page: Any, *, candidate_frame_bbox: Sequence[object],
    max_source_rectangles: int = MAX_SOURCE_RECTANGLE_CANDIDATES,
):
    """Reuse the source rectangle collector/dimension family key from F.07.

    Critical: table adjacency is still only candidate geometric evidence.
    Native source-parent identity, glyph/clip integrity, external caption and
    real table-content binding are separate mandatory first gates.
    """
    from pb_viewport_segmentation import (
        _page_rectangle_primitives,
        _TABLE_CELL_COUNT,
        _TABLE_CELL_DIMENSION_ROUND_DIGITS,
    )
    box = _rect(candidate_frame_bbox)
    if box is None:
        raise ValueError("valid_source_frame_bbox_required")
    if type(max_source_rectangles) is not int or max_source_rectangles < 1:
        raise ValueError("valid_source_rect_scope_cap_required")
    candidates = list(_page_rectangle_primitives(page))
    if len(candidates) > max_source_rectangles:
        return {
            "status": "source_rectangle_scope_cap_exceeded",
            "source_candidate_scope_complete": False,
            "positive_table_cell_authority": False,
            "physical_ceiling_or_material_authority": False,
        }
    frame_area = (box[2]-box[0])*(box[3]-box[1])
    width, height = box[2]-box[0], box[3]-box[1]
    families: dict[tuple[float,float],list[tuple[float,float,float,float]]] = defaultdict(list)
    for raw in candidates:
        cell = _rect(raw)
        if cell is None:
            continue
        if (cell[0] < box[0]-1 or cell[1] < box[1]-1
                or cell[2] > box[2]+1 or cell[3] > box[3]+1):
            continue
        area = (cell[2]-cell[0])*(cell[3]-cell[1])
        if not (4.0 < area < frame_area*.15):
            continue
        key = (
            round((cell[2]-cell[0])/width,_TABLE_CELL_DIMENSION_ROUND_DIGITS),
            round((cell[3]-cell[1])/height,_TABLE_CELL_DIMENSION_ROUND_DIGITS),
        )
        families[key].append(cell)
    rows = []
    for key in sorted(families):
        cells = families[key]
        if len(cells) < _TABLE_CELL_COUNT:
            continue
        components = _family_connected_cell_witness(
            cells, min_source_cell_count=_TABLE_CELL_COUNT,
        )
        rows.append({
            "source_dimension_normalized_family": list(key),
            "original_candidate_rectangles_pdf_pts": [list(cell) for cell in cells],
            "source_rectangle_count": len(cells),
            "components": components,
            "candidate_source_cell_lattice_present": any(
                c["two_axis_source_connected_cell_lattice_candidate"]
                for c in components
            ),
        })
    any_lattice = any(row["candidate_source_cell_lattice_present"] for row in rows)
    return {
        "status": "read_only_original_rectangle_cell_contact_inventory",
        "source_candidate_scope_complete": True,
        "original_source_rectangle_candidate_count": len(candidates),
        "frame_bbox_pdf_pts": list(box),
        "repeated_source_rectangle_families": rows,
        "connected_cell_lattice_candidate_only": any_lattice,
        "first_remaining_table_gate": (
            "connected_native_cells_still_need_semantic_table_owner"
            if any_lattice
            else "no_shared_source_cell_edges_in_both_axes"
        ),
        "positive_table_cell_authority": False,
        "physical_ceiling_or_material_authority": False,
        "view_separation_authority": False,
        "new_quantity_evidence": 0,
    }
