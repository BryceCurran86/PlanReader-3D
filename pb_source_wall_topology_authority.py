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
from dataclasses import replace
from typing import Iterable, Optional

from pb_accuracy_v13_engines_v145 import extract_planar_faces
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_wall_candidate_authority import PhysicalWallCandidateAuthority
from pb_wall_component_completeness_authority import (
    WALL_COMPONENT_COMPLETE,
    WallComponentCompletenessAuthority,
    WallComponentCompletenessSelector,
    _component_sets,
    _raw_path_family,
)
from pb_wall_room_topology_contracts import JunctionType
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


def _point_on_edge(point: Point, edge: Edge, tol: float = 1e-6) -> bool:
    (ax, ay), (bx, by) = edge
    px, py = point
    cross = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
    scale = max(1.0, abs(bx - ax), abs(by - ay))
    if abs(cross) > tol * scale:
        return False
    return (
        min(ax, bx) - tol <= px <= max(ax, bx) + tol
        and min(ay, by) - tol <= py <= max(ay, by) + tol
    )


def _face_edge_owner(
    face_edge: Edge,
    edge_owner: dict[Edge, str],
) -> str | None:
    """Map an intersection-split face edge to exactly one source wall owner.

    extract_planar_faces() splits source segments at junctions before returning
    face polygons.  A returned polygon edge can therefore be a strict
    subsegment of one authenticated wall edge.  Exact equality is preferred;
    otherwise both subsegment endpoints must lie on one and only one source
    wall edge.  Multiple physical owners remain ambiguous.
    """
    exact = edge_owner.get(face_edge)
    if exact is not None:
        return exact
    owners = {
        owner
        for source_edge, owner in edge_owner.items()
        if _point_on_edge(face_edge[0], source_edge)
        and _point_on_edge(face_edge[1], source_edge)
    }
    return next(iter(owners)) if len(owners) == 1 else None


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
            (scope.document_id, scope.revision_id, scope.source_sha256, scope.snapshot_id, scope.page_id, scope.decision_scope_id, wall_id):
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
            owner = _face_edge_owner(_edge(first, second), edge_owner)
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
                "decision_scope_id": scope.decision_scope_id,
                "polygon": polygon,
            },
            digest_chars=32,
        )
        faces[face_id] = polygon
        face_walls[face_id] = tuple(sorted(set(mapped)))
        face_areas[face_id] = _polygon_area(polygon)

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
                "decision_scope_id": scope.decision_scope_id,
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
                decision_scope_id=scope.decision_scope_id,
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
                    scope.decision_scope_id,
                    wall_id,
                )
            ] = evidence

    return results



