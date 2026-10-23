"""Exact geometry identity: segment-parent lines ↔ W4 centerline edges (shadow).

Not digit-tail. Not nearest. Retain every exact match; abstain on 0 or >1
distinct wall candidates. Never grants host.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isclose
from typing import Any


_ABS = 1e-6
_REL = 1e-9


def _clean(value: object) -> str:
    return str(value or "").strip()


def _finite_line(coords: object) -> tuple[float, float, float, float] | None:
    if not isinstance(coords, (list, tuple)) or len(coords) != 4:
        return None
    try:
        vals = tuple(float(v) for v in coords)
    except (TypeError, ValueError):
        return None
    if not all(v == v and abs(v) != float("inf") for v in vals):
        return None
    if vals[0] == vals[2] and vals[1] == vals[3]:
        return None
    return vals  # type: ignore[return-value]


def canonicalize_line_endpoints(
    line: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    """Order endpoints so undirected identity compares stably."""
    x0, y0, x1, y1 = line
    a = (x0, y0, x1, y1)
    b = (x1, y1, x0, y0)
    return a if a <= b else b


def lines_exactly_equal(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> bool:
    la = canonicalize_line_endpoints(left)
    ra = canonicalize_line_endpoints(right)
    return all(isclose(a, b, rel_tol=_REL, abs_tol=_ABS) for a, b in zip(la, ra))


def w4_centerline_edge_lines(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Extract undirected centerline edges from wall-candidate record mappings."""
    edges: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise TypeError("wall record must be a mapping")
        wid = _clean(record.get("wall_candidate_id"))
        if not wid:
            raise ValueError("wall_candidate_id required")
        pts = record.get("centerline_pts") or ()
        primitives = tuple(
            sorted(_clean(p) for p in (record.get("source_primitive_ids") or ()) if _clean(p))
        )
        if not isinstance(pts, (list, tuple)) or len(pts) < 2:
            continue
        for i in range(len(pts) - 1):
            try:
                x0, y0 = float(pts[i][0]), float(pts[i][1])
                x1, y1 = float(pts[i + 1][0]), float(pts[i + 1][1])
            except (TypeError, ValueError, IndexError):
                continue
            line = _finite_line((x0, y0, x1, y1))
            if line is None:
                continue
            edges.append({
                "wall_candidate_id": wid,
                "edge_index": i,
                "record_index": index,
                "line_pt": list(canonicalize_line_endpoints(line)),
                "source_primitive_ids": list(primitives),
            })
    return edges


def assess_segment_w4_exact_geometry_identity_shadow(
    *,
    physical_opening_id: str,
    segment_lines_by_id: Mapping[str, Sequence[float]],
    w4_wall_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    oid = _clean(physical_opening_id)
    if not oid:
        raise ValueError("physical opening identity required")

    segment_rows: list[dict[str, Any]] = []
    for sid, coords in sorted(segment_lines_by_id.items()):
        line = _finite_line(coords)
        if line is None:
            continue
        segment_rows.append({
            "segment_line_id": _clean(sid),
            "line_pt": list(canonicalize_line_endpoints(line)),
        })

    edges = w4_centerline_edge_lines(w4_wall_records)
    matches: list[dict[str, Any]] = []
    for seg in segment_rows:
        seg_line = tuple(seg["line_pt"])  # type: ignore[arg-type]
        for edge in edges:
            edge_line = tuple(edge["line_pt"])  # type: ignore[arg-type]
            if lines_exactly_equal(seg_line, edge_line):  # type: ignore[arg-type]
                matches.append({
                    "segment_line_id": seg["segment_line_id"],
                    "wall_candidate_id": edge["wall_candidate_id"],
                    "edge_index": edge["edge_index"],
                    "w4_source_primitive_ids": edge["source_primitive_ids"],
                    "line_pt": seg["line_pt"],
                })

    wall_ids = sorted({m["wall_candidate_id"] for m in matches})
    if not segment_rows:
        gate = "segment_lines_empty"
    elif not edges:
        gate = "w4_centerline_edges_unavailable"
    elif not matches:
        gate = "exact_geometry_identity_unavailable"
    elif len(wall_ids) > 1:
        gate = "exact_geometry_identity_ambiguous_multi_wall"
    else:
        # Unique wall candidate with ≥1 exact edge match — still review only.
        gate = "exact_geometry_identity_unique_wall_review_only"

    return {
        "physical_opening_id": oid,
        "first_remaining_gate": gate,
        "segment_line_count": len(segment_rows),
        "w4_centerline_edge_count": len(edges),
        "exact_match_count": len(matches),
        "matched_wall_candidate_ids": wall_ids,
        "matches_sample": matches[:16],
        "selected_wall_candidate_id": None,
        "nearest_wins_applied": False,
        "digit_tail_used": False,
        "host_granted": False,
        "measurement_published": False,
        "shadow_only": True,
    }


def summarize_exact_geometry_rows(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    from collections import Counter
    gates: Counter[str] = Counter()
    total_matches = 0
    for row in rows:
        gates[str(row.get("first_remaining_gate") or "")] += 1
        total_matches += int(row.get("exact_match_count") or 0)
    return {
        "status": "UNPUBLISHED_SEGMENT_W4_EXACT_GEOMETRY_SUMMARY",
        "opening_count": len(rows),
        "gate_counts": dict(sorted(gates.items())),
        "total_exact_match_hits": total_matches,
        "host_granted": False,
        "shadow_only": True,
    }
