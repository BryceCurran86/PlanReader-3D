"""W4 path fingerprint + hybrid candidate identity helpers.

``pb_wall_room_topology_wall_assembly._canonical_wall_candidate_id`` now hashes
the direction-canonical, collinear-collapsed centerline
(``canonical_path_fingerprint``) so geometrically different chains that share
outer endpoints no longer collide. Assembly identity is geometry-only;
provenance is intentionally excluded there so legitimate re-chunking of one
physical path stays stable when fragment source ids differ.

``canonical_wall_candidate_id_v2`` remains the HYBRID (geometry + U1 provenance)
candidate-identity helper used by the physical-wall identity sidecar. It is
candidate identity only — not publication authority. Quantity publication
must continue to use physical equivalence separately and must not treat
``different V2 ID ⇒ different physical wall``.

DESIGN: path fingerprint (shared)
---------------------------------
``canonical_path_fingerprint``:
1. Round every vertex to a fixed precision (quantization — ordinary
   floating-point replay noise must not change identity).
2. Collapse redundant collinear interior vertices (three consecutive points
   where the middle one lies on the straight line through its neighbours
   are reduced to the two endpoints) — this is what makes the fingerprint
   insensitive to simple collinear re-chunking.
3. Canonical orientation: compare the point sequence forward against
   reversed, keep whichever sorts smaller — direction-invariant.

DESIGN: HYBRID identity (v2 sidecar only)
-----------------------------------------
Never provenance-ALONE and never geometry-ALONE. The v2 id hashes:

    (viewport_id, canonical_path_fingerprint(centerline), sorted
     provenance_ids_or_empty)

Provenance ids (sorted, deduped U1 ``source_primitive_ids`` unioned across
every contributing edge) are combined WITH this fingerprint, never used to
replace it.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from pb_migration_contracts import stable_contract_id
from pb_wall_room_topology_primitive_lineage import LINEAGE_KEY

_PATH_QUANTIZATION_NDIGITS = 6
# Collinearity tolerance for collapsing a redundant interior vertex: the
# cross-product-based perpendicular distance (in pt) of the middle point
# from the line through its neighbours. Deliberately generous relative to
# ordinary floating-point noise but far below any real architectural
# feature size -- not fitted to any project's own measurements.
_COLLINEAR_TOLERANCE_PT = 1e-4


def _chain_source_primitive_ids(edge_ids: Iterable[str], edges_by_id: Mapping[str, Mapping[str, Any]]) -> Tuple[str, ...]:
    ids: set = set()
    for edge_id in edge_ids:
        edge = edges_by_id.get(edge_id)
        if not edge:
            continue
        lineage = edge.get(LINEAGE_KEY) or {}
        for source_id in lineage.get("source_primitive_ids") or ():
            if source_id not in (None, ""):
                ids.add(str(source_id))
    return tuple(sorted(ids))


def _is_collinear(a: Tuple[float, float], b: Tuple[float, float], c: Tuple[float, float]) -> bool:
    cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    length_ac = math.hypot(c[0] - a[0], c[1] - a[1])
    if length_ac <= 1e-9:
        return True
    perpendicular_distance = abs(cross) / length_ac
    return perpendicular_distance <= _COLLINEAR_TOLERANCE_PT


def _collapse_collinear(points: Sequence[Tuple[float, float]]) -> Tuple[Tuple[float, float], ...]:
    """Standard collinear-run collapse: for each new point, if it and the
    previous TWO accepted points are collinear, the previous accepted point
    was a redundant interior vertex on the same straight run and is
    replaced (extending the run) rather than kept as a real corner."""
    if len(points) <= 2:
        return tuple(points)
    result = [points[0]]
    for point in points[1:]:
        if len(result) >= 2 and _is_collinear(result[-2], result[-1], point):
            result[-1] = point
        else:
            result.append(point)
    return tuple(result)


def canonical_path_fingerprint(
    points: Sequence[Tuple[float, float]], ndigits: int = _PATH_QUANTIZATION_NDIGITS
) -> Tuple[Tuple[float, float], ...]:
    """Direction-invariant, re-chunking-tolerant fingerprint of a wall's
    centerline path. See module docstring for the three-step algorithm."""
    quantized = tuple((round(float(x), ndigits), round(float(y), ndigits)) for x, y in points)
    collapsed = _collapse_collinear(quantized)
    reversed_collapsed = tuple(reversed(collapsed))
    return min(collapsed, reversed_collapsed)


def _path_from_edges(
    edge_ids: Sequence[str],
    edges_by_id: Mapping[str, Mapping[str, Any]],
    p1: Tuple[float, float],
    p2: Tuple[float, float],
) -> Tuple[Tuple[float, float], ...]:
    """Reconstruct the chain's own actual interior polyline from its
    contributing edges' own coordinates, walking shared endpoints -- NOT
    just the two boundary points. Falls back to (p1, p2) when edge
    coordinates are unavailable or when the edges do not form one clean
    simple path — never guesses a partial reconstruction.
    """
    raw_segments: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
    for edge_id in edge_ids:
        edge = edges_by_id.get(edge_id) or {}
        try:
            x1, y1 = float(edge["x1"]), float(edge["y1"])
            x2, y2 = float(edge["x2"]), float(edge["y2"])
        except (KeyError, TypeError, ValueError):
            return (p1, p2)
        raw_segments.append(((x1, y1), (x2, y2)))

    if not raw_segments:
        return (p1, p2)
    if len(raw_segments) == 1:
        return raw_segments[0]

    def _round_key(point: Tuple[float, float]) -> Tuple[float, float]:
        return (round(point[0], _PATH_QUANTIZATION_NDIGITS), round(point[1], _PATH_QUANTIZATION_NDIGITS))

    adjacency: Dict[Tuple[float, float], List[int]] = {}
    for idx, (a, b) in enumerate(raw_segments):
        adjacency.setdefault(_round_key(a), []).append(idx)
        adjacency.setdefault(_round_key(b), []).append(idx)

    endpoints = [point for point, incident in adjacency.items() if len(incident) == 1]
    if len(endpoints) != 2:
        return (p1, p2)  # degenerate/non-simple -- fall back rather than guess

    start = sorted(endpoints)[0]
    path: List[Tuple[float, float]] = [start]
    used: set = set()
    current = start
    for _ in range(len(raw_segments)):
        candidates = [idx for idx in adjacency[current] if idx not in used]
        if not candidates:
            break
        idx = candidates[0]
        used.add(idx)
        a, b = raw_segments[idx]
        nxt = b if _round_key(a) == current else a
        path.append(nxt)
        current = _round_key(nxt)

    if len(path) != len(raw_segments) + 1:
        return (p1, p2)  # could not walk cleanly -- fall back rather than guess
    return tuple(path)


def canonical_wall_candidate_id_v2(
    viewport_id: str,
    edge_ids: Sequence[str],
    edges_by_id: Mapping[str, Mapping[str, Any]],
    p1: Tuple[float, float],
    p2: Tuple[float, float],
) -> str:
    """HYBRID wall identity: geometry AND provenance, always both.

    Used by the physical-wall identity sidecar. Assembly uses the
    geometry-only path fingerprint via ``canonical_path_fingerprint``.
    """
    source_primitive_ids = _chain_source_primitive_ids(edge_ids, edges_by_id)
    path = _path_from_edges(edge_ids, edges_by_id, p1, p2)
    path_fingerprint = canonical_path_fingerprint(path)
    payload = {
        "viewport_id": viewport_id,
        "path_fingerprint": path_fingerprint,
        "source_primitive_ids": source_primitive_ids,
    }
    return stable_contract_id("wall2", payload)
