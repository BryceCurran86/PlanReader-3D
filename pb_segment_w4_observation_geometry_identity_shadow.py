"""Identity between opening parent lines and W4-owned observation geometries.

Exact equality first; collinear positive-length overlap second. Retain every
matching wall. Never nearest, never host.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import hypot
from typing import Any

from pb_segment_w4_exact_geometry_identity_shadow import (
    _finite_line,
    canonicalize_line_endpoints,
    lines_exactly_equal,
)
from pb_w4_raster_segment_geometry_index_shadow import lookup_w4_primitive_geometries


_ABS = 1e-6
_REL = 1e-9


def _clean(value: object) -> str:
    return str(value or "").strip()


def collinear_overlap_length_pt(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> float | None:
    """Positive overlap length if segments share an infinite line; else None.

    Parallel-but-offset (gap) returns None. Does not pick a nearest line.
    """
    ax0, ay0, ax1, ay1 = canonicalize_line_endpoints(left)
    bx0, by0, bx1, by1 = canonicalize_line_endpoints(right)
    adx, ady = ax1 - ax0, ay1 - ay0
    bdx, bdy = bx1 - bx0, by1 - by0
    a_len = hypot(adx, ady)
    b_len = hypot(bdx, bdy)
    if a_len <= _ABS or b_len <= _ABS:
        return None
    cross = adx * bdy - ady * bdx
    if abs(cross) > _ABS * a_len * b_len / max(a_len, 1.0):
        # Not parallel.
        if abs(cross) / (a_len * b_len) > 1e-6:
            return None
    # Distance of B start to infinite line A.
    dist = abs((bx0 - ax0) * ady - (by0 - ay0) * adx) / a_len
    if dist > _ABS:
        return None
    # Project both onto A's unit axis.
    ux, uy = adx / a_len, ady / a_len

    def _proj(x: float, y: float) -> float:
        return (x - ax0) * ux + (y - ay0) * uy

    a0, a1 = sorted((_proj(ax0, ay0), _proj(ax1, ay1)))
    b0, b1 = sorted((_proj(bx0, by0), _proj(bx1, by1)))
    overlap = min(a1, b1) - max(a0, b0)
    if overlap <= _ABS:
        return None
    return overlap


def assess_segment_w4_observation_geometry_identity_shadow(
    *,
    physical_opening_id: str,
    segment_lines_by_id: Mapping[str, Sequence[float]],
    w4_wall_records: Sequence[Mapping[str, Any]],
    geometries_by_ref: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    oid = _clean(physical_opening_id)
    if not oid:
        raise ValueError("physical opening identity required")
    segments = []
    for sid, coords in sorted(segment_lines_by_id.items()):
        line = _finite_line(coords)
        if line is None:
            continue
        segments.append({"segment_line_id": _clean(sid), "line_pt": line})

    exact_matches: list[dict[str, Any]] = []
    overlap_matches: list[dict[str, Any]] = []
    walls_looked_up = 0
    primitives_with_geom = 0
    primitives_missing_geom = 0

    for record in w4_wall_records:
        if not isinstance(record, Mapping):
            raise TypeError("wall record must be a mapping")
        wid = _clean(record.get("wall_candidate_id"))
        if not wid:
            raise ValueError("wall_candidate_id required")
        walls_looked_up += 1
        lookup = lookup_w4_primitive_geometries(
            w4_source_primitive_ids=tuple(record.get("source_primitive_ids") or ()),
            geometries_by_ref=geometries_by_ref,
        )
        primitives_with_geom += lookup["matched_w4_primitive_geometry_count"]
        primitives_missing_geom += lookup["unmatched_w4_primitive_count"]
        for hit in lookup["hits"]:
            wline = _finite_line(hit["line_pt"])
            if wline is None:
                continue
            for seg in segments:
                sline = seg["line_pt"]
                if lines_exactly_equal(sline, wline):
                    exact_matches.append({
                        "segment_line_id": seg["segment_line_id"],
                        "wall_candidate_id": wid,
                        "w4_source_primitive_id": hit["w4_source_primitive_id"],
                        "match_kind": "exact_observation_geometry",
                    })
                    continue
                overlap = collinear_overlap_length_pt(sline, wline)
                if overlap is not None:
                    overlap_matches.append({
                        "segment_line_id": seg["segment_line_id"],
                        "wall_candidate_id": wid,
                        "w4_source_primitive_id": hit["w4_source_primitive_id"],
                        "match_kind": "collinear_overlap_observation_geometry",
                        "overlap_length_pt": overlap,
                    })

    exact_walls = sorted({m["wall_candidate_id"] for m in exact_matches})
    overlap_walls = sorted({m["wall_candidate_id"] for m in overlap_matches})
    if not segments:
        gate = "segment_lines_empty"
    elif not geometries_by_ref:
        gate = "observation_geometry_index_empty"
    elif exact_walls and len(exact_walls) == 1:
        gate = "exact_observation_geometry_unique_wall_review_only"
    elif len(exact_walls) > 1:
        gate = "exact_observation_geometry_ambiguous_multi_wall"
    elif overlap_walls and len(overlap_walls) == 1:
        gate = "collinear_overlap_unique_wall_review_only"
    elif len(overlap_walls) > 1:
        gate = "collinear_overlap_ambiguous_multi_wall"
    else:
        gate = "observation_geometry_identity_unavailable"

    return {
        "physical_opening_id": oid,
        "first_remaining_gate": gate,
        "segment_line_count": len(segments),
        "w4_walls_looked_up": walls_looked_up,
        "w4_primitives_with_indexed_geometry": primitives_with_geom,
        "w4_primitives_missing_indexed_geometry": primitives_missing_geom,
        "exact_match_count": len(exact_matches),
        "collinear_overlap_match_count": len(overlap_matches),
        "exact_matched_wall_candidate_ids": exact_walls,
        "overlap_matched_wall_candidate_ids": overlap_walls,
        "exact_matches_sample": exact_matches[:12],
        "overlap_matches_sample": overlap_matches[:12],
        "selected_wall_candidate_id": None,
        "nearest_wins_applied": False,
        "digit_tail_used": False,
        "host_granted": False,
        "measurement_published": False,
        "shadow_only": True,
    }


def summarize_observation_geometry_rows(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    from collections import Counter
    gates: Counter[str] = Counter()
    exact = 0
    overlap = 0
    for row in rows:
        gates[str(row.get("first_remaining_gate") or "")] += 1
        exact += int(row.get("exact_match_count") or 0)
        overlap += int(row.get("collinear_overlap_match_count") or 0)
    return {
        "status": "UNPUBLISHED_SEGMENT_W4_OBSERVATION_GEOMETRY_SUMMARY",
        "opening_count": len(rows),
        "gate_counts": dict(sorted(gates.items())),
        "total_exact_hits": exact,
        "total_collinear_overlap_hits": overlap,
        "host_granted": False,
        "shadow_only": True,
    }