def _component_topology_records(
    scope,
    completeness_authority: WallComponentCompletenessAuthority,
) -> dict[tuple[str, str, str, str, str, str, str], WallTopologyEvidence]:
    """Derive topology only for producer-proven complete wall components.

    The source viewport remains globally incomplete. This helper never changes
    that proposition. It constructs a temporary complete topology scope only
    from the exact member set sealed by WallComponentCompletenessAuthority.
    """
    if (
        scope.status is not EvidenceResolutionStatus.CORROBORATED
        or scope.scope_complete
        or getattr(scope, "scope_kind", "page") != "viewport"
        or str(getattr(scope, "viewport_view_type", "") or "") != "floor_plan"
        or not tuple(scope.records or ())
    ):
        return {}

    by_id = {
        str(record.wall_candidate_id): record
        for record in tuple(scope.records or ())
    }
    equivalence = getattr(scope, "equivalence", None)
    seen_components: set[str] = set()
    output: dict[
        tuple[str, str, str, str, str, str, str],
        WallTopologyEvidence,
    ] = {}

    for wall_id in sorted(by_id):
        result = completeness_authority.resolve(
            WallComponentCompletenessSelector(
                document_id=scope.document_id,
                revision_id=scope.revision_id,
                source_sha256=scope.source_sha256,
                snapshot_id=scope.snapshot_id,
                page_id=scope.page_id,
                decision_scope_id=scope.decision_scope_id,
                physical_wall_id=wall_id,
            )
        )
        record = result.record
        if (
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or WALL_COMPONENT_COMPLETE not in result.reason_codes
            or record is None
            or record.status is not EvidenceResolutionStatus.CORROBORATED
        ):
            continue
        if record.record_id in seen_components:
            continue
        if (
            record.document_id != scope.document_id
            or record.revision_id != scope.revision_id
            or record.source_sha256 != scope.source_sha256
            or record.snapshot_id != scope.snapshot_id
            or record.page_id != scope.page_id
            or record.decision_scope_id != scope.decision_scope_id
            or wall_id not in record.member_wall_ids
        ):
            continue

        member_ids = set(record.member_wall_ids)
        if not member_ids or not member_ids <= set(by_id):
            continue

        # One topology representation per producer-proven physical-wall SAME
        # group. Un-grouped walls remain unchanged. We accept only an upstream
        # representative that is itself inside this component; no geometry
        # ranking or local "best" member selection is introduced here.
        keep_ids = set(member_ids)
        if equivalence is not None:
            representatives = set(
                tuple(equivalence.representative_wall_ids or ())
            )
            for group in tuple(equivalence.equivalence_groups or ()):
                group_members = member_ids & set(group)
                if not group_members:
                    continue
                group_reps = group_members & representatives
                if len(group_reps) != 1:
                    keep_ids = set()
                    break
                keep = next(iter(group_reps))
                keep_ids.difference_update(group_members - {keep})
        if not keep_ids:
            continue

        component_records = tuple(
            by_id[member]
            for member in sorted(keep_ids)
        )
        local_scope = replace(
            scope,
            scope_complete=True,
            records=component_records,
            equivalence=None,
        )
        derived = _derive_scope_records(local_scope)
        if not derived:
            continue

        seen_components.add(record.record_id)
        output.update(derived)

    return output



_PAGE_LOCAL_BLOCKING_JUNCTIONS = frozenset({
    JunctionType.ENDPOINT,
    JunctionType.UNRESOLVED,
    JunctionType.NEAR_JUNCTION_REVIEW,
    JunctionType.AMBIGUOUS,
    JunctionType.REJECTED_NON_WALL_CROSSING,
})


def _collapsed_component_records(scope, member_ids) -> tuple:
    """Return one upstream-approved representative per SAME physical wall."""
    by_id = {
        str(record.wall_candidate_id): record
        for record in tuple(scope.records or ())
    }
    members = set(str(value) for value in member_ids)
    if not members or not members <= set(by_id):
        return ()

    keep_ids = set(members)
    equivalence = getattr(scope, "equivalence", None)
    if equivalence is not None:
        representatives = set(tuple(equivalence.representative_wall_ids or ()))
        for group in tuple(equivalence.equivalence_groups or ()):
            group_members = members & set(group)
            if not group_members:
                continue
            group_reps = group_members & representatives
            if len(group_reps) != 1:
                return ()
            keep = next(iter(group_reps))
            keep_ids.difference_update(group_members - {keep})
    return tuple(by_id[wall_id] for wall_id in sorted(keep_ids))


def _page_component_is_locally_closed(records) -> bool:
    """Require producer junction evidence that leaves no unresolved wall end.

    A page can be globally incomplete because another drawing region has
    unresolved bounds. This narrower proof accepts one connected source-wall
    component only when every member has two classified ends and neither end
    is dangling, ambiguous, review-only, unresolved, or rejected.
    """
    if not records:
        return False
    for record in records:
        junctions = tuple(
            getattr(record.wall_candidate, "junction_types", ()) or ()
        )
        if len(junctions) != 2:
            return False
        normalized = []
        for raw in junctions:
            try:
                normalized.append(
                    raw if isinstance(raw, JunctionType) else JunctionType(str(raw))
                )
            except ValueError:
                return False
        if any(value in _PAGE_LOCAL_BLOCKING_JUNCTIONS for value in normalized):
            return False
    return True


