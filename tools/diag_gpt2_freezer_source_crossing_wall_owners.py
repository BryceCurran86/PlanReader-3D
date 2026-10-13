"""Read-only original producer W4 edge receipts at a self-crossing room ring.

A planarized source face may retain exact subedge-to-W4 addresses, but a W4
address is not physical-wall equivalence, a repair instruction, metric scale,
or valid room closure. This diagnostic never modifies source authority.
"""
from __future__ import annotations

import math
from collections import Counter

from pb_source_room_face_authority import SourceRoomFaceRecord
from tools.diag_gpt2_source_room_handoff_integrity import (
    original_polygon_first_failure_receipt,
)


def _source_edge_key(value):
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        return None
    points = []
    for point in value:
        if not isinstance(point, (tuple, list)) or len(point) != 2:
            return None
        if any(type(v) not in (int, float) for v in point):
            return None
        try:
            if any(not math.isfinite(v) for v in point):
                return None
            points.append(tuple(round(float(v), 6) for v in point))
        except (ValueError, TypeError, OverflowError):
            return None
    if points[0] == points[1]:
        return None
    return tuple(sorted(points))


def source_room_ring_crossing_wall_owner_census(record):
    """Audit producer-indexed source wall ownership; no guessed owner selection."""
    output = {
        "source_room_face_record_id": None,
        "first_source_gate": "original_source_face_record_unavailable",
        "original_polygon_crossing_edges_diagnostic_only": [],
        "indexed_original_w4_wall_owner_receipts": [],
        "source_crossing_wall_roles_authenticated": False,
        "source_crossing_physical_wall_equivalence_authenticated": False,
        "source_room_polygon_repaired": False,
        "source_room_metric_area_published": False,
        "diagnostic_only": True,
    }
    if type(record) is not SourceRoomFaceRecord:
        return output
    output["source_room_face_record_id"] = record.record_id
    crossing = original_polygon_first_failure_receipt(record)
    observed = crossing.get("original_native_source_ring_crossing_diagnostic_only")
    if (
        crossing["first_source_polygon_gate_diagnostic_only"]
        != "source_native_polygon_invalid"
        or not isinstance(observed, dict)
        or observed.get("first_source_crossing_gate_diagnostic_only")
        != "original_nonadjacent_ring_edges_intersect_role_unproven"
    ):
        output["first_source_gate"] = "original_source_ring_crossing_not_verified"
        return output
    edge_indices = observed.get("original_ring_crossing_edge_indices", ())
    edges = observed.get("original_ring_crossing_edge_pdf_pts", ())
    if (
        not isinstance(edges, list) or len(edges) != 2
        or not isinstance(edge_indices, list) or len(edge_indices) != 2
        or any(type(i) is not int for i in edge_indices)
    ):
        output["first_source_gate"] = "original_source_crossing_receipt_malformed"
        return output
    output["original_polygon_crossing_edges_diagnostic_only"] = [
        {"source_ring_edge_index": index, "edge_pdf_pts": edge}
        for index, edge in zip(edge_indices, edges)
    ]
    raw = record.boundary_wall_edges
    if not isinstance(raw, (tuple, list)):
        output["first_source_gate"] = "original_boundary_wall_edge_receipts_unavailable"
        return output
    owner_index = {}
    malformed = False
    for receipt in raw:
        if not isinstance(receipt, (tuple, list)) or len(receipt) != 2:
            malformed = True
            continue
        owner, edge = receipt
        native_key = _source_edge_key(edge)
        if (
            not isinstance(owner, str) or not owner
            or owner != owner.strip() or native_key is None
            or owner not in record.bounding_wall_ids
        ):
            malformed = True
            continue
        owner_index.setdefault(native_key, []).append(owner)
    if malformed:
        output["first_source_gate"] = "original_source_boundary_owner_receipt_invalid"
        return output
    found = []
    for item in output["original_polygon_crossing_edges_diagnostic_only"]:
        key = _source_edge_key(item["edge_pdf_pts"])
        matches = tuple(owner_index.get(key, ())) if key is not None else ()
        unique = len(matches) == 1
        found.append({
            "source_ring_edge_index": item["source_ring_edge_index"],
            "original_exact_edge_pdf_pts": item["edge_pdf_pts"],
            "original_indexed_w4_wall_candidate_ids": sorted(set(matches)),
            "exact_source_boundary_edge_owner_count": len(matches),
            "unique_original_indexed_w4_owner_receipt": unique,
            "distinct_original_w4_candidate_id_count": len(set(matches)),
            "repeated_same_w4_candidate_address_diagnostic_only": len(matches)>1 and len(set(matches))==1,
            "competing_distinct_w4_candidate_addresses_diagnostic_only": len(set(matches))>1,
            "second_physical_room_face_proven": False,
        })
    output["indexed_original_w4_wall_owner_receipts"] = found
    counts = Counter(
        "unique" if row["unique_original_indexed_w4_owner_receipt"]
        else "missing" if row["exact_source_boundary_edge_owner_count"] == 0
        else "ambiguous"
        for row in found
    )
    output["first_source_gate"] = (
        "both_original_ring_edges_have_exact_w4_receipts_crossing_unresolved"
        if counts["unique"] == 2
        else "original_ring_crossing_edge_w4_receipt_missing_or_ambiguous"
    )
    return output
