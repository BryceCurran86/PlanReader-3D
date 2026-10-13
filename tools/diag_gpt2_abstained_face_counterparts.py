"""Read-only source room-face counterpart audit for one original W4 atomic edge.

This does not construct faces, elect physical walls, modify source edges,
override withheld faces, authenticate a second side, or publish quantities.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from pb_source_composite_room_face_authority import _edge_key
from pb_source_room_face_authority import (
    _collinear_overlap_edge, _edge_contains_edge,
)

_MAX_FACE_UNIVERSE = 5000
_MAX_OBSERVATIONS = 32


def _valid_id(value: object) -> bool:
    return type(value) is str and bool(value) and value == value.strip()


def inspect_unpublished_source_face_counterparts(
    room_scope: Any, *, wall_id: str, atomic_edge: Any,
    known_component_face_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Observe original published/withheld faces, never infer opposite-side ownership."""
    result: dict[str, Any] = {
        "status": "unavailable",
        "original_w4_wall_id": wall_id,
        "native_atomic_edge_pdf_pts": None,
        "candidate_only_no_second_side_authority": True,
        "source_room_face_universe_complete": False,
        "second_physical_source_face_authenticated": False,
        "rejected_source_receipt_count": 0,
        "all_matching_receipts_observed": False,
        "matching_published_face_receipts": [],
        "matching_withheld_face_receipts": [],
        "matching_withheld_polygon_geometry_only": [],
    }
    atomic = _edge_key(atomic_edge)
    if (not _valid_id(wall_id) or atomic is None
            or any(not _valid_id(v) for v in known_component_face_ids)
            or len(set(known_component_face_ids)) != len(known_component_face_ids)):
        result["status"] = "invalid_source_query"
        return result
    result["native_atomic_edge_pdf_pts"] = [list(p) for p in atomic]
    published = tuple(getattr(room_scope, "records", ()) or ())
    withheld = tuple(getattr(room_scope, "abstained_faces", ()) or ())
    if len(published) + len(withheld) > _MAX_FACE_UNIVERSE:
        result["status"] = "face_source_universe_safety_bound"
        return result
    keys = [getattr(row, "face_id", None) for row in published + withheld]
    if any(not _valid_id(key) for key in keys) or any(
        v != 1 for v in Counter(keys).values()
    ):
        result["status"] = "ambiguous_original_source_face_identity"
        return result

    selected = set(known_component_face_ids)
    total_matches = 0
    for kind, rows in (("published", published), ("withheld", withheld)):
        for face in rows:
            face_id = face.face_id
            candidate_edges = tuple(getattr(face, "boundary_wall_edges", ()) or ())
            matched = []
            invalid = False
            for entry in candidate_edges:
                if not isinstance(entry, (tuple, list)) or len(entry) != 2:
                    invalid = True
                    continue
                parent_wall, edge_raw = entry
                if not _valid_id(parent_wall):
                    invalid = True
                    continue
                if parent_wall != wall_id:
                    continue
                edge = _edge_key(edge_raw)
                if edge is None:
                    invalid = True
                    continue
                full = _edge_contains_edge(edge, atomic)
                overlap = None if full else _collinear_overlap_edge(edge, atomic)
                if full or overlap is not None:
                    matched.append({
                        "original_w4_wall_id": parent_wall,
                        "exact_source_edge_pdf_pts": [list(p) for p in edge],
                        "full_atomic_coverage": full,
                        "partial_source_overlap_pdf_pts": (
                            None if overlap is None else [list(p) for p in overlap]
                        ),
                    })
            if invalid:
                result["rejected_source_receipt_count"] += 1
            if matched:
                total_matches += 1
                if total_matches <= _MAX_OBSERVATIONS:
                    result[
                        "matching_published_face_receipts" if kind == "published"
                        else "matching_withheld_face_receipts"
                    ].append({
                        "original_face_id": face_id,
                        "already_in_original_room_component": face_id in selected,
                        "source_publication_state": kind,
                        "withheld_reason": (
                            str(getattr(face, "reason", ""))
                            if kind == "withheld" else None
                        ),
                        "source_w4_subedges": matched[:_MAX_OBSERVATIONS],
                        "opposite_side_proven": False,
                    })
            elif kind == "withheld":
                # Geometry-only witness: no W4 claim is inferred from a
                # coincident polygon side, including abstained source faces.
                poly = tuple(getattr(face, "polygon_pdf_pts", ()) or ())
                overlaps = []
                if 3 <= len(poly) <= 500:
                    for left, right in zip(poly, poly[1:] + poly[:1]):
                        line = _edge_key((left, right))
                        if line is not None:
                            overlap = _collinear_overlap_edge(line, atomic)
                            if overlap is not None:
                                overlaps.append([list(p) for p in overlap])
                if overlaps:
                    total_matches += 1
                    if total_matches <= _MAX_OBSERVATIONS:
                        result["matching_withheld_polygon_geometry_only"].append({
                            "original_face_id": face_id,
                            "withheld_reason": str(getattr(face, "reason", "")),
                            "original_polygon_source_overlaps": overlaps[:8],
                            "no_authenticated_w4_owner_or_second_face": True,
                        })
    result["status"] = "original_face_source_candidates_only"
    result["all_matching_receipts_observed"] = (
        total_matches <= _MAX_OBSERVATIONS
        and result["rejected_source_receipt_count"] == 0
    )
    result["matching_original_face_count"] = total_matches
    return result
