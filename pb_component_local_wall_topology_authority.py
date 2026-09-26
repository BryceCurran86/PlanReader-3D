"""Equivalence-aware component-local source wall topology authority.

Shadow-first authority. It does not mutate the global wall-scope completeness
flag and does not relax the existing source topology path.

A physical wall component can publish room/envelope topology when:
- its source wall scope is corroborated;
- only floor-plan viewport scopes are used for viewport topology;
- positive physical-wall equivalence groups are normalized to one owner;
- the component itself has no wall ending on a page/viewport boundary;
- every source structural observation withheld because of viewport ownership
  is replayable; and
- none of those withheld observations touches or crosses any wall edge in the
  component.

Unrelated cropped geometry elsewhere on the sheet therefore cannot poison an
isolated component. Any ambiguity connected to the component still abstains.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Iterable

import fitz

from pb_accuracy_v13_engines_v145 import extract_planar_faces
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    _viewport_scope_boundary_reason,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_source_wall_topology_authority import (
    _ABSOLUTE_DEGENERATE_AREA_PT2,
    _SOURCE_TOPOLOGY_AUTHORITY_SEAL,
    _TINY_RELATIVE_THRESHOLD,
    _canonical_polygon,
    _edge,
    _polygon_area,
    _wall_edges,
)
from pb_wall_role_authority import (
    WallTopologyAuthority,
    WallTopologyEvidence,
    _AUTHORITY_SEAL,
)

COMPONENT_LOCAL_TOPOLOGY_SCHEMA_VERSION = "1.0.0"
COMPONENT_LOCAL_TOPOLOGY_PROVENANCE = (
    "source_derived_component_local_physical_wall_face_topology"
)
_INTERSECTION_TOL = 1e-6

Point = tuple[float, float]
Edge = tuple[Point, Point]
TopologyKey = tuple[str, str, str, str, str, str, str]


@dataclass(frozen=True)
class ComponentLocalTopologyProof:
    proof_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    component_wall_ids: tuple[str, ...]
    source_candidate_wall_ids: tuple[str, ...]
    withheld_observation_ids_checked: tuple[str, ...]
    equivalence_groups_used: tuple[tuple[str, ...], ...]
    scope_was_globally_complete: bool
    schema_version: str = COMPONENT_LOCAL_TOPOLOGY_SCHEMA_VERSION


def _equivalence_owner_map(
    scope,
) -> tuple[dict[str, str], set[str], tuple[tuple[str, ...], ...]]:
    records = tuple(scope.records or ())
    owner = {
        str(record.wall_candidate_id): str(record.wall_candidate_id)
        for record in records
    }
    equivalence = getattr(scope, "equivalence", None)
    groups = tuple(
        tuple(sorted(str(value) for value in group))
        for group in tuple(getattr(equivalence, "equivalence_groups", ()) or ())
        if group
    )
    for group in groups:
        representative = group[0]
        for wall_id in group:
            if wall_id in owner:
                owner[wall_id] = representative
    ambiguous = {
        str(value)
        for value in tuple(getattr(equivalence, "ambiguous_wall_ids", ()) or ())
    }
    return owner, ambiguous, groups


def _orientation(a: Point, b: Point, c: Point) -> float:
    return (
        (b[0] - a[0]) * (c[1] - a[1])
        - (b[1] - a[1]) * (c[0] - a[0])
    )


def _point_on_segment(a: Point, b: Point, p: Point) -> bool:
    return (
        min(a[0], b[0]) - _INTERSECTION_TOL
        <= p[0]
        <= max(a[0], b[0]) + _INTERSECTION_TOL
        and min(a[1], b[1]) - _INTERSECTION_TOL
        <= p[1]
        <= max(a[1], b[1]) + _INTERSECTION_TOL
        and abs(_orientation(a, b, p)) <= _INTERSECTION_TOL
    )


def _segments_touch_or_cross(left: Edge, right: Edge) -> bool:
    a, b = left
    c, d = right
    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)

    proper = (
        (
            (o1 > _INTERSECTION_TOL and o2 < -_INTERSECTION_TOL)
            or (o1 < -_INTERSECTION_TOL and o2 > _INTERSECTION_TOL)
        )
        and (
            (o3 > _INTERSECTION_TOL and o4 < -_INTERSECTION_TOL)
            or (o3 < -_INTERSECTION_TOL and o4 > _INTERSECTION_TOL)
        )
    )
    if proper:
        return True
    return (
        _point_on_segment(a, b, c)
        or _point_on_segment(a, b, d)
        or _point_on_segment(c, d, a)
        or _point_on_segment(c, d, b)
    )


def _observation_edge(observation) -> Edge | None:
    try:
        geometry = tuple(float(value) for value in observation.geometry)
    except (TypeError, ValueError):
        return None
    if (
        len(geometry) < 4
        or not all(math.isfinite(value) for value in geometry[:4])
    ):
        return None
    a = (round(geometry[0], 6), round(geometry[1], 6))
    b = (round(geometry[2], 6), round(geometry[3], 6))
    if a == b:
        return None
    return _edge(a, b)


def _normalized_owner_geometry(scope):
    owner_map, ambiguous, groups = _equivalence_owner_map(scope)
    edges_by_owner: dict[str, set[Edge]] = defaultdict(set)
    members_by_owner: dict[str, set[str]] = defaultdict(set)
    records_by_owner: dict[str, list[object]] = defaultdict(list)
    edge_owners: dict[Edge, set[str]] = defaultdict(set)

    for record in tuple(scope.records or ()):
        source_id = str(record.wall_candidate_id)
        owner_id = owner_map[source_id]
        members_by_owner[owner_id].add(source_id)
        records_by_owner[owner_id].append(record)
        for edge in _wall_edges(record):
            edges_by_owner[owner_id].add(edge)
            edge_owners[edge].add(owner_id)

    return (
        owner_map,
        ambiguous,
        groups,
        edges_by_owner,
        members_by_owner,
        records_by_owner,
        edge_owners,
    )


def _derive_faces(scope, edge_owners):
    conflicting_edges = {
        edge for edge, owners in edge_owners.items() if len(owners) != 1
    }
    conflicting_owners = {
        owner for edge in conflicting_edges for owner in edge_owners[edge]
    }

    raw_faces = extract_planar_faces(
        [(edge[0], edge[1]) for edge in sorted(edge_owners)],
        min_area=1e-6,
    )
    face_walls: dict[str, tuple[str, ...]] = {}
    face_areas: dict[str, float] = {}
    invalid_owners: set[str] = set()

    for raw_face in raw_faces:
        polygon = _canonical_polygon(raw_face)
        if not polygon:
            continue
        mapped: list[str] = []
        invalid = False
        for index, first in enumerate(polygon):
            second = polygon[(index + 1) % len(polygon)]
            owners = edge_owners.get(_edge(first, second), set())
            if len(owners) != 1:
                invalid_owners.update(owners)
                invalid = True
                break
            mapped.append(next(iter(owners)))
        if invalid:
            continue

        face_id = stable_contract_id(
            "component_local_source_room_face",
            {
                "document_id": scope.document_id,
                "revision_id": scope.revision_id,
                "source_sha256": scope.source_sha256,
                "snapshot_id": scope.snapshot_id,
                "page_id": scope.page_id,
                "decision_scope_id": scope.decision_scope_id,
                "polygon": polygon,
            },
            digest_chars=32,
        )
        face_walls[face_id] = tuple(sorted(set(mapped)))
        face_areas[face_id] = _polygon_area(polygon)

    return face_walls, face_areas, conflicting_owners, invalid_owners


def _components_from_faces(
    owners: Iterable[str],
    face_walls: dict[str, tuple[str, ...]],
) -> tuple[tuple[str, ...], ...]:
    owners = tuple(sorted(set(owners)))
    parent = {owner: owner for owner in owners}

    def find(owner: str) -> str:
        while parent[owner] != owner:
            parent[owner] = parent[parent[owner]]
            owner = parent[owner]
        return owner

    def union(left: str, right: str) -> None:
        a, b = find(left), find(right)
        if a != b:
            parent[max(a, b)] = min(a, b)

    for face_owner_ids in face_walls.values():
        row = tuple(sorted(set(face_owner_ids)))
        if row:
            for other in row[1:]:
                union(row[0], other)

    grouped: dict[str, set[str]] = defaultdict(set)
    for owner in owners:
        grouped[find(owner)].add(owner)
    return tuple(
        tuple(sorted(values))
        for _root, values in sorted(grouped.items())
    )


def _replay_withheld_edges(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    scope,
) -> tuple[tuple[tuple[str, Edge], ...], bool]:
    withheld_ids = tuple(
        sorted(
            set(tuple(scope.scope_boundary_observation_ids or ()))
            | set(tuple(scope.ambiguous_source_observation_ids or ()))
        )
    )
    if not withheld_ids:
        return (), True

    authority = source_visibility_producer.authority()
    rows: list[tuple[str, Edge]] = []
    for observation_id in withheld_ids:
        result = authority.resolve_visible(
            ObservationSelector(
                document_id=scope.document_id,
                revision_id=scope.revision_id,
                source_sha256=scope.source_sha256,
                snapshot_id=scope.snapshot_id,
                observation_id=observation_id,
            )
        )
        if (
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or result.observation is None
        ):
            return (), False
        edge = _observation_edge(result.observation)
        if edge is None:
            return (), False
        rows.append((str(observation_id), edge))
    return tuple(rows), True


def _scope_page_size(
    source_visibility_producer: SourceVisibilityProducer,
    scope,
) -> tuple[float, float] | None:
    published = source_visibility_producer.published_snapshot_for_revision(
        scope.revision_id
    )
    if (
        published is None
        or published.revision.document_id != scope.document_id
        or published.revision.source_sha256 != scope.source_sha256
        or published.snapshot.snapshot_id != scope.snapshot_id
    ):
        return None

    store = source_visibility_producer._producer._store
    source_bytes = store.source_bytes_by_revision.get(scope.revision_id)
    if source_bytes is None:
        return None
    if not store.source_bytes_match_revision(
        scope.revision_id,
        source_bytes,
        scope.source_sha256,
    ):
        return None

    doc = fitz.open(stream=source_bytes, filetype="pdf")
    try:
        page_number = int(scope.page_id)
        if not 1 <= page_number <= doc.page_count:
            return None
        page = doc.load_page(page_number - 1)
        return float(page.rect.width), float(page.rect.height)
    finally:
        doc.close()


def _component_is_locally_complete(
    *,
    scope,
    component: tuple[str, ...],
    records_by_owner: dict[str, list[object]],
    edges_by_owner: dict[str, set[Edge]],
    members_by_owner: dict[str, set[str]],
    withheld_edges: tuple[tuple[str, Edge], ...],
    withheld_replay_complete: bool,
    page_size: tuple[float, float],
) -> bool:
    if scope.scope_complete:
        return True

    if not withheld_replay_complete or scope.viewport_bbox is None:
        return False

    page_width, page_height = page_size
    for owner in component:
        for record in records_by_owner[owner]:
            reason = _viewport_scope_boundary_reason(
                record.wall_candidate,
                bbox=scope.viewport_bbox,
                page_width=page_width,
                page_height=page_height,
            )
            if reason is not None:
                return False

    component_edges = tuple(
        edge
        for owner in component
        for edge in edges_by_owner[owner]
    )
    for _observation_id, withheld_edge in withheld_edges:
        if any(
            _segments_touch_or_cross(withheld_edge, component_edge)
            for component_edge in component_edges
        ):
            return False
    return True


def _derive_scope(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    scope,
) -> tuple[dict[TopologyKey, WallTopologyEvidence], tuple[ComponentLocalTopologyProof, ...]]:
    if (
        scope.status is not EvidenceResolutionStatus.CORROBORATED
        or not scope.records
    ):
        return {}, ()
    if (
        getattr(scope, "scope_kind", "page") == "viewport"
        and str(getattr(scope, "viewport_view_type", "") or "") != "floor_plan"
    ):
        return {}, ()

    page_size = _scope_page_size(source_visibility_producer, scope)
    if page_size is None:
        return {}, ()

    (
        _owner_map,
        ambiguous_ids,
        equivalence_groups,
        edges_by_owner,
        members_by_owner,
        records_by_owner,
        edge_owners,
    ) = _normalized_owner_geometry(scope)
    if not edge_owners:
        return {}, ()

    (
        face_walls,
        face_areas,
        conflicting_owners,
        invalid_owners,
    ) = _derive_faces(scope, edge_owners)
    if not face_walls:
        return {}, ()

    largest_area = max(face_areas.values())
    tiny_faces = {
        face_id
        for face_id, area in face_areas.items()
        if (
            area < _ABSOLUTE_DEGENERATE_AREA_PT2
            or (
                largest_area > 0.0
                and area < _TINY_RELATIVE_THRESHOLD * largest_area
            )
        )
    }

    wall_faces: dict[str, set[str]] = {
        owner: set() for owner in edges_by_owner
    }
    for face_id, owners in face_walls.items():
        for owner in owners:
            if owner in wall_faces:
                wall_faces[owner].add(face_id)

    withheld_edges, replay_complete = _replay_withheld_edges(
        source_visibility_producer=source_visibility_producer,
        scope=scope,
    )

    results: dict[TopologyKey, WallTopologyEvidence] = {}
    proofs: list[ComponentLocalTopologyProof] = []

    for component in _components_from_faces(edges_by_owner, face_walls):
        component_set = set(component)
        component_faces = set().union(
            *(wall_faces[owner] for owner in component)
        )
        has_two_sided = any(
            len(wall_faces[owner]) == 2 for owner in component
        )
        if (
            len(component_faces) < 2
            or not has_two_sided
            or component_set & conflicting_owners
            or component_set & invalid_owners
            or component_faces & tiny_faces
        ):
            continue

        if not _component_is_locally_complete(
            scope=scope,
            component=component,
            records_by_owner=records_by_owner,
            edges_by_owner=edges_by_owner,
            members_by_owner=members_by_owner,
            withheld_edges=withheld_edges,
            withheld_replay_complete=replay_complete,
            page_size=page_size,
        ):
            continue

        source_candidate_ids = tuple(
            sorted(
                wall_id
                for owner in component
                for wall_id in members_by_owner[owner]
            )
        )
        groups_used = tuple(
            group
            for group in equivalence_groups
            if set(group) & set(source_candidate_ids)
        )
        checked_ids = tuple(
            observation_id for observation_id, _edge_value in withheld_edges
        )
        proof_payload = {
            "document_id": scope.document_id,
            "revision_id": scope.revision_id,
            "source_sha256": scope.source_sha256,
            "snapshot_id": scope.snapshot_id,
            "page_id": scope.page_id,
            "decision_scope_id": scope.decision_scope_id,
            "component_wall_ids": component,
            "source_candidate_wall_ids": source_candidate_ids,
            "withheld_observation_ids_checked": checked_ids,
            "equivalence_groups_used": groups_used,
            "scope_was_globally_complete": bool(scope.scope_complete),
        }
        proof = ComponentLocalTopologyProof(
            proof_id=stable_contract_id(
                "component_local_wall_topology_proof",
                proof_payload,
                digest_chars=32,
            ),
            **proof_payload,
        )
        proofs.append(proof)

        for owner in component:
            face_ids = tuple(sorted(wall_faces[owner]))
            count = len(face_ids)
            if count not in (1, 2):
                continue
            payload = {
                "document_id": scope.document_id,
                "revision_id": scope.revision_id,
                "source_sha256": scope.source_sha256,
                "snapshot_id": scope.snapshot_id,
                "page_id": scope.page_id,
                "decision_scope_id": scope.decision_scope_id,
                "physical_wall_id": owner,
                "face_ids": face_ids,
                "component_proof_id": proof.proof_id,
            }
            evidence = WallTopologyEvidence(
                evidence_id=stable_contract_id(
                    "component_local_source_wall_topology",
                    payload,
                    digest_chars=32,
                ),
                document_id=scope.document_id,
                revision_id=scope.revision_id,
                source_sha256=scope.source_sha256,
                snapshot_id=scope.snapshot_id,
                page_id=scope.page_id,
                physical_wall_id=owner,
                bounds_exterior=(count == 1),
                decision_scope_id=scope.decision_scope_id,
                enclosed_space_count=count,
                enclosed_space_ids=face_ids,
                is_ambiguous=False,
                ambiguity_reason=None,
            )
            key = (
                scope.document_id,
                scope.revision_id,
                scope.source_sha256,
                scope.snapshot_id,
                scope.page_id,
                scope.decision_scope_id,
                owner,
            )
            results[key] = evidence

    return results, tuple(proofs)


def build_component_local_source_wall_topology_authority(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
) -> WallTopologyAuthority:
    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError(
            "source_visibility_producer must be producer-owned SourceVisibilityProducer"
        )
    if type(physical_wall_candidate_authority) is not PhysicalWallCandidateAuthority:
        raise TypeError(
            "physical_wall_candidate_authority must be producer-owned "
            "PhysicalWallCandidateAuthority"
        )

    records: dict[TopologyKey, WallTopologyEvidence] = {}
    proofs: list[ComponentLocalTopologyProof] = []
    for scope in physical_wall_candidate_authority._scopes.values():
        derived, scope_proofs = _derive_scope(
            source_visibility_producer=source_visibility_producer,
            scope=scope,
        )
        records.update(derived)
        proofs.extend(scope_proofs)

    authority = WallTopologyAuthority(records, _seal=_AUTHORITY_SEAL)
    # Use the existing source-topology provenance seal so WallRoleProducer can
    # consume this authority without opening a second trust boundary.
    object.__setattr__(
        authority,
        "_source_topology_provenance_seal",
        _SOURCE_TOPOLOGY_AUTHORITY_SEAL,
    )
    object.__setattr__(
        authority,
        "_component_local_topology_provenance",
        COMPONENT_LOCAL_TOPOLOGY_PROVENANCE,
    )
    object.__setattr__(
        authority,
        "_component_local_topology_proofs",
        MappingProxyType({proof.proof_id: proof for proof in proofs}),
    )
    return authority


__all__ = [
    "COMPONENT_LOCAL_TOPOLOGY_PROVENANCE",
    "COMPONENT_LOCAL_TOPOLOGY_SCHEMA_VERSION",
    "ComponentLocalTopologyProof",
    "build_component_local_source_wall_topology_authority",
]
