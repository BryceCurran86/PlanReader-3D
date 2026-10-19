"""Read-only GPT2 W2/W4 source-edge ring checker, never wall/room authority.

A complete geometric loop is necessary but not sufficient: furniture and
dimension rectangles also close. Producer authenticity of each edge and W4
physical wall membership must be reproven independently at the source owner.
"""
from __future__ import annotations

from collections import defaultdict
import math
import re


def _point(p):
    if (not isinstance(p, (tuple, list)) or len(p) != 2
            or any(type(c) not in (int, float) or not math.isfinite(c)
                   for c in p)):
        raise ValueError("source endpoint must be finite numeric pair")
    return tuple(
        0.0 if round(c, 6) == 0 else round(c, 6) for c in p
    )


def _cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _intersect(a, b, c, d):
    def on(p, q, r):
        return (min(p[0], q[0]) <= r[0] <= max(p[0], q[0])
                and min(p[1], q[1]) <= r[1] <= max(p[1], q[1]))
    p, q, r, s = _cross(a, b, c), _cross(a, b, d), _cross(c, d, a), _cross(c, d, b)
    if p * q < 0 and r * s < 0:
        return True
    return any(o == 0 and on(x, y, z) for o, x, y, z in (
        (p, a, b, c), (q, a, b, d), (r, c, d, a), (s, c, d, b)
    ))


def audit_source_ring(edges: list[dict], *, source_sha256: str,
                      page_id: str, snapshot_id: str,
                      decision_scope_id: str) -> dict:
    """Audit exact candidate ring; fail closed for open passages/competitors."""
    if (type(source_sha256) is not str
            or re.fullmatch(r"[0-9a-f]{64}", source_sha256) is None
            or any(type(x) is not str or not x.strip() for x in (
                page_id, snapshot_id, decision_scope_id
            ))):
        raise ValueError("source SHA/page/snapshot/decision scope required")
    if type(edges) is not list:
        raise TypeError("original source edge receipts must be list")

    vertices = defaultdict(list)
    by_id = {}
    reasons = set()
    received = []
    for edge in edges:
        if not isinstance(edge, dict):
            raise TypeError("source edge receipt must be mapping")
        eid = edge.get("edge_id")
        if type(eid) is not str or not eid.strip() or eid in by_id:
            reasons.add("source_edge_id_missing_or_reused")
            continue
        by_id[eid] = edge
        pts = edge.get("points")
        try:
            if not isinstance(pts, (tuple, list)) or len(pts) != 2:
                raise ValueError("two endpoints required")
            a, b = _point(pts[0]), _point(pts[1])
        except ValueError:
            reasons.add("original_source_segment_geometry_unavailable")
            continue
        if a == b:
            reasons.add("zero_length_original_source_edge")
            continue
        parents = edge.get("source_primitive_ids")
        if (not isinstance(parents, (tuple, list)) or not parents
                or any(type(z) is not str or not z.strip() for z in parents)
                or len(set(parents)) != len(parents)):
            reasons.add("source_edge_ancestry_not_authenticated")
        wall = edge.get("wall_candidate_id")
        if type(wall) is not str or not wall.strip():
            reasons.add("structural_wall_candidate_address_missing")
        for key, expected in (
            ("source_sha256", source_sha256),
            ("page_id", page_id),
            ("snapshot_id", snapshot_id),
            ("decision_scope_id", decision_scope_id),
        ):
            if edge.get(key) != expected:
                reasons.add("source_edge_scope_or_snapshot_conflict")
        received.append((eid, a, b, wall))
        vertices[a].append(eid)
        vertices[b].append(eid)
    if len(received) != len(edges):
        reasons.add("source_edge_membership_incomplete")
    if len(received) < 3:
        reasons.add("source_ring_too_few_edges")
    if any(len(ids) != 2 or len(set(ids)) != 2 for ids in vertices.values()):
        reasons.add("open_passage_or_branch_endpoint_degree_not_two")
    geometry = defaultdict(list)
    for eid, a, b, wall in received:
        geometry[tuple(sorted((a, b)))].append((eid, wall))
    if any(len(owners) > 1 for owners in geometry.values()):
        reasons.add("coincident_source_edges_compete_for_wall_owner")
    for i, (_, a, b, _) in enumerate(received):
        for _, c, d, _ in received[i + 1:]:
            if {a, b} == {c, d}:
                continue
            shared = set((a, b)).intersection((c, d))
            if _intersect(a, b, c, d) and not shared:
                reasons.add("self_intersecting_source_room_perimeter")
            elif _intersect(a, b, c, d) and shared:
                ab = next((p for p in (a, b) if p not in shared), None)
                cd = next((p for p in (c, d) if p not in shared), None)
                if (ab is not None and cd is not None
                        and _cross(a, b, c) == 0
                        and _cross(a, b, d) == 0
                        and (min(a, b) <= cd <= max(a, b)
                             or min(c, d) <= ab <= max(c, d))):
                    reasons.add("overlapping_source_boundary_segments")

    ordered = []
    if not reasons and vertices:
        start = min(vertices)
        current = start
        used = set()
        lookup = {eid: (a, b) for eid, a, b, _ in received}
        for _ in received:
            possible = [eid for eid in vertices[current] if eid not in used]
            if len(possible) != 1 and used:
                reasons.add("source_cycle_chain_ambiguous")
                break
            if not possible:
                reasons.add("source_cycle_chain_incomplete")
                break
            eid = min(possible)
            used.add(eid)
            a, b = lookup[eid]
            ordered.append(current)
            current = b if a == current else a
        if current != start or len(used) != len(received):
            reasons.add("disconnected_or_multiple_source_cycles")
    if ordered and not reasons:
        signed = sum(a[0] * b[1] - b[0] * a[1]
                     for a, b in zip(ordered, ordered[1:] + ordered[:1]))
        if signed == 0:
            reasons.add("source_boundary_area_degenerate")

    return {
        "source_sha256": source_sha256, "page_id": page_id,
        "snapshot_id": snapshot_id, "decision_scope_id": decision_scope_id,
        "source_edge_ids": sorted(by_id), "source_edge_count": len(edges),
        "status": "ABSTAINED" if reasons else "CANDIDATE",
        "blocking_reasons": sorted(reasons),
        "geometry_ring_vertices_page_points": ordered if not reasons else None,
        "physical_room_boundary_authority": False,
        "original_source_membership_reproven": False,
        "source_only_positive_wall_role_required": True,
        "source_finish_area_ceiling_or_count_granted": False,
    }
