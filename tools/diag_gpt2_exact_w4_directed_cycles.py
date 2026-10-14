"""Exact original W4 directed ring-cycle census; no geometry repair.

A planar half-edge boundary walk can revisit an original source vertex,
traversing a nonzero-area nested loop and a reciprocal W4 bridge. Such a
walk is NOT a simple room polygon. This tool partitions only its existing
ordered, producer-owned directed edges into elementary closed walks and
reports their signed source area. It neither constructs nor publishes a
polygon, infers physical wall roles, closes an opening, or mints quantities.
"""
from __future__ import annotations

import math
from typing import Any

from pb_source_composite_room_face_authority import _edge_key

_MAX_EDGES = 256


def _valid_id(value: Any) -> bool:
    return type(value) is str and bool(value) and value == value.strip()


def _signed_area(vertices: tuple[tuple[float, float], ...]) -> float:
    return 0.5 * math.fsum(
        a[0] * b[1] - b[0] * a[1]
        for a, b in zip(vertices, vertices[1:] + vertices[:1])
    )


def inspect_exact_original_w4_directed_cycles(record: Any) -> dict[str, Any]:
    """Never turn multiple original signed loops into one manufactured room."""
    result: dict[str, Any] = {
        "status": "unavailable",
        "original_source_face_id": getattr(record, "face_id", None),
        "exact_source_wall_edges_owned": False,
        "directed_source_cycle_area_conserved": False,
        "original_source_edge_count": 0,
        "source_cycles_observed_only": [],
        "source_face_geometry_rewritten": False,
        "new_authenticated_physical_room_or_metric_quantity": False,
        "original_room_label_ownership_changed": False,
        "source_cycle_roles_are_unproven": True,
    }
    raw = getattr(record, "polygon_pdf_pts", ())
    receipts = getattr(record, "boundary_wall_edges", ())
    if not isinstance(raw, (tuple, list)) or not isinstance(
        receipts, (tuple, list)
    ):
        result["status"] = "missing_original_producer_boundary"
        return result
    if len(raw) < 3 or len(raw) > _MAX_EDGES or len(raw) != len(receipts):
        result["status"] = "original_boundary_receipt_count_or_safety_bound"
        return result
    points = []
    for point in raw:
        if not isinstance(point, (tuple, list)) or len(point) != 2:
            result["status"] = "original_source_vertex_invalid"
            return result
        try:
            x, y = float(point[0]), float(point[1])
        except (ValueError, TypeError, OverflowError):
            result["status"] = "original_source_vertex_invalid"
            return result
        if not math.isfinite(x) or not math.isfinite(y):
            result["status"] = "original_source_vertex_invalid"
            return result
        points.append((x, y))
    vertices = tuple(points)
    owners = []
    for idx, receipt in enumerate(receipts):
        if not isinstance(receipt, (tuple, list)) or len(receipt) != 2:
            result["status"] = "original_w4_source_receipt_invalid"
            return result
        wall, edge = receipt
        claimed = _edge_key(edge)
        original = _edge_key((
            vertices[idx], vertices[(idx + 1) % len(vertices)]
        ))
        if (not _valid_id(wall) or claimed is None or original is None
                or claimed != original):
            result["status"] = "original_w4_source_receipt_mismatch"
            return result
        owners.append(wall)
    result["original_source_edge_count"] = len(vertices)
    result["exact_source_wall_edges_owned"] = True

    # A stack partitions repeated *exact* source vertices without removing
    # even one directed W4 edge or inventing an intersection point.
    stack = [vertices[0]]
    active_edges = []
    cycles = []
    for index, destination in enumerate(vertices[1:] + vertices[:1]):
        if destination in stack:
            first = stack.index(destination)
            indices = active_edges[first:] + [index]
            ring = tuple(stack[first:])
            # A->B->A is a zero signed area retrace, not a room or hole.
            signed = _signed_area(ring) if len(ring) >= 3 else 0.0
            cycles.append({
                "source_edge_indexes": indices,
                "source_w4_wall_candidate_ids": [owners[i] for i in indices],
                "source_cycle_vertex_count": len(ring),
                "signed_area_pdf_pt2_observed_only": signed,
                "zero_area_retrace_only": math.isclose(
                    signed, 0.0, rel_tol=0.0, abs_tol=1e-8
                ),
                "physical_shell_hole_or_separator_role_authenticated": False,
                "source_cycle_may_be_published_as_room": False,
            })
            stack = stack[:first + 1]
            active_edges = active_edges[:first]
        else:
            stack.append(destination)
            active_edges.append(index)
    edge_ids = [idx for cycle in cycles for idx in cycle["source_edge_indexes"]]
    if (stack != [vertices[0]] or active_edges
            or sorted(edge_ids) != list(range(len(vertices)))):
        result["status"] = "source_directed_boundary_partition_incomplete"
        return result
    original_signed = _signed_area(vertices)
    cycle_signed = math.fsum(
        cycle["signed_area_pdf_pt2_observed_only"] for cycle in cycles
    )
    original_area = getattr(record, "area_page_pts2", None)
    if (type(original_area) not in (int, float)
            or not math.isfinite(float(original_area))
            or not math.isclose(abs(original_signed), float(original_area),
                                rel_tol=1e-10, abs_tol=1e-5)
            or not math.isclose(original_signed, cycle_signed,
                                rel_tol=1e-10, abs_tol=1e-5)):
        result["status"] = "original_signed_source_area_unverified"
        return result
    result["original_signed_walk_area_pdf_pt2"] = original_signed
    result["source_directed_cycle_count"] = len(cycles)
    result["source_nonzero_area_cycle_count"] = sum(
        not item["zero_area_retrace_only"] for item in cycles
    )
    result["directed_source_cycle_area_conserved"] = True
    result["source_cycles_observed_only"] = cycles
    result["status"] = "exact_original_w4_directed_cycles_observed_not_room"
    return result