def _page_local_component_topology_records(
    scope,
) -> dict[tuple[str, str, str, str, str, str, str], WallTopologyEvidence]:
    """Derive topology for closed page-local components on an incomplete page.

    This never upgrades the enclosing page scope completeness. The exact page
    wall graph is partitioned only by producer-owned physical equivalence and
    trusted junction identities.
    """
    if (
        scope.status is not EvidenceResolutionStatus.CORROBORATED
        or scope.scope_complete
        or getattr(scope, "scope_kind", "page") != "page"
        or not tuple(scope.records or ())
    ):
        return {}

    output = {}
    for members in _component_sets(scope.records, scope.equivalence):
        component_records = _collapsed_component_records(scope, members)
        if not _page_component_is_locally_closed(component_records):
            continue
        local_scope = replace(
            scope,
            scope_complete=True,
            records=component_records,
            equivalence=None,
        )
        derived = _derive_scope_records(local_scope)
        if not derived:
            continue
        if not any(not evidence.is_ambiguous for evidence in derived.values()):
            continue
        output.update(derived)
    return output


def _page_equivalence_representatives(page_scope) -> dict[str, str]:
    mapping = {
        str(record.wall_candidate_id): str(record.wall_candidate_id)
        for record in tuple(page_scope.records or ())
    }
    equivalence = getattr(page_scope, "equivalence", None)
    if equivalence is None:
        return mapping
    representatives = set(tuple(equivalence.representative_wall_ids or ()))
    for group in tuple(equivalence.equivalence_groups or ()):
        group_members = [str(value) for value in group if str(value) in mapping]
        group_reps = set(group_members) & representatives
        if len(group_reps) != 1:
            continue
        representative = next(iter(group_reps))
        for wall_id in group_members:
            mapping[wall_id] = representative
    return mapping


def _page_component_source_ids_by_wall(page_scope) -> dict[str, frozenset[str]]:
    """Map each page wall to every immutable source id in its full component.

    Topology itself may collapse producer-proven SAME representations, but the
    sibling-ownership safety check must retain the source ids of *all* members.
    Otherwise a foreign-owned duplicate could disappear behind the chosen
    representative and incorrectly make a mixed-drawing component look local.
    """
    output: dict[str, frozenset[str]] = {}
    by_id = {
        str(record.wall_candidate_id): record
        for record in tuple(page_scope.records or ())
    }
    for members in _component_sets(page_scope.records, page_scope.equivalence):
        # Preserve the same fail-closed representative gate used by topology.
        if not _collapsed_component_records(page_scope, members):
            continue
        member_records = tuple(
            by_id[str(wall_id)]
            for wall_id in members
            if str(wall_id) in by_id
        )
        if len(member_records) != len(tuple(members)):
            continue
        source_ids = frozenset(
            str(raw_id)
            for record in member_records
            for raw_id in record.physical_identity.source_primitive_ids
            if str(raw_id)
        )
        if not source_ids:
            continue
        for wall_id in members:
            output[str(wall_id)] = source_ids
    return output


def _source_path_families(source_ids) -> frozenset[str]:
    """Return immutable native-PDF path families where the raw id encodes one."""
    return frozenset(
        family
        for raw_id in source_ids
        for family in (_raw_path_family(str(raw_id)),)
        if family is not None
    )


def _foreign_sibling_source_ids(
    scopes,
    *,
    viewport_scope,
) -> frozenset[str]:
    """Return source primitives uniquely published into other sibling viewports.

    PhysicalWallCandidateProducer publishes a primitive into a viewport scope
    only when that primitive has exactly one authenticated viewport owner.
    Therefore an id present in another same-lineage viewport is positive
    evidence that it does not belong to the target drawing universe.
    """
    return frozenset(
        str(raw_id)
        for sibling in scopes
        if sibling is not viewport_scope
        and sibling.scope_kind == "viewport"
        and sibling.status is EvidenceResolutionStatus.CORROBORATED
        and sibling.document_id == viewport_scope.document_id
        and sibling.revision_id == viewport_scope.revision_id
        and sibling.source_sha256 == viewport_scope.source_sha256
        and sibling.snapshot_id == viewport_scope.snapshot_id
        and sibling.page_id == viewport_scope.page_id
        and sibling.decision_scope_id != viewport_scope.decision_scope_id
        for record in tuple(sibling.records or ())
        for raw_id in record.physical_identity.source_primitive_ids
        if str(raw_id)
    )


