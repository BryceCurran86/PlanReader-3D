"""Source-derived wall/envelope topology evidence for Item 26.

This adapter consumes only a producer-owned PhysicalWallCandidateAuthority.
It derives bounded planar faces from authenticated wall centerlines and publishes
WallTopologyEvidence only where external/internal role is topologically exact.

Positive publication is intentionally narrow:
- the physical wall scope must be CORROBORATED and complete;
- every face boundary edge must map to exactly one authenticated wall;
- tiny/degenerate faces make the scope ambiguous;
- a connected component must contain at least two bounded faces and at least
  one two-sided wall, preventing single-loop title blocks / boxes from becoming
  exterior-wall authority;
- one bounded face => EXTERNAL boundary; two bounded faces => INTERNAL divider;
- zero, >2, or inconsistent face memberships remain ambiguous.

No candidate interior/exterior label, thickness, perimeter rank, page/project
identity, benchmark value, or caller role hint participates in the proof.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from pb_accuracy_v13_engines_v145 import extract_planar_faces
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_wall_candidate_authority import PhysicalWallCandidateAuthority
from pb_wall_role_authority import (
    WallTopologyAuthority,
    WallTopologyEvidence,
    _AUTHORITY_SEAL,
)

SOURCE_WALL_TOPOLOGY_SCHEMA_VERSION = "1.0.0"
SOURCE_WALL_TOPOLOGY_PROVENANCE = "source_derived_physical_wall_face_topology"
_SOURCE_TOPOLOGY_AUTHORITY_SEAL = object()

_ABSOLUTE_DEGENERATE_AREA_PT2 = 1.0
_TINY_RELATIVE_THRESHOLD = 0.01
_NDIGITS = 6

Point = tuple[float, float]
Edge = tuple[Point, Point]


def _point(value: Iterable[float]) -> Point:
    x, y = value
    return (round(float(x), _NDIGITS), round(float(y), _NDIGITS))


def _edge(first: Iterable[float], second: Iterable[float]) -> Edge:
    a, b = _point(first), _point(second)
    return (a, b) if a <= b else (b, a)


def _polygon_area(points: tuple[Point, ...]) -> float:
    total = 0.0
    for index, (x1, y1) in enumerate(points):
        x2, y2 = points[(index + 1) % len(points)]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def _canonical_polygon(points: Iterable[Iterable[float]]) -> tuple[Point, ...]:
    cleaned = tuple(_point(point) for point in points)
    if len(cleaned) < 3:
        return ()
    variants: list[tuple[Point, ...]] = []
    for start in range(len(cleaned)):
        variants.append(tuple(cleaned[(start + i) % len(cleaned)] for i in range(len(cleaned))))
        variants.append(tuple(cleaned[(start - i) % len(cleaned)] for i in range(len(cleaned))))
    return min(variants)


def _wall_edges(record) -> tuple[Edge, ...]:
    points = tuple(getattr(record.wall_candidate, "centerline_pts", ()) or ())
    if len(points) < 2:
        return ()
    result = []
    for first, second in zip(points, points[1:]):
        edge = _edge(first, second)
        if edge[0] != edge[1]:
            result.append(edge)
    return tuple(result)


def _ambiguous_record(scope, wall_id: str, reason: str) -> WallTopologyEvidence:
    payload = {
        "document_id": scope.document_id,
        "revision_id": scope.revision_id,
        "source_sha256": scope.source_sha256,
        "snapshot_id": scope.snapshot_id,
        "page_id": scope.page_id,
        "physical_wall_id": wall_id,
        "reason": reason,
    }
    return WallTopologyEvidence(
        evidence_id=stable_contract_id("source_wall_topology", payload, digest_chars=32),
        document_id=scope.document_id,
        revision_id=scope.revision_id,
        source_sha256=scope.source_sha256,
        snapshot_id=scope.snapshot_id,
        page_id=scope.page_id,
        physical_wall_id=wall_id,
        bounds_exterior=False,
        enclosed_space_count=0,
        enclosed_space_ids=(),
        is_ambiguous=True,
        ambiguity_reason=reason,
    )


def _derive_scope_records(scope) -> dict[tuple[str, str, str, str, str, str], WallTopologyEvidence]:
    records = tuple(scope.records or ())
    if (
        scope.status is not EvidenceResolutionStatus.CORROBORATED
        or not scope.scope_complete
        or not records
    ):
        return {}

    wall_edges: dict[str, tuple[Edge, ...]] = {}
    edge_owner: dict[Edge, str] = {}
    duplicate_edges: set[Edge] = set()
    endpoints_by_wall: dict[str, set[Point]] = {}

    for record in records:
        wall_id = str(record.wall_candidate_id)
        edges = _wall_edges(record)
        if not edges:
            continue
        wall_edges[wall_id] = edges
        endpoints_by_wall[wall_id] = {point for edge in edges for point in edge}
        for edge in edges:
            prior = edge_owner.get(edge)
            if prior is not None and prior != wall_id:
                duplicate_edges.add(edge)
            else:
                edge_owner[edge] = wall_id

    wall_ids = tuple(sorted(wall_edges))
    if not wall_ids:
        return {}

    if duplicate_edges:
        return {
            (scope.document_id, scope.revision_id, scope.source_sha256, scope.snapshot_id, scope.page_id, wall_id):
                _ambiguous_record(scope, wall_id, "duplicate_wall_edge_ownership")
            for wall_id in wall_ids
        }

    raw_segments = [(edge[0], edge[1]) for wall_id in wall_ids for edge in wall_edges[wall_id]]
    raw_faces = extract_planar_faces(raw_segments, min_area=1e-6)

    faces: dict[str, tuple[Point, ...]] = {}
    face_walls: dict[str, tuple[str, ...]] = {}
    face_areas: dict[str, float] = {}
    invalid_boundary = False

    for raw_face in raw_faces:
        polygon = _canonical_polygon(raw_face)
        if not polygon:
            continue
        mapped: list[str] = []
        for index, first in enumerate(polygon):
            second = polygon[(index + 1) % len(polygon)]
            owner = edge_owner.get(_edge(first, second))
            if owner is None:
                invalid_boundary = True
                break
            mapped.append(owner)
        if invalid_boundary:
            break
        face_id = stable_contract_id(
            "source_room_face",
            {
                "document_id": scope.document_id,
                "revision_id": scope.revision_id,
                "source_sha256": scope.source_sha256,
                "snapshot_id": scope.snapshot_id,
                "page_id": scope.page_id,
                "polygon": polygon,
            },
            digest_chars=32,
        )
        faces[face_id] = polygon
        face_walls[face_id] = tuple(sorted(set(mapped)))
        face_areas[face_id] = _polygon_area(polygon)

    if invalid_boundary or not faces:
        return {
            (scope.document_id, scope.revision_id, scope.source_sha256, scope.snapshot_id, scope.page_id, wall_id):
                _ambiguous_record(scope, wall_id, "room_face_boundary_unresolved")
            for wall_id in wall_ids
        }

    largest_area = max(face_areas.values())
    if any(
        area < _ABSOLUTE_DEGENERATE_AREA_PT2
        or (largest_area > 0.0 and area < _TINY_RELATIVE_THRESHOLD * largest_area)
        for area in face_areas.values()
    ):
        return {
            (scope.document_id, scope.revision_id, scope.source_sha256, scope.snapshot_id, scope.page_id, wall_id):
                _ambiguous_record(scope, wall_id, "tiny_or_degenerate_room_face")
            for wall_id in wall_ids
        }

    wall_faces: dict[str, set[str]] = {wall_id: set() for wall_id in wall_ids}
    for face_id, owners in face_walls.items():
        for wall_id in owners:
            if wall_id in wall_faces:
                wall_faces[wall_id].add(face_id)

    # Connected components are wall-topology components, not page-position groups.
    parent = {wall_id: wall_id for wall_id in wall_ids}

    def find(wall_id: str) -> str:
        while parent[wall_id] != wall_id:
            parent[wall_id] = parent[parent[wall_id]]
            wall_id = parent[wall_id]
        return wall_id

    def union(left: str, right: str) -> None:
        a, b = find(left), find(right)
        if a != b:
            parent[max(a, b)] = min(a, b)

    for index, left in enumerate(wall_ids):
        for right in wall_ids[index + 1 :]:
            if endpoints_by_wall[left] & endpoints_by_wall[right]:
                union(left, right)

    component_walls: dict[str, set[str]] = defaultdict(set)
    for wall_id in wall_ids:
        component_walls[find(wall_id)].add(wall_id)

    results: dict[tuple[str, str, str, str, str, str], WallTopologyEvidence] = {}
    for component in component_walls.values():
        component_faces = set().union(*(wall_faces[wall_id] for wall_id in component))
        has_two_sided_wall = any(len(wall_faces[wall_id]) == 2 for wall_id in component)
        component_resolved = len(component_faces) >= 2 and has_two_sided_wall

        for wall_id in sorted(component):
            face_ids = tuple(sorted(wall_faces[wall_id]))
            count = len(face_ids)
            ambiguous = not component_resolved or count not in (1, 2)
            reason = None
            if not component_resolved:
                reason = "component_lacks_multiroom_topology"
            elif count not in (1, 2):
                reason = "wall_face_adjacency_not_exact"

            payload = {
                "document_id": scope.document_id,
                "revision_id": scope.revision_id,
                "source_sha256": scope.source_sha256,
                "snapshot_id": scope.snapshot_id,
                "page_id": scope.page_id,
                "physical_wall_id": wall_id,
                "face_ids": face_ids,
                "ambiguous": ambiguous,
            }
            evidence = WallTopologyEvidence(
                evidence_id=stable_contract_id("source_wall_topology", payload, digest_chars=32),
                document_id=scope.document_id,
                revision_id=scope.revision_id,
                source_sha256=scope.source_sha256,
                snapshot_id=scope.snapshot_id,
                page_id=scope.page_id,
                physical_wall_id=wall_id,
                bounds_exterior=(count == 1 and not ambiguous),
                enclosed_space_count=count,
                enclosed_space_ids=face_ids,
                is_ambiguous=ambiguous,
                ambiguity_reason=reason,
            )
            results[
                (
                    scope.document_id,
                    scope.revision_id,
                    scope.source_sha256,
                    scope.snapshot_id,
                    scope.page_id,
                    wall_id,
                )
            ] = evidence

    return results


def build_source_wall_topology_authority(
    physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
) -> WallTopologyAuthority:
    """Derive sealed wall topology evidence from producer-owned wall scopes only."""

    if type(physical_wall_candidate_authority) is not PhysicalWallCandidateAuthority:
        raise TypeError(
            "physical_wall_candidate_authority must be producer-owned PhysicalWallCandidateAuthority"
        )

    records: dict[tuple[str, str, str, str, str, str], WallTopologyEvidence] = {}
    for scope in physical_wall_candidate_authority._scopes.values():
        records.update(_derive_scope_records(scope))

    authority = WallTopologyAuthority(records, _seal=_AUTHORITY_SEAL)
    object.__setattr__(
        authority,
        "_source_topology_provenance_seal",
        _SOURCE_TOPOLOGY_AUTHORITY_SEAL,
    )
    return authority


def is_source_wall_topology_authority(authority: object) -> bool:
    return (
        type(authority) is WallTopologyAuthority
        and getattr(authority, "_source_topology_provenance_seal", None)
        is _SOURCE_TOPOLOGY_AUTHORITY_SEAL
    )


__all__ = [
    "SOURCE_WALL_TOPOLOGY_PROVENANCE",
    "SOURCE_WALL_TOPOLOGY_SCHEMA_VERSION",
    "build_source_wall_topology_authority",
    "is_source_wall_topology_authority",
]
