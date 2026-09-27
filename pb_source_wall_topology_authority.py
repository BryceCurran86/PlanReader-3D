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
    WallRoleClassification,
    WallTopologyAuthority,
    WallTopologyEvidence,
    WallTopologyIntervalIncidence,
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


def _directed_wall_edges(record) -> tuple[tuple[Edge, Point, Point], ...]:
    """Return atomic wall edges with producer-owned centerline direction."""
    points = tuple(
        _point(point)
        for point in (
            getattr(record.wall_candidate, "centerline_pts", ()) or ()
        )
    )
    result = []
    for first, second in zip(points, points[1:]):
        edge = _edge(first, second)
        if edge[0] != edge[1]:
            result.append((edge, first, second))
    return tuple(result)


def _ambiguous_record(scope, wall_id: str, reason: str) -> WallTopologyEvidence:
    payload = {
        "document_id": scope.document_id,
        "revision_id": scope.revision_id,
        "source_sha256": scope.source_sha256,
        "snapshot_id": scope.snapshot_id,
        "page_id": scope.page_id,
        "decision_scope_id": scope.decision_scope_id,
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
        decision_scope_id=scope.decision_scope_id,
        enclosed_space_count=0,
        enclosed_space_ids=(),
        is_ambiguous=True,
        ambiguity_reason=reason,
        interval_incidence=(),
    )


