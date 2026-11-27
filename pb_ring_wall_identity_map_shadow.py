"""Report only (#4764 7219675205, tasks C06/C08): which physical wall candidates are drawn on each layered ring edge?

See docs/engineering/claude_c06_c08_ring_wall_map_note_20261127.md. A candidate belongs to a ring edge only when one of its
source primitives is on one of the edge's owner paths AND its centreline lies on the edge line with a positive shared length.
No nearest or longest choice is made; closure edges are never walls. Nothing here publishes, promotes or changes anything,
and nothing on a live path imports it.
"""
from __future__ import annotations

import math

from pb_layered_wall_doorway_room_ring_shadow import NOISE_PT

CLOSURE_EDGE = "closure"
PUBLISHED = "published_wall"
AMBIGUOUS_ONLY = "only_unpublished_walls"
NO_WALL = "no_wall_candidate"
_STRIP, _FILL, _CLOSURE = "layered_wall_strip:", "layered_wall_fill:", "layered_doorway_closure:"


def _owner_paths(owners) -> set[int]:
    return {int(owner.split(":", 1)[1]) for owner in owners if owner.startswith((_STRIP, _FILL))}


def _primitive_path(primitive: str) -> int | None:
    head = primitive[1:].split("i", 1)[0] if primitive.startswith("d") else ""
    return int(head) if head.isdigit() else None


def _shared_length_on_edge(a, b, points, tolerance: float) -> float:
    """Length of the candidate's own segments lying on the edge line and overlapping the edge."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length <= tolerance:
        return 0.0
    ux, uy = dx / length, dy / length
    shared = 0.0
    for p, q in zip(points, points[1:]):
        offsets = [abs((x - a[0]) * -uy + (y - a[1]) * ux) for x, y in (p, q)]
        if max(offsets) > tolerance:
            continue
        along = sorted((x - a[0]) * ux + (y - a[1]) * uy for x, y in (p, q))
        shared += max(0.0, min(along[1], length) - max(along[0], 0.0))
    return shared


def ring_wall_identity_map(rings, wall_scope) -> list[dict]:
    """Per candidate ring: each edge's matching physical wall candidates and whether any of them publishes."""
    equivalence = wall_scope.equivalence
    published = set(equivalence.representative_wall_ids) if equivalence is not None else set()
    walls_by_path: dict[int, list] = {}
    for record in wall_scope.records:
        for primitive in record.physical_identity.source_primitive_ids:
            path = _primitive_path(str(primitive))
            if path is not None:
                walls_by_path.setdefault(path, []).append(record)
    tolerance = NOISE_PT * 2
    rows = []
    for ring in rings:
        points = [tuple(p) for p in ring.polygon_pdf_pts]
        edges = []
        for (a, b), owners in zip(zip(points, points[1:] + points[:1]), ring.edge_owner_ids):
            if any(owner.startswith(_CLOSURE) for owner in owners):
                edges.append({"kind": CLOSURE_EDGE, "wall_ids": []})
                continue
            candidates = {}
            for path in _owner_paths(owners):
                for record in walls_by_path.get(path, ()):
                    wall = record.wall_candidate
                    if _shared_length_on_edge(a, b, [tuple(p) for p in wall.centerline_pts], tolerance) > tolerance:
                        candidates[record.wall_candidate_id] = record
            kind = NO_WALL if not candidates else PUBLISHED if set(candidates) & published else AMBIGUOUS_ONLY
            edges.append({"kind": kind, "wall_ids": sorted(candidates)})
        rows.append({
            "ring_record_id": ring.record_id,
            "status": ring.status.value,
            "edges": edges,
            "counts": {kind: sum(edge["kind"] == kind for edge in edges)
                       for kind in (PUBLISHED, AMBIGUOUS_ONLY, NO_WALL, CLOSURE_EDGE)},
        })
    return rows
