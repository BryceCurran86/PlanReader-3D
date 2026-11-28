"""Report only (MAX 7236570478): which edges of a room ring may carry finished wall faces.

Takes a ring and its row from ``pb_ring_wall_identity_map_shadow.ring_wall_identity_map`` (existing evidence, no new
geometry rule). Each edge is a published wall face, an ambiguous wall face (only unpublished walls), a doorway closure
or has no wall candidate. A jog -- the outline leaving a face line and returning to the same line -- with any edge that
has no wall candidate is one unverified jog (equipment outlines often make these; a drawn wall nib carries wall
candidates). Interior holes are unverified obstacles: column or equipment is not decided here. Finished-face wall
quantities stay ABSTAINED unless every non-closure edge is a published wall face and there is no hole.
No quantity, area or promotion; nothing on a live path imports this.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from pb_layered_wall_doorway_room_ring_shadow import NOISE_PT
from pb_migration_contracts import EvidenceResolutionStatus
from pb_ring_wall_identity_map_shadow import (
    AMBIGUOUS_ONLY,
    CLOSURE_EDGE,
    NO_WALL,
    PUBLISHED,
)

PUBLISHED_FACE = "published_wall_face"
AMBIGUOUS_FACE = "ambiguous_wall_face"
DOORWAY = "doorway_closure"
NO_CANDIDATE = "no_wall_candidate"
UNVERIFIED_JOG = "unverified_jog"
_CLASS = {PUBLISHED: PUBLISHED_FACE, AMBIGUOUS_ONLY: AMBIGUOUS_FACE, CLOSURE_EDGE: DOORWAY, NO_WALL: NO_CANDIDATE}
_TOL = NOISE_PT * 2


def _points(polygon: Sequence[Sequence[float]]) -> list[tuple[float, float]]:
    points = [(float(x), float(y)) for x, y in polygon]
    if len(points) > 1 and points[0] == points[-1]:
        points.pop()
    return points


def _on_line(a, b, p) -> bool:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    return length > _TOL and abs((p[0] - a[0]) * dy - (p[1] - a[1]) * dx) / length <= _TOL


def _jogs(points: list) -> list[tuple[int, int, int]]:
    """Edge index triples (leave, along, return) whose neighbours before and after lie on one face line."""
    n = len(points)
    found = []
    if n < 7:
        return found
    for i in range(n):
        before, leave, along, back, after = ((i - 1) % n, i, (i + 1) % n, (i + 2) % n, (i + 3) % n)
        a, b = points[before], points[(before + 1) % n]
        e, f = points[after], points[(after + 1) % n]
        if not (_on_line(a, b, e) and _on_line(a, b, f)):
            continue
        if (b[0] - a[0]) * (f[0] - e[0]) + (b[1] - a[1]) * (f[1] - e[1]) <= 0:
            continue  # the face must carry on in the same direction
        p, q = points[along], points[(along + 1) % n]
        if _on_line(a, b, p) or _on_line(a, b, q):
            continue  # the middle edge must be off the face line
        found.append((leave, along, back))
    return found


def ring_finish_face_edge_classes(polygon: Sequence[Sequence[float]], wall_map_row: Mapping[str, Any], *,
                                  hole_count: int) -> dict[str, Any]:
    points = _points(polygon)
    edges = list(wall_map_row["edges"])
    if len(edges) != len(points) or type(hole_count) is not int or hole_count < 0:
        raise ValueError("ring, wall map row and hole count must describe one ring")
    classes = [_CLASS[edge["kind"]] for edge in edges]
    for triple in _jogs(points):
        if any(edges[i]["kind"] == NO_WALL for i in triple) and all(edges[i]["kind"] != CLOSURE_EDGE for i in triple):
            for i in triple:
                classes[i] = UNVERIFIED_JOG
    lengths: dict[str, float] = {}
    for (a, b), kind in zip(zip(points, points[1:] + points[:1]), classes):
        lengths[kind] = lengths.get(kind, 0.0) + math.dist(a, b)
    complete = hole_count == 0 and all(kind in (PUBLISHED_FACE, DOORWAY) for kind in classes)
    return {
        "status": EvidenceResolutionStatus.CANDIDATE if complete else EvidenceResolutionStatus.ABSTAINED,
        "edge_classes": tuple(classes),
        "length_pt_by_class": {kind: lengths[kind] for kind in sorted(lengths)},
        "unverified_interior_obstacles": hole_count,
        "finished_face_quantity_authority": False,
    }
