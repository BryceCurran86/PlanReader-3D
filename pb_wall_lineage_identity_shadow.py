"""Wall identity from source lineage (report only, default off).

A wall's assembly id hashes its snapped centreline, so any node move renames it.
Splitting at crossings happens before snapping, so the source pieces a wall is
built from do not change with the snap. This sidecar hashes those pieces
instead: for each piece longer than the snap tolerance, its source primitive ids
and its own endpoints before snapping. Shorter pieces are left out (different
snaps keep or collapse them).

A wall gets no lineage id, never a chosen one, when an edge or piece cannot be
found, a long piece lacks source ancestry, the wall has no long piece, or a long
piece is used by another wall of the same viewport. Existing candidate ids, host
bindings, evidence ids and signed rows are untouched; no id is ever copied from
one wall to another. See docs/engineering/claude_wall_lineage_identity_design_20261128.md.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from pb_migration_contracts import stable_contract_id

LINEAGE_IDENTITY_SHADOW_VERSION = "wall-lineage-1.0.0"
MISSING_EDGE = "wall_lineage_missing_edge"
MISSING_PIECE = "wall_lineage_missing_fragment"
MISSING_SOURCE = "wall_lineage_missing_source_ancestry"
NO_LONG_PIECE = "wall_lineage_no_long_piece"
SHARED_PIECE = "wall_lineage_shared_piece"


def _piece_key(fragment: Mapping[str, Any]) -> tuple | None:
    """(source ids, direction-free endpoints), or None without finite geometry."""
    x1, y1, x2, y2 = fragment["points"]
    if not all(type(v) in (int, float) and math.isfinite(v) for v in (x1, y1, x2, y2)):
        return None
    # "+ 0.0" turns -0.0 into 0.0: intersections produce either, and the ids hash them apart.
    ends = sorted(((round(x1, 6) + 0.0, round(y1, 6) + 0.0), (round(x2, 6) + 0.0, round(y2, 6) + 0.0)))
    return (tuple(sorted(str(s) for s in fragment["source_primitive_ids"] if str(s).strip())), tuple(ends))


def wall_lineage_identities(
    walls: Sequence[Any], graph: Mapping[str, Any], *, tolerance_pt: float,
) -> dict[str, Any]:
    """Lineage ids for assembled walls of one graph built with ``retain_leaf_fragments_shadow``.

    ``walls`` are W4 wall candidates (candidate_id, viewport_id, face segment ids).
    """
    if not (math.isfinite(tolerance_pt) and tolerance_pt >= 0):
        raise ValueError("lineage identity needs a finite tolerance")
    fragments = graph.get("leaf_fragments_shadow")
    if not isinstance(fragments, Mapping):
        raise ValueError("graph was not built with retained leaf fragments")  # noqa: TRY004 - same refusal as None
    edges = {str(edge.get("id")): edge for edge in graph.get("edges") or ()}
    pieces_by_wall: dict[str, tuple[str, frozenset]] = {}
    vetoes: dict[str, str] = {}
    owners: dict[tuple, set] = {}
    for wall in walls:
        wall_id, viewport = str(wall.candidate_id), str(wall.viewport_id)
        edge_ids = [str(e) for e in (*wall.face_a_segment_ids, *(wall.face_b_segment_ids or ()))]
        if not edge_ids or any(e not in edges for e in edge_ids):
            vetoes[wall_id] = MISSING_EDGE
            continue
        pieces, veto = set(), None
        for edge_id in edge_ids:
            leaves = edges[edge_id].get("collinear_merge_leaf_edge_ids") or (edge_id,)
            for leaf in leaves:
                fragment = fragments.get(str(leaf))
                key = _piece_key(fragment) if fragment is not None else None
                if key is None:
                    veto = MISSING_PIECE
                    break
                (ax, ay), (bx, by) = key[1]
                if math.hypot(bx - ax, by - ay) <= tolerance_pt + 1e-6:
                    continue
                if not key[0]:
                    veto = MISSING_SOURCE
                    break
                pieces.add(key)
            if veto:
                break
        if veto or not pieces:
            vetoes[wall_id] = veto or NO_LONG_PIECE
            continue
        pieces_by_wall[wall_id] = (viewport, frozenset(pieces))
        for piece in pieces:
            owners.setdefault((viewport, piece), set()).add(wall_id)
    shared = {wall_id for ids in owners.values() if len(ids) > 1 for wall_id in ids}
    identities: dict[str, str | None] = {}
    for wall in walls:
        wall_id = str(wall.candidate_id)
        if wall_id in shared:
            vetoes[wall_id] = SHARED_PIECE
        if wall_id in vetoes:
            identities[wall_id] = None
            continue
        viewport, pieces = pieces_by_wall[wall_id]
        identities[wall_id] = stable_contract_id("wall_lineage_v1", {
            "viewport_id": viewport,
            "pieces": [{"source_primitive_ids": list(sources), "points": [list(p) for p in ends]}
                       for sources, ends in sorted(pieces)],
        })
    return {
        "version": LINEAGE_IDENTITY_SHADOW_VERSION,
        "identities": identities,
        "vetoes": vetoes,
        "diagnostic_only": True,
        "replaces_existing_identity": False,
    }
