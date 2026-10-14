"""Read-only G17 versus ordinary W4 source-fragment competitor census.

A geometric overlap across independently raster-detected source namespaces
is NOT physical wall equivalence. No result can authorize a host or quantity.
"""
from __future__ import annotations

from collections import Counter
from math import isfinite
from typing import Any, Sequence

_COORD_TOL = 1e-6


def _line(value: object) -> tuple[float, float, float, float] | None:
    if not isinstance(value, (tuple, list)) or len(value) != 4:
        return None
    try:
        values = tuple(float(v) for v in value)
    except (TypeError, ValueError):
        return None
    return values if all(isfinite(v) for v in values) else None


def _positive_collinear_source_overlap(left: object, right: object) -> bool:
    """Exact-collinear positive source-edge overlap, not a nearest-line rule."""
    a, b = _line(left), _line(right)
    if a is None or b is None:
        return False
    for axis in (0, 1):
        cross = 1 - axis
        if (abs(a[cross] - a[cross + 2]) > _COORD_TOL
                or abs(b[cross] - b[cross + 2]) > _COORD_TOL
                or abs(a[cross] - b[cross]) > _COORD_TOL):
            continue
        al, ah = sorted((a[axis], a[axis + 2]))
        bl, bh = sorted((b[axis], b[axis + 2]))
        if min(ah, bh) - max(al, bl) > _COORD_TOL:
            return True
    return False


def _fragments(record: Any) -> tuple[Any, ...]:
    return tuple(getattr(record, "source_edge_fragments", ()) or ())


def compare_g17_to_ordinary_w4_shadow(
    flank_shadows: Sequence[Any], ordinary_w4_records: Sequence[Any],
) -> dict[str, Any]:
    """Retain every real W4 alternative; always abstain on role/equivalence.

    The caller must separately authenticate the source producer and wall scope.
    This observer has no method to grant authority, even on a unique match.
    """
    ordinary = tuple(ordinary_w4_records)
    counts = Counter(str(r.wall_candidate_id) for r in ordinary)
    collision_ids = sorted(k for k, v in counts.items() if v > 1)
    results = []
    for flank in flank_shadows:
        if not getattr(flank, "source_ink_supported", False):
            results.append({
                "source_ink_supported": False, "g17_edge_count": 0,
                "competing_ordinary_w4": [], "unmatched_g17_source_edges": [],
                "source_ancestry_shared_w4": [],
                "physical_wall_equivalence_granted": False,
                "first_blocker": "g17_original_source_ink_unavailable",
            })
            continue
        source_edges = tuple(
            fragment
            for record in tuple(getattr(flank, "exact_coordinate_records", ()) or ())
            for fragment in _fragments(record)
        )
        # No dropped alternatives: duplicate edge addresses remain explicit.
        edge_counts = Counter(str(f.edge_id) for f in source_edges)
        edges = {str(f.edge_id): f for f in source_edges}
        duplicate_edges = sorted(k for k, v in edge_counts.items() if v > 1)
        g17_raw = {str(s) for f in source_edges for s in f.source_primitive_ids}
        competitors = []
        shared_source = []
        overlapping = set()
        for record in ordinary:
            identity = record.physical_identity
            shared = sorted(g17_raw & {str(s) for s in identity.source_primitive_ids})
            if shared:
                shared_source.append({
                    "w4_wall_candidate_id": str(record.wall_candidate_id),
                    "shared_source_primitive_ids": shared,
                })
            matches = []
            for edge_id, left in sorted(edges.items()):
                fragments = tuple(
                    f for f in _fragments(record)
                    if _positive_collinear_source_overlap(left.geometry, f.geometry)
                )
                if fragments:
                    overlapping.add(edge_id)
                    matches.append({
                        "g17_edge_id": edge_id,
                        "w4_edge_ids": sorted(str(f.edge_id) for f in fragments),
                        "g17_source_primitive_ids": sorted(left.source_primitive_ids),
                        "w4_source_primitive_ids": sorted({
                            str(s) for f in fragments for s in f.source_primitive_ids
                        }),
                    })
            if matches:
                competitors.append({
                    "w4_wall_candidate_id": str(record.wall_candidate_id),
                    "w4_candidate_identity_id": identity.candidate_identity_id,
                    "w4_identity_usable": bool(identity.usable),
                    "geometrically_overlapping_source_edges": matches,
                    "independently_proven_cross_source_equivalence": False,
                })
        competitors.sort(key=lambda row: (
            row["w4_wall_candidate_id"], str(row["w4_candidate_identity_id"]),
        ))
        results.append({
            "source_ink_supported": True, "g17_edge_count": len(source_edges),
            "duplicate_g17_edge_addresses": duplicate_edges,
            "competing_ordinary_w4": competitors,
            "unmatched_g17_source_edges": sorted(set(edges) - overlapping),
            "source_ancestry_shared_w4": sorted(
                shared_source, key=lambda row: row["w4_wall_candidate_id"],
            ),
            "physical_wall_equivalence_granted": False,
            "first_blocker": (
                "g17_graph_edge_address_collision" if duplicate_edges else
                "g17_source_graph_edges_unavailable" if not edges else
                "ordinary_w4_same_source_ancestry_unavailable" if not shared_source else
                "cross_scope_wall_role_and_equivalence_unproven"
            ),
        })
    return {
        "ordinary_w4_records_examined": len(ordinary),
        "ordinary_w4_candidate_address_collisions": collision_ids,
        "flanks": results,
        "physical_wall_role_granted": False,
        "physical_wall_equivalence_granted": False,
        "host_binding_granted": False,
        "metric_quantity_granted": False,
        "ordinary_w4_universe_complete_proven": False,
    }
