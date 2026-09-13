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

DESIGN: provenance-first, geometry-fallback
--------------------------------------------
1. If the chain's edges carry U1 primitive lineage (``primitive_lineage`` ->
   ``source_primitive_ids``), hash the viewport id plus the SORTED, DEDUPED
   union of every contributing native primitive id. Sorting makes this
   direction-invariant (walking the chain start-to-end or end-to-start
   collects the same set) and reordering-invariant (native primitive
   enumeration order, an artifact of PDF extraction, never affects a sorted
   set). Because splitting one native line into more fragments, or merging
   several fragments back into one chain, only changes how many pieces the
   SAME set of native ids is spread across (U1's own union-of-lineage
   guarantee -- see pb_wall_room_topology_primitive_lineage.lineage_from_
   edges), this identity is stable under re-chunking by construction, not by
   coincidence.
2. If no chain edge carries any lineage at all (a graph built by a caller
   that never wired U1 -- backward compatible), fall back to the EXISTING
   geometry-endpoint identity, imported unchanged from wall_assembly rather
   than re-implemented, so the fallback path is never a second, possibly-
   diverging copy of that logic.

This directly fixes the same-endpoints-different-interior-path collision
(distinct interior paths are made of distinct native primitives, so their
provenance-first ids differ) while remaining exactly as re-chunking-tolerant
and viewport-isolated as the geometry-only scheme it extends.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple

from pb_migration_contracts import stable_contract_id
from pb_wall_room_topology_primitive_lineage import LINEAGE_KEY
from pb_wall_room_topology_wall_assembly import _canonical_wall_candidate_id


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


def canonical_wall_candidate_id_v2(
    viewport_id: str,
    edge_ids: Sequence[str],
    edges_by_id: Mapping[str, Mapping[str, Any]],
    p1: Tuple[float, float],
    p2: Tuple[float, float],
) -> str:
    """Provenance-first wall identity with a geometry-endpoint fallback.

    ``edge_ids`` are the Stage-A edge ids assembled into this one chain
    (``assemble_wall_candidates``'s own per-group ``edge_ids`` set);
    ``edges_by_id`` is that same function's already-built lookup;
    ``p1``/``p2`` are the chain's two boundary endpoints, passed straight
    through to the geometry fallback so it need not be recomputed.
    """
    source_primitive_ids = _chain_source_primitive_ids(edge_ids, edges_by_id)
    if source_primitive_ids:
        return stable_contract_id(
            "wall2",
            {"viewport_id": viewport_id, "source_primitive_ids": source_primitive_ids},
        )
    return _canonical_wall_candidate_id(viewport_id, p1, p2)
