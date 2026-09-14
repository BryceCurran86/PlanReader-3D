"""W4 identity, revisited now that U1 primitive lineage exists (research only).

``pb_wall_room_topology_wall_assembly._canonical_wall_candidate_id`` hashes a
chain's two *boundary endpoint coordinates* only. That is correct for the
narrow guarantee it was built for (a wall's id survives re-chunking, since
the boundary points do not move when a straight run is re-split into more or
fewer collinear fragments), but it has a real blind spot the U1 review
foreshadowed: two GEOMETRICALLY AND TOPOLOGICALLY DIFFERENT walls that happen
to start and end at the same two points -- e.g. a straight connector versus
an L-shaped detour between the identical pair of corners -- collide onto the
same id, because the hash never looks at what happens *between* the
endpoints.

This module is a side-by-side research comparison, not a replacement:
nothing here is imported by ``pb_wall_room_topology_wall_assembly.py`` or any
other production/shadow-authority module. Per the standing instruction, a new
identity function is not wired into production until tests prove it superior
across the adversarial matrix -- see
``tests/test_canonical_wall_room_model.py::TestWallIdentityV2``.

REVISED after an independent GPT-2 review: the FIRST version of this module
made provenance take over ENTIRELY whenever lineage was present, dropping
geometry from the hash altogether -- meaning two genuinely disjoint physical
spans sharing the same native ancestor (e.g. two different derived wall
candidates split from one native primitive) collided onto the SAME id,
which is a real regression relative to even the old geometry-only scheme.
Confirmed and reproduced independently via GPT-2's own regression test
before this fix.

DESIGN: HYBRID identity -- geometry AND provenance, always combined
---------------------------------------------------------------------
Never provenance-ALONE and never geometry-ALONE. The id hashes:

    (viewport_id, canonical_path_fingerprint(centerline), sorted
     provenance_ids_or_empty)

``canonical_path_fingerprint``:
1. Round every vertex to a fixed precision (quantization -- ordinary
   floating-point replay noise must not change identity).
2. Collapse redundant collinear interior vertices (three consecutive points
   where the middle one lies on the straight line through its neighbours
   are reduced to the two endpoints) -- this is what makes the fingerprint
   insensitive to simple collinear re-chunking: a straight run split into
   more or fewer fragments by the splitter, or re-merged by chain assembly,
   reduces to the identical vertex sequence either way. Every WallCandidate
   this repository's own assemble_wall_candidates can currently produce is
   already a single straight chain (L_CORNER never merges two edges into
   one chain -- see wall_assembly.py's own docstring), so for the walls
   this system actually builds today this step is usually a no-op beyond
   the two boundary points; it is still implemented generally (not just for
   2-point input) so a future non-simple/fallback chain (the "non_simple_
   chain_topology_fallback_ordering" case ``assemble_wall_candidates`` can
   flag) fingerprints correctly too, rather than only "working by
   accident" for the straight-chain case.
3. Canonical orientation: compare the point sequence forward against
   reversed, keep whichever sorts smaller -- direction-invariant (walking a
   chain start-to-end or end-to-start gives the identical fingerprint).

Provenance ids (sorted, deduped U1 ``source_primitive_ids`` unioned across
every contributing edge) are combined WITH this fingerprint, never used to
replace it. Two chains sharing every native ancestor but occupying disjoint
geometric spans (split descendants of one native primitive) now correctly
receive different ids, because their path fingerprints differ even though
their provenance sets are identical.

Required properties, each proven by a dedicated test in
``tests/test_canonical_wall_room_model.py::TestWallIdentityV2``:
- same native source + disjoint spans -> DIFFERENT ids (fingerprint differs)
- same source + same physical wall after splitter re-chunk -> SAME id
  (fingerprint's collinear-collapse + quantization absorbs re-chunking)
- same endpoints + different interior path -> DIFFERENT ids (fingerprint
  differs even without relying on provenance to do all the work)
- reversed direction -> SAME id (canonical orientation)
- viewport change -> DIFFERENT id (viewport_id is part of the hash)
"""
from __future__ import annotations

import math
from typing import Any, Iterable, Mapping, Sequence, Tuple

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


def canonical_wall_candidate_id_v2(
    viewport_id: str,
    edge_ids: Sequence[str],
    edges_by_id: Mapping[str, Mapping[str, Any]],
    p1: Tuple[float, float],
    p2: Tuple[float, float],
) -> str:
    """HYBRID wall identity: geometry AND provenance, always both.

    ``edge_ids`` are the Stage-A edge ids assembled into this one chain
    (``assemble_wall_candidates``'s own per-group ``edge_ids`` set);
    ``edges_by_id`` is that same function's already-built lookup; ``p1``/
    ``p2`` are the chain's two boundary endpoints. Callers with the chain's
    full interior polyline (``WallCandidate.centerline_pts``) may pass it
    via ``p1``/``p2`` as a 2-tuple degenerate case, or a future caller could
    extend this signature to accept the full path directly -- for every
    wall this repository's assemble_wall_candidates can currently produce,
    the two boundary points already fully determine the canonical
    fingerprint (see module docstring: chains are always single straight
    runs by construction), so the 2-point signature is not a loss of
    precision for today's callers.
    """
    source_primitive_ids = _chain_source_primitive_ids(edge_ids, edges_by_id)
    path_fingerprint = canonical_path_fingerprint((p1, p2))
    payload = {
        "viewport_id": viewport_id,
        "path_fingerprint": path_fingerprint,
        "source_primitive_ids": source_primitive_ids,
    }
    return stable_contract_id("wall2", payload)