def _derive_scope_records(scope) -> dict[tuple[str, str, str, str, str, str, str], WallTopologyEvidence]:
    records = tuple(scope.records or ())
    if (
        scope.status is not EvidenceResolutionStatus.CORROBORATED
        or not scope.scope_complete
        or not records
    ):
        return {}

    wall_edges: dict[str, tuple[Edge, ...]] = {}
    directed_edges_by_wall: dict[
        str, tuple[tuple[Edge, Point, Point], ...]
    ] = {}
    edge_owner: dict[Edge, str] = {}
    duplicate_edges: set[Edge] = set()
    endpoints_by_wall: dict[str, set[Point]] = {}

    for record in records:
        wall_id = str(record.wall_candidate_id)
        edges = _wall_edges(record)
        if not edges:
            continue
        wall_edges[wall_id] = edges
        directed_edges_by_wall[wall_id] = _directed_wall_edges(record)
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
            (scope.document_id, scope.revision_id, scope.source_sha256, scope.snapshot_id, scope.page_id, scope.decision_scope_id, wall_id):
                _ambiguous_record(scope, wall_id, "duplicate_wall_edge_ownership")
            for wall_id in wall_ids
        }

    raw_segments = [(edge[0], edge[1]) for wall_id in wall_ids for edge in wall_edges[wall_id]]
    raw_faces = extract_planar_faces(raw_segments, min_area=1e-6)

    faces: dict[str, tuple[Point, ...]] = {}
    face_walls: dict[str, tuple[str, ...]] = {}
    face_areas: dict[str, float] = {}
    # wall_id -> canonical atomic edge -> {"left": face ids, "right": face ids}
    interval_faces: dict[
        str, dict[Edge, dict[str, set[str]]]
    ] = {
        wall_id: {
            edge: {"left": set(), "right": set()}
            for edge in wall_edges[wall_id]
        }
        for wall_id in wall_ids
    }
    directed_lookup: dict[tuple[str, Edge], tuple[Point, Point]] = {
        (wall_id, edge): (first, second)
        for wall_id, rows in directed_edges_by_wall.items()
        for edge, first, second in rows
    }
    invalid_boundary = False

    for raw_face in raw_faces:
        polygon = _canonical_polygon(raw_face)
        if not polygon:
            continue
        mapped: list[str] = []
        traversed: list[tuple[str, Edge, Point, Point]] = []
        raw_points = tuple(_point(point) for point in raw_face)
        for index, raw_first in enumerate(raw_points):
            raw_second = raw_points[(index + 1) % len(raw_points)]
            edge = _edge(raw_first, raw_second)
            owner = edge_owner.get(edge)
            if owner is None:
                invalid_boundary = True
                break
            directed = directed_lookup.get((owner, edge))
            if directed is None:
                invalid_boundary = True
                break
            mapped.append(owner)
            traversed.append((owner, edge, raw_first, raw_second))
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
                "decision_scope_id": scope.decision_scope_id,
                "polygon": polygon,
            },
            digest_chars=32,
        )
        faces[face_id] = polygon
        face_walls[face_id] = tuple(sorted(set(mapped)))
        face_areas[face_id] = _polygon_area(polygon)

        # extract_planar_faces traverses every retained bounded face with the
        # face on the LEFT of its directed half-edge. Compare that traversal
        # with each producer-owned wall interval direction to retain oriented
        # side incidence without centroid/proximity heuristics.
        for owner, edge, raw_first, raw_second in traversed:
            directed_first, directed_second = directed_lookup[(owner, edge)]
            if (
                raw_first == directed_first
                and raw_second == directed_second
            ):
                side = "left"
            elif (
                raw_first == directed_second
                and raw_second == directed_first
            ):
                side = "right"
            else:
                invalid_boundary = True
                break
            interval_faces[owner][edge][side].add(face_id)
        if invalid_boundary:
            break

    if invalid_boundary or not faces:
        return {
            (scope.document_id, scope.revision_id, scope.source_sha256, scope.snapshot_id, scope.page_id, scope.decision_scope_id, wall_id):
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
            (scope.document_id, scope.revision_id, scope.source_sha256, scope.snapshot_id, scope.page_id, scope.decision_scope_id, wall_id):
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

    results: dict[tuple[str, str, str, str, str, str, str], WallTopologyEvidence] = {}
    for component in component_walls.values():
        component_faces = set().union(*(wall_faces[wall_id] for wall_id in component))
        has_two_sided_interval = any(
            bool(sides["left"]) and bool(sides["right"])
            for wall_id in component
            for sides in interval_faces[wall_id].values()
        )
        component_resolved = (
            len(component_faces) >= 2 and has_two_sided_interval
        )

        for wall_id in sorted(component):
            face_ids = tuple(sorted(wall_faces[wall_id]))
            count = len(face_ids)
            interval_rows: list[WallTopologyIntervalIncidence] = []
            interval_roles: list[WallRoleClassification] = []
            interval_reason = None

            for edge, directed_first, directed_second in directed_edges_by_wall[wall_id]:
                sides = interval_faces[wall_id].get(
                    edge, {"left": set(), "right": set()}
                )
                left_ids = tuple(sorted(sides["left"]))
                right_ids = tuple(sorted(sides["right"]))
                ambiguous_interval = False
                reason_code = None

                # A simple embedded atomic edge can have at most one bounded
                # face per oriented side. More than one on one side means the
                # arrangement/ownership is not exact enough for role authority.
                if len(left_ids) > 1 or len(right_ids) > 1:
                    role = WallRoleClassification.UNRESOLVED
                    ambiguous_interval = True
                    reason_code = "interval_side_face_cardinality_ambiguous"
                elif set(left_ids) & set(right_ids):
                    role = WallRoleClassification.UNRESOLVED
                    ambiguous_interval = True
                    reason_code = "same_face_incident_on_both_wall_sides"
                elif left_ids and right_ids:
                    role = WallRoleClassification.INTERNAL
                elif left_ids or right_ids:
                    role = WallRoleClassification.EXTERNAL
                else:
                    role = WallRoleClassification.UNRESOLVED
                    ambiguous_interval = True
                    reason_code = "interval_has_no_bounded_face_incidence"

                interval_payload = {
                    "document_id": scope.document_id,
                    "revision_id": scope.revision_id,
                    "source_sha256": scope.source_sha256,
                    "snapshot_id": scope.snapshot_id,
                    "page_id": scope.page_id,
                    "decision_scope_id": scope.decision_scope_id,
                    "physical_wall_id": wall_id,
                    "start_pt": directed_first,
                    "end_pt": directed_second,
                    "left_space_ids": left_ids,
                    "right_space_ids": right_ids,
                    "role": role.value,
                    "ambiguous": ambiguous_interval,
                }
                interval_rows.append(
                    WallTopologyIntervalIncidence(
                        evidence_id=stable_contract_id(
                            "source_wall_topology_interval",
                            interval_payload,
                            digest_chars=32,
                        ),
                        start_pt=directed_first,
                        end_pt=directed_second,
                        left_space_ids=left_ids,
                        right_space_ids=right_ids,
                        role=role,
                        is_ambiguous=ambiguous_interval,
                        ambiguity_reason=reason_code,
                    )
                )
                interval_roles.append(role)
                if reason_code is not None and interval_reason is None:
                    interval_reason = reason_code

            resolved_roles = {
                role
                for role in interval_roles
                if role in (
                    WallRoleClassification.EXTERNAL,
                    WallRoleClassification.INTERNAL,
                )
            }
            has_unresolved_interval = any(
                role is WallRoleClassification.UNRESOLVED
                for role in interval_roles
            )
            mixed_roles = len(resolved_roles) > 1

            ambiguous = (
                not component_resolved
                or not interval_rows
                or has_unresolved_interval
                or mixed_roles
            )
            reason = None
            if not component_resolved:
                reason = "component_lacks_multiroom_topology"
            elif not interval_rows or has_unresolved_interval:
                reason = interval_reason or "interval_side_incidence_unresolved"
            elif mixed_roles:
                reason = "mixed_wall_interval_roles"

            all_external = (
                not ambiguous
                and resolved_roles == {WallRoleClassification.EXTERNAL}
            )
            all_internal = (
                not ambiguous
                and resolved_roles == {WallRoleClassification.INTERNAL}
            )
            if not ambiguous and not (all_external or all_internal):
                ambiguous = True
                reason = "interval_role_profile_unresolved"

            payload = {
                "document_id": scope.document_id,
                "revision_id": scope.revision_id,
                "source_sha256": scope.source_sha256,
                "snapshot_id": scope.snapshot_id,
                "page_id": scope.page_id,
                "decision_scope_id": scope.decision_scope_id,
                "physical_wall_id": wall_id,
                "face_ids": face_ids,
                "interval_incidence_ids": [
                    interval.evidence_id for interval in interval_rows
                ],
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
                bounds_exterior=all_external,
                decision_scope_id=scope.decision_scope_id,
                enclosed_space_count=count,
                enclosed_space_ids=face_ids,
                is_ambiguous=ambiguous,
                ambiguity_reason=reason,
                interval_incidence=tuple(interval_rows),
            )
            results[
                (
                    scope.document_id,
                    scope.revision_id,
                    scope.source_sha256,
                    scope.snapshot_id,
                    scope.page_id,
                    scope.decision_scope_id,
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

    records: dict[tuple[str, str, str, str, str, str, str], WallTopologyEvidence] = {}
    for scope in physical_wall_candidate_authority._scopes.values():
        # Room/envelope topology is a plan-view proposition. Viewport-scoped
        # elevation/section/detail geometry remains valid physical-wall
        # evidence, but it must not mint EXTERNAL/INTERNAL roles by being
        # interpreted as a planar room graph.
        if (
            getattr(scope, "scope_kind", "page") == "viewport"
            and str(getattr(scope, "viewport_view_type", "") or "") != "floor_plan"
        ):
            continue
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
