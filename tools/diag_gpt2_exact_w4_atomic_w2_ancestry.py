"""Read-only exact W4 atomic edge -> surviving W2/native primitive receipts.

A published SourceRoomFace W4 edge is NOT independently proven structural
wall authority. It can originate in multiple W2 fragments and source
primitives. Observe every original producer surviving edge fragment on ONE
exact selected W4 candidate, fail closed on collisions, and never elect a
physical room separator. No geometry, quantities or benchmark truth mutated.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from pb_source_composite_room_face_authority import _edge_key
from pb_source_room_face_authority import (
    _collinear_overlap_edge,
    _edge_contains_edge,
)

_MAX_W4 = 5000
_MAX_W2 = 1024
_MAX_RECEIPTS = 64


def _valid(value: object) -> bool:
    return type(value) is str and bool(value) and value == value.strip()


def _fragment_edge(fragment: object):
    data = getattr(fragment, "geometry", None)
    if not isinstance(data, (tuple, list)) or len(data) != 4:
        return None
    return _edge_key(((data[0], data[1]), (data[2], data[3])))


def _exact_w4_centerline_source_receipts(target: object, original_w4_wall_id: str,
                                         atomic: object) -> dict[str, Any]:
    """Compare authenticated indexed W4 centerline *segments*, not wall roles.

    Even a source-owned W4 centerline segment matching a proposed face subedge
    is not an original structural wall or permission to repair a room ring.
    """
    output = {
        "status": "w4_centerline_unavailable",
        "w4_centerline_source_segment_count": 0,
        "w4_centerline_full_span_receipts": [],
        "w4_centerline_partial_span_receipts": [],
        "source_w4_path_match_is_structural_wall_role": False,
        "source_room_face_repaired": False,
    }
    wall = getattr(target, "wall_candidate", None)
    if wall is None:
        return output
    if getattr(wall, "candidate_id", None) != original_w4_wall_id:
        output["status"] = "w4_centerline_candidate_identity_conflict"
        return output
    vertices = getattr(wall, "centerline_pts", None)
    if not isinstance(vertices, (tuple, list)) or not 2 <= len(vertices) <= 10000:
        output["status"] = "w4_centerline_invalid"
        return output
    points = []
    for item in vertices:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            output["status"] = "w4_centerline_invalid"
            return output
        if any(type(n) not in (int, float) for n in item):
            output["status"] = "w4_centerline_invalid"
            return output
        points.append(tuple(item))
    path = []
    for a, b in zip(points, points[1:]):
        edge = _edge_key((a, b))
        if edge is None:
            output["status"] = "w4_centerline_invalid"
            return output
        path.append(edge)
    output["w4_centerline_source_segment_count"] = len(path)
    full, partial = [], []
    for index, candidate in enumerate(path):
        receipt = {
            "original_w4_centerline_segment_index": index,
            "original_w4_centerline_segment_pdf_pts": [list(p) for p in candidate],
            "original_native_ink_or_structural_role_granted": False,
        }
        if _edge_contains_edge(candidate, atomic):
            full.append(receipt)
            continue
        overlap = _collinear_overlap_edge(candidate, atomic)
        if overlap is not None:
            receipt["positive_overlap_pdf_pts"] = [list(p) for p in overlap]
            partial.append(receipt)
    output["w4_centerline_full_span_receipts"] = full
    output["w4_centerline_partial_span_receipts"] = partial
    output["status"] = (
        "original_w4_centerline_full_span_observed"
        if full else
        "original_w4_centerline_partial_only"
        if partial else "original_w4_centerline_no_collinear_support"
    )
    return output


def inspect_original_w4_atomic_w2_ancestry(
    wall_scope: Any, *, original_w4_wall_id: str, atomic_edge: Any
) -> dict[str, Any]:
    """Report exact/partial W2 sources, *not* prove room or wall roles."""
    report = {
        "status": "source_unavailable",
        "original_w4_wall_id": original_w4_wall_id,
        "original_atomic_edge_pdf_pts": None,
        "w4_candidate_record_count": 0,
        "w2_source_fragment_full_edge_receipts": [],
        "w2_source_fragment_partial_overlap_receipts": [],
        "matched_source_w2_edge_count": 0,
        "rejected_original_w2_fragment_count": 0,
        "source_w2_receipts_truncated": False,
        "candidate_only_no_wall_or_room_authority": True,
        "physical_wall_role_or_w4_equivalence_proven": False,
        "physical_room_closed_or_metric_quantity_published": False,
        "original_source_primitive_universe_proven_complete": False,
        "w4_centerline_geometry_first_gate": {
            "status": "original_w4_unavailable",
            "source_w4_path_match_is_structural_wall_role": False,
            "source_room_face_repaired": False,
        },
        "first_unrepresented_geometry_stage_diagnostic_only": "UNAVAILABLE",
    }
    atomic = _edge_key(atomic_edge)
    if not _valid(original_w4_wall_id) or atomic is None:
        report["status"] = "invalid_exact_original_w4_query"
        return report
    report["original_atomic_edge_pdf_pts"] = [list(p) for p in atomic]
    records = tuple(getattr(wall_scope, "records", ()) or ())
    if len(records) > _MAX_W4:
        report["status"] = "w4_source_universe_safety_bound"
        return report
    counts = Counter(
        getattr(record, "wall_candidate_id", None) for record in records
        if _valid(getattr(record, "wall_candidate_id", None))
    )
    if any(not _valid(getattr(r, "wall_candidate_id", None)) for r in records):
        report["status"] = "original_w4_record_identity_invalid"
        return report
    report["w4_candidate_record_count"] = counts[original_w4_wall_id]
    if counts[original_w4_wall_id] != 1:
        report["status"] = (
            "original_w4_candidate_collision"
            if counts[original_w4_wall_id] else "original_w4_candidate_missing"
        )
        return report
    target = next(r for r in records if r.wall_candidate_id == original_w4_wall_id)
    report["w4_centerline_geometry_first_gate"] = (
        _exact_w4_centerline_source_receipts(target, original_w4_wall_id, atomic)
    )
    identity = getattr(target, "physical_identity", None)
    edge_ids = getattr(identity, "edge_ids", None)
    source_ids = getattr(identity, "source_primitive_ids", None)
    if (getattr(identity, "usable", False) is not True
            or getattr(identity, "wall_candidate_id", None) != original_w4_wall_id
            or not isinstance(edge_ids, (tuple, list, set, frozenset))
            or not edge_ids or any(not _valid(x) for x in edge_ids)
            or not isinstance(source_ids, (tuple, list, set, frozenset))
            or not source_ids or any(not _valid(x) for x in source_ids)):
        report["status"] = "original_w4_physical_identity_unverified"
        return report
    fragments = tuple(getattr(target, "source_edge_fragments", ()) or ())
    if len(fragments) > _MAX_W2:
        report["status"] = "original_w2_source_fragment_safety_bound"
        return report
    duplicate_edges = Counter(getattr(f, "edge_id", None) for f in fragments)
    if any(c != 1 for c in duplicate_edges.values()):
        report["status"] = "duplicate_surviving_w2_source_identity"
        return report
    full, partial = [], []
    for fragment in fragments:
        fragment_id = getattr(fragment, "edge_id", None)
        native = getattr(fragment, "source_primitive_ids", None)
        geometry = _fragment_edge(fragment)
        if (not _valid(fragment_id) or fragment_id not in edge_ids
                or not isinstance(native, (tuple, list)) or not native
                or any(not _valid(x) for x in native)
                or len(native) != len(set(native))
                or not set(native).issubset(source_ids)
                or geometry is None):
            report["rejected_original_w2_fragment_count"] += 1
            continue
        contains = _edge_contains_edge(geometry, atomic)
        overlap = None if contains else _collinear_overlap_edge(geometry, atomic)
        if not contains and overlap is None:
            continue
        receipt = {
            "original_w2_edge_id": fragment_id,
            "original_native_source_primitive_ids": list(native),
            "original_w2_fragment_edge_pdf_pts": [list(p) for p in geometry],
            "source_primitive_is_a_physical_wall_proven": False,
        }
        if contains:
            receipt["original_atomic_edge_fully_covered_by_w2"] = True
            full.append(receipt)
        else:
            receipt["original_atomic_edge_fully_covered_by_w2"] = False
            receipt["positive_collinear_overlap_pdf_pts"] = [
                list(p) for p in overlap
            ]
            partial.append(receipt)
    full.sort(key=lambda r:r["original_w2_edge_id"])
    partial.sort(key=lambda r:r["original_w2_edge_id"])
    report["w2_source_fragment_full_edge_receipts"] = full[:_MAX_RECEIPTS]
    report["w2_source_fragment_partial_overlap_receipts"] = partial[:_MAX_RECEIPTS]
    report["matched_source_w2_edge_count"] = len(full) + len(partial)
    report["source_w2_receipts_truncated"] = (
        len(full) > _MAX_RECEIPTS or len(partial) > _MAX_RECEIPTS
    )
    if report["rejected_original_w2_fragment_count"]:
        report["status"] = "original_w2_source_ancestry_conflict"
    elif report["source_w2_receipts_truncated"]:
        report["status"] = "original_w2_source_ancestry_truncated"
    elif len(full) == 1 and not partial:
        report["status"] = "one_original_w2_source_fragment_observed"
    elif len(full) > 1 or (full and partial) or len(partial) > 1:
        report["status"] = "plural_original_w2_source_fragments_observed"
    elif partial:
        report["status"] = "partial_original_w2_source_overlap_only"
    else:
        report["status"] = "no_original_w2_fragment_covering_selected_atomic_edge"
    w4 = report["w4_centerline_geometry_first_gate"]
    if report["status"] == "no_original_w2_fragment_covering_selected_atomic_edge":
        if w4["status"] == "original_w4_centerline_full_span_observed":
            report["first_unrepresented_geometry_stage_diagnostic_only"] = (
                "W2_SOURCE_FRAGMENTS_TO_W4_CENTERLINE"
            )
        elif w4["status"] == "original_w4_centerline_no_collinear_support":
            report["first_unrepresented_geometry_stage_diagnostic_only"] = (
                "W4_CENTERLINE_TO_FACE_SUBEDGE"
            )
    elif w4["status"] == "original_w4_centerline_full_span_observed":
        report["first_unrepresented_geometry_stage_diagnostic_only"] = (
            "BOTH_W2_SOURCE_AND_W4_GEOMETRY_OBSERVED_NOT_WALL_AUTHORITY"
        )
    return report
