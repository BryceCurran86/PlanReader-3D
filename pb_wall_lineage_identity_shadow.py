"""Wall identity from source lineage (report only, default off).

A wall's assembly id hashes its snapped centreline, so any node move renames it.
Splitting at crossings happens before snapping, so the source pieces a wall is
built from do not change with the snap. This sidecar hashes those pieces
instead: for each piece longer than the snap tolerance, its source primitive ids
and its own endpoints before snapping. Shorter pieces are left out (different
snaps keep or collapse them).

A wall gets no lineage id, never a chosen one, when an edge or piece cannot be
found, a long piece lacks source ancestry, the wall has no long piece, or a long
piece is used by another wall of the same viewport.

Whole chains change when a snap changes where walls end, so for an opening's
host the narrower ``host_jamb_identity`` names only the long piece of each
member wall that ends at the opening's own source geometry; a member with none or
several there vetoes the whole identity. Existing candidate ids, host
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
NO_JAMB_PIECE = "wall_lineage_no_piece_at_opening"
SEVERAL_JAMB_PIECES = "wall_lineage_several_pieces_at_opening"


def _piece_key(fragment: Mapping[str, Any]) -> tuple | None:
    """(source ids, direction-free endpoints), or None without finite geometry."""
    x1, y1, x2, y2 = fragment["points"]
    if not all(type(v) in (int, float) and math.isfinite(v) for v in (x1, y1, x2, y2)):
        return None
    # "+ 0.0" turns -0.0 into 0.0: intersections produce either, and the ids hash them apart.
    ends = sorted(((round(x1, 6) + 0.0, round(y1, 6) + 0.0), (round(x2, 6) + 0.0, round(y2, 6) + 0.0)))
    return (tuple(sorted(str(s) for s in fragment["source_primitive_ids"] if str(s).strip())), tuple(ends))


def _long_pieces(wall: Any, edges: Mapping, fragments: Mapping, tolerance_pt: float) -> tuple[set | None, str | None]:
    """The wall's source pieces longer than the tolerance, or the reason there is no trustworthy set."""
    edge_ids = [str(e) for e in (*wall.face_a_segment_ids, *(wall.face_b_segment_ids or ()))]
    if not edge_ids or any(e not in edges for e in edge_ids):
        return None, MISSING_EDGE
    pieces = set()
    for edge_id in edge_ids:
        for leaf in edges[edge_id].get("collinear_merge_leaf_edge_ids") or (edge_id,):
            fragment = fragments.get(str(leaf))
            key = _piece_key(fragment) if fragment is not None else None
            if key is None:
                return None, MISSING_PIECE
            (ax, ay), (bx, by) = key[1]
            if math.hypot(bx - ax, by - ay) <= tolerance_pt + 1e-6:
                continue
            if not key[0]:
                return None, MISSING_SOURCE
            pieces.add(key)
    return (pieces, None) if pieces else (None, NO_LONG_PIECE)


def _graph_parts(graph: Mapping[str, Any], tolerance_pt: float) -> tuple[dict, Mapping]:
    if not (math.isfinite(tolerance_pt) and tolerance_pt >= 0):
        raise ValueError("lineage identity needs a finite tolerance")
    fragments = graph.get("leaf_fragments_shadow")
    if not isinstance(fragments, Mapping):
        raise ValueError("graph was not built with retained leaf fragments")  # noqa: TRY004 - same refusal as None
    return {str(edge.get("id")): edge for edge in graph.get("edges") or ()}, fragments


def _to_segment(point: tuple[float, float], segment: Sequence[float]) -> float:
    x1, y1, x2, y2 = (float(v) for v in segment[:4])
    dx, dy = x2 - x1, y2 - y1
    length_sq = dx * dx + dy * dy
    t = 0.0 if length_sq == 0 else max(0.0, min(1.0, ((point[0] - x1) * dx + (point[1] - y1) * dy) / length_sq))
    return math.hypot(point[0] - x1 - t * dx, point[1] - y1 - t * dy)


def _payload(pieces) -> list[dict]:
    return [{"source_primitive_ids": list(sources), "points": [list(p) for p in ends]} for sources, ends in sorted(pieces)]


def host_jamb_identity(
    members: Sequence[Any], graph: Mapping[str, Any], opening_segments: Sequence[Sequence[float]], *, tolerance_pt: float,
) -> dict[str, Any]:
    """Report-only identity of an opening's host from the one piece of each member wall that ends at the opening.

    ``opening_segments`` are the opening's own source segments (x1, y1, x2, y2); a piece is "at the opening" when
    one of its ends is within the snap tolerance of one of them.
    """
    edges, fragments = _graph_parts(graph, tolerance_pt)
    anchors = [tuple(float(v) for v in s[:4]) for s in opening_segments]
    chosen: list[tuple] = []
    vetoes: dict[str, str] = {}
    viewports = {str(wall.viewport_id) for wall in members}
    for wall in members:
        wall_id = str(wall.candidate_id)
        pieces, veto = _long_pieces(wall, edges, fragments, tolerance_pt)
        if veto:
            vetoes[wall_id] = veto
            continue
        at_opening = [piece for piece in pieces if any(
            _to_segment(end, anchor) <= tolerance_pt + 1e-6 for end in piece[1] for anchor in anchors)]
        if len(at_opening) != 1:
            vetoes[wall_id] = SEVERAL_JAMB_PIECES if at_opening else NO_JAMB_PIECE
            continue
        chosen.append(at_opening[0])
    if len(set(chosen)) != len(chosen):
        vetoes.update({str(wall.candidate_id): SHARED_PIECE for wall in members})
    identity = None
    if members and anchors and not vetoes and len(viewports) == 1:
        identity = stable_contract_id("wall_jamb_lineage_v1", {"viewport_id": viewports.pop(), "pieces": _payload(chosen)})
    return {"identity": identity, "vetoes": vetoes, "diagnostic_only": True, "replaces_existing_identity": False,
            "version": LINEAGE_IDENTITY_SHADOW_VERSION}


def wall_lineage_identities(
    walls: Sequence[Any], graph: Mapping[str, Any], *, tolerance_pt: float,
) -> dict[str, Any]:
    """Lineage ids for assembled walls of one graph built with ``retain_leaf_fragments_shadow``.

    ``walls`` are W4 wall candidates (candidate_id, viewport_id, face segment ids).
    """
    edges, fragments = _graph_parts(graph, tolerance_pt)
    pieces_by_wall: dict[str, tuple[str, frozenset]] = {}
    vetoes: dict[str, str] = {}
    owners: dict[tuple, set] = {}
    for wall in walls:
        wall_id, viewport = str(wall.candidate_id), str(wall.viewport_id)
        pieces, veto = _long_pieces(wall, edges, fragments, tolerance_pt)
        if veto:
            vetoes[wall_id] = veto
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
        identities[wall_id] = stable_contract_id("wall_lineage_v1", {"viewport_id": viewport, "pieces": _payload(pieces)})
    return {
        "version": LINEAGE_IDENTITY_SHADOW_VERSION,
        "identities": identities,
        "vetoes": vetoes,
        "diagnostic_only": True,
        "replaces_existing_identity": False,
    }