def _bridge_page_topology_to_viewports(
    physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
    records: dict[
        tuple[str, str, str, str, str, str, str],
        WallTopologyEvidence,
    ],
) -> dict[tuple[str, str, str, str, str, str, str], WallTopologyEvidence]:
    """Project proven page-local topology onto exact viewport wall identities.

    Every primitive owned by the viewport wall must be covered by page-wall
    candidates, every overlapping page candidate must normalize through
    producer-owned SAME equivalence to topology evidence, and all evidence must
    agree on one exact face-adjacency signature.
    """
    output = {}
    scopes = tuple(physical_wall_candidate_authority._scopes.values())
    page_scopes = [scope for scope in scopes if scope.scope_kind == "page"]

    for viewport_scope in scopes:
        if (
            viewport_scope.scope_kind != "viewport"
            or str(viewport_scope.viewport_view_type or "") != "floor_plan"
            or viewport_scope.status is not EvidenceResolutionStatus.CORROBORATED
        ):
            continue
        matches = [
            page_scope
            for page_scope in page_scopes
            if page_scope.document_id == viewport_scope.document_id
            and page_scope.revision_id == viewport_scope.revision_id
            and page_scope.source_sha256 == viewport_scope.source_sha256
            and page_scope.snapshot_id == viewport_scope.snapshot_id
            and page_scope.page_id == viewport_scope.page_id
        ]
        if len(matches) != 1:
            continue
        page_scope = matches[0]
        page_records = tuple(page_scope.records or ())
        representative_for = _page_equivalence_representatives(page_scope)
        component_source_ids_by_wall = _page_component_source_ids_by_wall(
            page_scope
        )
        foreign_sibling_source_ids = _foreign_sibling_source_ids(
            scopes,
            viewport_scope=viewport_scope,
        )
        foreign_sibling_path_families = _source_path_families(
            foreign_sibling_source_ids
        )

        topology_by_page_wall = {}
        for evidence in records.values():
            if (
                evidence.document_id == page_scope.document_id
                and evidence.revision_id == page_scope.revision_id
                and evidence.source_sha256 == page_scope.source_sha256
                and evidence.snapshot_id == page_scope.snapshot_id
                and evidence.page_id == page_scope.page_id
                and evidence.decision_scope_id == page_scope.decision_scope_id
            ):
                topology_by_page_wall[evidence.physical_wall_id] = evidence
        if not topology_by_page_wall:
            continue

        for viewport_record in tuple(viewport_scope.records or ()):
            target_ids = {
                str(raw_id)
                for raw_id in viewport_record.physical_identity.source_primitive_ids
                if str(raw_id)
            }
            if not target_ids:
                continue

            covered = set()
            normalized_page_ids = set()
            for page_record in page_records:
                page_ids = {
                    str(raw_id)
                    for raw_id in page_record.physical_identity.source_primitive_ids
                    if str(raw_id)
                }
                overlap = target_ids & page_ids
                if not overlap:
                    continue
                covered.update(overlap)
                normalized_page_ids.add(
                    representative_for.get(
                        str(page_record.wall_candidate_id),
                        str(page_record.wall_candidate_id),
                    )
                )

            if covered != target_ids or not normalized_page_ids:
                continue

            evidences = []
            unresolved = False
            for page_wall_id in sorted(normalized_page_ids):
                component_source_ids = component_source_ids_by_wall.get(
                    page_wall_id
                )
                if not component_source_ids:
                    unresolved = True
                    break
                component_path_families = _source_path_families(
                    component_source_ids
                )
                if (
                    component_source_ids & foreign_sibling_source_ids
                    or component_path_families & foreign_sibling_path_families
                ):
                    unresolved = True
                    break
                evidence = topology_by_page_wall.get(page_wall_id)
                if evidence is None or evidence.is_ambiguous:
                    unresolved = True
                    break
                evidences.append(evidence)
            if unresolved or not evidences:
                continue

            signatures = {
                (
                    bool(evidence.bounds_exterior),
                    int(evidence.enclosed_space_count),
                    tuple(evidence.enclosed_space_ids),
                )
                for evidence in evidences
            }
            if len(signatures) != 1:
                continue
            bounds_exterior, enclosed_space_count, enclosed_space_ids = next(
                iter(signatures)
            )
            if (bounds_exterior, enclosed_space_count) not in (
                (True, 1),
                (False, 2),
            ):
                continue

            payload = {
                "document_id": viewport_scope.document_id,
                "revision_id": viewport_scope.revision_id,
                "source_sha256": viewport_scope.source_sha256,
                "snapshot_id": viewport_scope.snapshot_id,
                "page_id": viewport_scope.page_id,
                "decision_scope_id": viewport_scope.decision_scope_id,
                "physical_wall_id": viewport_record.wall_candidate_id,
                "source_primitive_ids": tuple(sorted(target_ids)),
                "page_topology_evidence_ids": tuple(
                    sorted(evidence.evidence_id for evidence in evidences)
                ),
                "face_ids": enclosed_space_ids,
            }
            bridged = WallTopologyEvidence(
                evidence_id=stable_contract_id(
                    "source_wall_topology_viewport_bridge",
                    payload,
                    digest_chars=32,
                ),
                document_id=viewport_scope.document_id,
                revision_id=viewport_scope.revision_id,
                source_sha256=viewport_scope.source_sha256,
                snapshot_id=viewport_scope.snapshot_id,
                page_id=viewport_scope.page_id,
                physical_wall_id=viewport_record.wall_candidate_id,
                bounds_exterior=bounds_exterior,
                decision_scope_id=viewport_scope.decision_scope_id,
                enclosed_space_count=enclosed_space_count,
                enclosed_space_ids=enclosed_space_ids,
                is_ambiguous=False,
                ambiguity_reason=None,
            )
            output[
                (
                    viewport_scope.document_id,
                    viewport_scope.revision_id,
                    viewport_scope.source_sha256,
                    viewport_scope.snapshot_id,
                    viewport_scope.page_id,
                    viewport_scope.decision_scope_id,
                    viewport_record.wall_candidate_id,
                )
            ] = bridged
    return output


