"""Shadow physical-wall candidate identity + publication equivalence.

``canonical_wall_candidate_id_v2`` is CANDIDATE IDENTITY only. It intentionally
preserves U1 provenance, so the same physical path with duplicated native
primitive IDs receives different V2 IDs. Quantity publication therefore must
not treat ``different V2 ID ⇒ different physical wall``.

Physical equivalence is a separate fail-closed classification:

- SAME_PHYSICAL_WALL — positive proof (same path + same U1 ancestry, or
  ancestor/descendant coverage identity)
- DISTINCT_PHYSICAL_WALLS — positive proof only (different viewport;
  authoritative different levels; same ancestry with proven disjoint spans)
- AMBIGUOUS_PHYSICAL_EQUIVALENCE — neither proven (including identical path
  with different primitive IDs and no explicit duplication proof; different
  path with independent provenance)

Geometry equality alone is never enough when provenance differs.
No confidence, nearest, first, or epsilon merge.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping, Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus
from pb_wall_room_topology_contracts import WallCandidate
from pb_wall_room_topology_wall_identity_v2 import (
    _chain_source_primitive_ids,
    _path_from_edges,
    canonical_path_fingerprint,
    canonical_wall_candidate_id_v2,
)

PHYSICAL_WALL_IDENTITY_SCHEMA_VERSION = "1.0.0"
PHYSICAL_WALL_IDENTITY_METHOD = "physical_wall_identity_v2_sidecar"
PHYSICAL_WALL_EQUIVALENCE_SCHEMA_VERSION = "1.2.0"


class PhysicalEquivalenceClass(str, Enum):
    SAME_PHYSICAL_WALL = "same_physical_wall"
    DISTINCT_PHYSICAL_WALLS = "distinct_physical_walls"
    AMBIGUOUS_PHYSICAL_EQUIVALENCE = "ambiguous_physical_equivalence"


@dataclass(frozen=True)
class PhysicalWallIdentity:
    """Immutable shadow candidate identity for one assembled wall."""

    wall_candidate_id: str
    viewport_id: str
    candidate_identity_id: Optional[str]
    path_fingerprint: Optional[tuple[tuple[float, float], ...]]
    source_primitive_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]
    status: EvidenceResolutionStatus
    blocking_reasons: tuple[str, ...] = ()
    comparison_mode: str = "v2_path"
    level_id: Optional[str] = None
    schema_version: str = PHYSICAL_WALL_IDENTITY_SCHEMA_VERSION

    @property
    def physical_identity_id(self) -> Optional[str]:
        """Back-compat alias: candidate V2 id, not publication equivalence."""
        return self.candidate_identity_id

    @property
    def usable(self) -> bool:
        return (
            self.status == EvidenceResolutionStatus.CORROBORATED
            and self.candidate_identity_id is not None
            and self.path_fingerprint is not None
            and not self.blocking_reasons
        )


@dataclass(frozen=True)
class PhysicalWallEquivalenceResolution:
    """Fail-closed publication equivalence over competing wall candidates."""

    scope_viewport_id: str
    representative_wall_ids: tuple[str, ...]
    abstained_wall_ids: tuple[str, ...]
    equivalence_groups: tuple[tuple[str, ...], ...]
    ambiguous_wall_ids: tuple[str, ...]
    same_wall_ids: tuple[str, ...]
    pair_classifications: tuple[tuple[str, str, str], ...]
    blocking_reasons_by_wall_id: Mapping[str, tuple[str, ...]]
    schema_version: str = PHYSICAL_WALL_EQUIVALENCE_SCHEMA_VERSION

    def blockers_for(self, wall_candidate_id: str) -> tuple[str, ...]:
        return tuple(self.blocking_reasons_by_wall_id.get(wall_candidate_id, ()))


def _wall_edge_ids(wall: WallCandidate) -> tuple[str, ...]:
    ids = list(wall.face_a_segment_ids)
    if wall.face_b_segment_ids:
        ids.extend(wall.face_b_segment_ids)
    return tuple(dict.fromkeys(ids))


def _edges_have_coordinates(
    edge_ids: Sequence[str],
    edges_by_id: Mapping[str, Mapping[str, Any]],
) -> bool:
    for edge_id in edge_ids:
        edge = edges_by_id.get(edge_id) or {}
        try:
            float(edge["x1"])
            float(edge["y1"])
            float(edge["x2"])
            float(edge["y2"])
        except (KeyError, TypeError, ValueError):
            return False
    return True


def _simple_path_walkable(
    edge_ids: Sequence[str],
    edges_by_id: Mapping[str, Mapping[str, Any]],
) -> bool:
    if len(edge_ids) <= 1:
        return True
    raw_segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for edge_id in edge_ids:
        edge = edges_by_id.get(edge_id) or {}
        try:
            raw_segments.append(
                (
                    (float(edge["x1"]), float(edge["y1"])),
                    (float(edge["x2"]), float(edge["y2"])),
                )
            )
        except (KeyError, TypeError, ValueError):
            return False
    adjacency: dict[tuple[float, float], list[int]] = {}
    for idx, (a, b) in enumerate(raw_segments):
        key_a = (round(a[0], 6), round(a[1], 6))
        key_b = (round(b[0], 6), round(b[1], 6))
        adjacency.setdefault(key_a, []).append(idx)
        adjacency.setdefault(key_b, []).append(idx)
    endpoints = [point for point, incident in adjacency.items() if len(incident) == 1]
    return len(endpoints) == 2


def _abstain(
    *,
    wall: WallCandidate,
    edge_ids: tuple[str, ...],
    source_primitive_ids: tuple[str, ...],
    reasons: tuple[str, ...],
    path_fingerprint: Optional[tuple[tuple[float, float], ...]] = None,
) -> PhysicalWallIdentity:
    return PhysicalWallIdentity(
        wall_candidate_id=wall.candidate_id,
        viewport_id=wall.viewport_id,
        candidate_identity_id=None,
        path_fingerprint=path_fingerprint,
        source_primitive_ids=source_primitive_ids,
        edge_ids=edge_ids,
        status=EvidenceResolutionStatus.ABSTAINED,
        blocking_reasons=reasons,
        comparison_mode="abstained",
        level_id=str(wall.level_id or "").strip() or None,
    )


def resolve_physical_wall_identity(
    *,
    wall: WallCandidate,
    edge_ids: Optional[Sequence[str]] = None,
    edges_by_id: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> PhysicalWallIdentity:
    """Resolve one shadow candidate identity where V2 prerequisites exist."""
    resolved_edge_ids = tuple(edge_ids) if edge_ids is not None else _wall_edge_ids(wall)
    lineage = _chain_source_primitive_ids(resolved_edge_ids, edges_by_id or {})
    if not resolved_edge_ids or edges_by_id is None:
        return _abstain(
            wall=wall,
            edge_ids=resolved_edge_ids,
            source_primitive_ids=lineage,
            reasons=("physical_identity_path_inputs_unavailable",),
        )
    missing = tuple(edge_id for edge_id in resolved_edge_ids if edge_id not in edges_by_id)
    if missing:
        return _abstain(
            wall=wall,
            edge_ids=resolved_edge_ids,
            source_primitive_ids=lineage,
            reasons=("physical_identity_edge_missing",),
        )
    if not _edges_have_coordinates(resolved_edge_ids, edges_by_id):
        return _abstain(
            wall=wall,
            edge_ids=resolved_edge_ids,
            source_primitive_ids=lineage,
            reasons=("physical_identity_edge_geometry_unavailable",),
        )
    if len(wall.centerline_pts) < 2:
        return _abstain(
            wall=wall,
            edge_ids=resolved_edge_ids,
            source_primitive_ids=lineage,
            reasons=("physical_identity_centerline_unresolved",),
        )
    p1 = wall.centerline_pts[0]
    p2 = wall.centerline_pts[-1]
    reconstructed = _path_from_edges(resolved_edge_ids, edges_by_id, p1, p2)
    if len(resolved_edge_ids) > 1 and not _simple_path_walkable(resolved_edge_ids, edges_by_id):
        path = tuple(wall.centerline_pts)
        comparison_mode = "centerline_path_with_lineage"
    else:
        path = reconstructed
        comparison_mode = "v2_path"
    path_fingerprint = canonical_path_fingerprint(path)
    candidate_id = canonical_wall_candidate_id_v2(
        wall.viewport_id,
        resolved_edge_ids,
        edges_by_id,
        p1,
        p2,
    )
    return PhysicalWallIdentity(
        wall_candidate_id=wall.candidate_id,
        viewport_id=wall.viewport_id,
        candidate_identity_id=candidate_id,
        path_fingerprint=path_fingerprint,
        source_primitive_ids=lineage,
        edge_ids=resolved_edge_ids,
        status=EvidenceResolutionStatus.CORROBORATED,
        comparison_mode=comparison_mode,
        level_id=str(wall.level_id or "").strip() or None,
    )


def collect_physical_wall_identities(
    walls: Sequence[WallCandidate],
    graph: Mapping[str, Any],
) -> dict[str, PhysicalWallIdentity]:
    """Build sidecar candidate identities at the W4/graph layer."""
    edges_by_id = {
        str(edge["id"]): edge
        for edge in (graph.get("edges") or [])
        if edge.get("id") and not edge.get("_removed")
    }
    return {
        wall.candidate_id: resolve_physical_wall_identity(
            wall=wall,
            edge_ids=_wall_edge_ids(wall),
            edges_by_id=edges_by_id,
        )
        for wall in walls
    }


def _axis_interval(
    path: Sequence[tuple[float, float]],
) -> Optional[tuple[str, float, float]]:
    if len(path) < 2:
        return None
    dx = path[-1][0] - path[0][0]
    dy = path[-1][1] - path[0][1]
    if abs(dx) >= abs(dy):
        xs = [point[0] for point in path]
        return ("h", min(xs), max(xs))
    ys = [point[1] for point in path]
    return ("v", min(ys), max(ys))


def _intervals_overlap(left: tuple[str, float, float], right: tuple[str, float, float]) -> bool:
    if left[0] != right[0]:
        return False
    return not (left[2] <= right[1] or right[2] <= left[1])


def _intervals_disjoint(left: tuple[str, float, float], right: tuple[str, float, float]) -> bool:
    """Positive disjointness requires comparable projections on the same axis.

    A dominant-axis mismatch can arise from curved/L-shaped/reconstructed
    paths.  It is therefore lack of a comparable 1-D span, not proof that two
    physical walls are distinct.
    """
    if left[0] != right[0]:
        return False
    return left[2] <= right[1] or right[2] <= left[1]


def _ancestry_equal(left: Sequence[str], right: Sequence[str]) -> bool:
    return bool(left) and set(left) == set(right)


def _ancestry_coverage_identical(left: Sequence[str], right: Sequence[str]) -> bool:
    """Ancestor/descendant reconstruction with identical coverage.

    Non-empty sets where one is a subset of the other and both describe the
    same complete path are treated as the same physical coverage only when
    the sets are equal. Strict subset without equal coverage stays ambiguous
    (no silent contained-subspan merge).
    """
    return _ancestry_equal(left, right)


def classify_physical_wall_pair(
    left: PhysicalWallIdentity,
    right: PhysicalWallIdentity,
) -> PhysicalEquivalenceClass:
    """Classify one pair. Never uses distance, confidence, or first-candidate.

    Absence of SAME proof is not positive DISTINCT proof. A bare label
    (``viewport_id`` or ``level_id``) difference is likewise not positive
    DISTINCT proof by itself -- this repository has no authoritative
    level/scope-identity resolver yet, so two candidates whose only
    difference is an unvalidated label string cannot be more than
    AMBIGUOUS. Crossing that same unproven boundary (``cross_scope`` below)
    also blocks the SAME rule: coordinate/ancestry coincidence across a
    labelled-but-unverified viewport or level boundary is not proof of
    physical identity either, only a coincidence. The only rules that may
    ever return DISTINCT are grounded in proven, positive geometry+provenance
    facts (disjoint spans under shared ancestry) that do not depend on any
    label string at all.
    """
    if not left.usable or not right.usable:
        return PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE

    left_level = str(left.level_id or "").strip()
    right_level = str(right.level_id or "").strip()
    cross_scope = (left.viewport_id != right.viewport_id) or (
        bool(left_level) and bool(right_level) and left_level != right_level
    )

    same_path = left.path_fingerprint is not None and left.path_fingerprint == right.path_fingerprint
    left_prims = tuple(left.source_primitive_ids)
    right_prims = tuple(right.source_primitive_ids)
    shared = set(left_prims) & set(right_prims)
    equal_ancestry = _ancestry_equal(left_prims, right_prims)
    coverage_identical = _ancestry_coverage_identical(left_prims, right_prims)

    if same_path and (equal_ancestry or coverage_identical) and not cross_scope:
        return PhysicalEquivalenceClass.SAME_PHYSICAL_WALL

    if same_path and not equal_ancestry:
        return PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE

    left_iv = _axis_interval(left.path_fingerprint or ())
    right_iv = _axis_interval(right.path_fingerprint or ())

    # Span comparisons are only positive evidence when both paths have the
    # same dominant projection axis.  Different axes are incomparable, not
    # disjoint proof.
    if left_iv is not None and right_iv is not None and left_iv[0] != right_iv[0]:
        return PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE

    if equal_ancestry and left_iv is not None and right_iv is not None:
        if _intervals_disjoint(left_iv, right_iv):
            return PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS
        return PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE

    if shared and left_iv is not None and right_iv is not None:
        if _intervals_overlap(left_iv, right_iv):
            return PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE
        return PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS

    return PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE


def _union_find_groups(pairs: Sequence[tuple[str, str]], members: Sequence[str]) -> list[list[str]]:
    parent = {member: member for member in members}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: str, right: str) -> None:
        root_l, root_r = find(left), find(right)
        if root_l != root_r:
            parent[root_r] = root_l

    for left, right in pairs:
        if left in parent and right in parent:
            union(left, right)
    groups: dict[str, list[str]] = {}
    for member in members:
        groups.setdefault(find(member), []).append(member)
    return [sorted(group) for group in groups.values()]


def _deterministic_representative(wall_ids: Sequence[str]) -> str:
    """Stable representative: lexicographic wall_candidate_id (not confidence/nearest)."""
    return sorted(wall_ids)[0]


def resolve_physical_wall_equivalence(
    identities: Sequence[Optional[PhysicalWallIdentity]],
    *,
    walls_by_id: Optional[Mapping[str, WallCandidate]] = None,
) -> PhysicalWallEquivalenceResolution:
    """Reconcile ALL competing candidates via SAME/DISTINCT/AMBIGUOUS components.

    Pure SAME component → exactly one representative may publish.
    Any AMBIGUOUS edge in a connected component → all members abstain.
    Proven DISTINCT walls publish independently when otherwise usable.
    """
    del walls_by_id
    usable: list[PhysicalWallIdentity] = []
    blockers: dict[str, list[str]] = {}
    viewport_ids: set[str] = set()

    for identity in identities:
        if identity is None:
            continue
        viewport_ids.add(identity.viewport_id)
        if not identity.usable:
            blockers.setdefault(identity.wall_candidate_id, []).extend(
                identity.blocking_reasons or ("physical_wall_identity_abstained",)
            )
            continue
        usable.append(identity)

    scope_viewport = sorted(viewport_ids)[0] if len(viewport_ids) == 1 else "multi"
    member_ids = [identity.wall_candidate_id for identity in usable]

    pair_classifications: list[tuple[str, str, str]] = []
    same_links: list[tuple[str, str]] = []
    ambiguous_links: list[tuple[str, str]] = []

    for i, left in enumerate(usable):
        for right in usable[i + 1 :]:
            classification = classify_physical_wall_pair(left, right)
            a, b = sorted((left.wall_candidate_id, right.wall_candidate_id))
            pair_classifications.append((a, b, classification.value))
            if classification == PhysicalEquivalenceClass.SAME_PHYSICAL_WALL:
                same_links.append((a, b))
            elif classification == PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE:
                ambiguous_links.append((a, b))

    related_links = same_links + ambiguous_links
    components = _union_find_groups(related_links, member_ids) if member_ids else []
    ambiguous_edges = {frozenset(pair) for pair in ambiguous_links}
    same_edges = {frozenset(pair) for pair in same_links}

    ambiguous_walls: set[str] = set()
    same_groups: list[tuple[str, ...]] = []
    representatives: list[str] = []

    for component in components:
        component_set = set(component)
        has_ambiguous = any(
            frozenset((a, b)) in ambiguous_edges
            for i, a in enumerate(component)
            for b in component[i + 1 :]
        )
        has_same = any(
            frozenset((a, b)) in same_edges
            for i, a in enumerate(component)
            for b in component[i + 1 :]
        )
        if has_ambiguous:
            ambiguous_walls.update(component_set)
            for wall_id in component:
                blockers.setdefault(wall_id, []).append("ambiguous_physical_wall_equivalence")
            continue
        if has_same and len(component) > 1:
            group = tuple(sorted(component))
            same_groups.append(group)
            rep = _deterministic_representative(group)
            representatives.append(rep)
            for wall_id in group:
                if wall_id == rep:
                    continue
                blockers.setdefault(wall_id, []).append(
                    f"equivalent_physical_wall_represented_by:{rep}"
                )
            continue
        for wall_id in component:
            if wall_id not in blockers:
                representatives.append(wall_id)

    linked = {wall_id for group in components for wall_id in group}
    for wall_id in member_ids:
        if wall_id in linked:
            continue
        if wall_id not in blockers:
            representatives.append(wall_id)

    representatives = list(dict.fromkeys(representatives))
    representatives = [wall_id for wall_id in representatives if wall_id not in blockers]

    abstained: list[str] = []
    for identity in identities:
        if identity is None:
            continue
        wall_id = identity.wall_candidate_id
        reasons = tuple(dict.fromkeys(blockers.get(wall_id, ())))
        if reasons:
            blockers[wall_id] = list(reasons)
            abstained.append(wall_id)
        elif identity.usable and wall_id in representatives:
            continue
        elif not identity.usable:
            abstained.append(wall_id)

    return PhysicalWallEquivalenceResolution(
        scope_viewport_id=scope_viewport,
        representative_wall_ids=tuple(representatives),
        abstained_wall_ids=tuple(dict.fromkeys(abstained)),
        equivalence_groups=tuple(same_groups),
        ambiguous_wall_ids=tuple(sorted(ambiguous_walls)),
        same_wall_ids=tuple(sorted({wall_id for group in same_groups for wall_id in group})),
        pair_classifications=tuple(sorted(pair_classifications)),
        blocking_reasons_by_wall_id={
            wall_id: tuple(dict.fromkeys(reasons)) for wall_id, reasons in blockers.items() if reasons
        },
    )