def build_source_wall_topology_authority(
    physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
    *,
    wall_component_completeness_authority: Optional[
        WallComponentCompletenessAuthority
    ] = None,
) -> WallTopologyAuthority:
    """Derive sealed wall topology evidence from producer-owned wall scopes.

    Complete source scopes retain the original topology path. An incomplete
    authenticated floor-plan viewport can contribute only when an independent
    producer-owned WallComponentCompletenessAuthority has proven one exact
    connected wall component locally complete.
    """

    if type(physical_wall_candidate_authority) is not PhysicalWallCandidateAuthority:
        raise TypeError(
            "physical_wall_candidate_authority must be producer-owned PhysicalWallCandidateAuthority"
        )
    if (
        wall_component_completeness_authority is not None
        and type(wall_component_completeness_authority)
        is not WallComponentCompletenessAuthority
    ):
        raise TypeError(
            "wall_component_completeness_authority must be producer-owned"
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
        if getattr(scope, "scope_complete", False):
            records.update(_derive_scope_records(scope))
        elif wall_component_completeness_authority is not None:
            records.update(
                _component_topology_records(
                    scope,
                    wall_component_completeness_authority,
                )
            )

    for scope in physical_wall_candidate_authority._scopes.values():
        if (
            getattr(scope, "scope_kind", "page") == "page"
            and not getattr(scope, "scope_complete", False)
        ):
            records.update(_page_local_component_topology_records(scope))

    records.update(
        _bridge_page_topology_to_viewports(
            physical_wall_candidate_authority,
            records,
        )
    )

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
