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
from typing import Iterable

from pb_accuracy_v13_engines_v145 import extract_planar_faces
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_wall_candidate_authority import (
    PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_VIEWPORT_BOUNDARY,
    PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,
    PHYSICAL_WALL_CANDIDATE_SOURCE_PRIMITIVE_OWNERSHIP_AMBIGUOUS,
    PhysicalWallCandidateAuthority,
)
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


def _derive_complete_scope_records(scope) -> dict[tuple[str, str, str, str, str, str, str], WallTopologyEvidence]:
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



def _line_intersects_bbox(
    geometry: tuple[float, float, float, float],
    bbox: tuple[float, float, float, float],
) -> bool:
    x1, y1, x2, y2 = (float(value) for value in geometry)
    xmin, ymin, xmax, ymax = (float(value) for value in bbox)

    def inside(x: float, y: float) -> bool:
        return xmin <= x <= xmax and ymin <= y <= ymax

    if inside(x1, y1) or inside(x2, y2):
        return True
    dx, dy = x2 - x1, y2 - y1
    lower, upper = 0.0, 1.0
    for p, q in (
        (-dx, x1 - xmin),
        (dx, xmax - x1),
        (-dy, y1 - ymin),
        (dy, ymax - y1),
    ):
        if p == 0.0:
            if q < 0.0:
                return False
            continue
        ratio = q / p
        if p < 0.0:
            if ratio > upper:
                return False
            lower = max(lower, ratio)
        else:
            if ratio < lower:
                return False
            upper = min(upper, ratio)
    return lower <= upper


def _record_bbox(record) -> tuple[float, float, float, float] | None:
    points = tuple(getattr(record.wall_candidate, "centerline_pts", ()) or ())
    if len(points) < 2:
        return None
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return (min(xs), min(ys), max(xs), max(ys))


def _bbox_union(records) -> tuple[float, float, float, float] | None:
    boxes = [box for record in records if (box := _record_bbox(record)) is not None]
    if not boxes:
        return None
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _record_touches_viewport_boundary(record, viewport_bbox) -> bool:
    if viewport_bbox is None:
        return True
    xmin, ymin, xmax, ymax = (float(value) for value in viewport_bbox)
    for x, y in tuple(getattr(record.wall_candidate, "centerline_pts", ()) or ()):
        if (
            abs(float(x) - xmin) <= 1e-6
            or abs(float(x) - xmax) <= 1e-6
            or abs(float(y) - ymin) <= 1e-6
            or abs(float(y) - ymax) <= 1e-6
        ):
            return True
    return False


def _topology_representative_records(scope):
    records = tuple(scope.records or ())
    equivalence = getattr(scope, "equivalence", None)
    if equivalence is None:
        return records, ()

    representatives = set(tuple(equivalence.representative_wall_ids or ()))
    if not representatives:
        return (), records

    selected = tuple(
        record for record in records
        if record.wall_candidate_id in representatives
    )
    rejected = tuple(
        record for record in records
        if record.wall_candidate_id not in representatives
    )
    return selected, rejected


def _connected_record_components(records):
    records = tuple(records)
    endpoints = {}
    for record in records:
        points = tuple(getattr(record.wall_candidate, "centerline_pts", ()) or ())
        endpoints[record.wall_candidate_id] = {
            _point(points[0]),
            _point(points[-1]),
        } if len(points) >= 2 else set()

    parent = {record.wall_candidate_id: record.wall_candidate_id for record in records}

    def find(wall_id: str) -> str:
        while parent[wall_id] != wall_id:
            parent[wall_id] = parent[parent[wall_id]]
            wall_id = parent[wall_id]
        return wall_id

    def union(left: str, right: str) -> None:
        a, b = find(left), find(right)
        if a != b:
            parent[max(a, b)] = min(a, b)

    ids = tuple(sorted(parent))
    for index, left in enumerate(ids):
        for right in ids[index + 1:]:
            if endpoints[left] & endpoints[right]:
                union(left, right)

    grouped = defaultdict(list)
    by_id = {record.wall_candidate_id: record for record in records}
    for wall_id in ids:
        grouped[find(wall_id)].append(by_id[wall_id])
    return tuple(
        tuple(sorted(component, key=lambda record: record.wall_candidate_id))
        for _root, component in sorted(grouped.items())
    )


def _derive_incomplete_viewport_component_records(scope):
    if (
        scope.status is not EvidenceResolutionStatus.CORROBORATED
        or scope.scope_complete
        or getattr(scope, "scope_kind", "page") != "viewport"
        or str(getattr(scope, "viewport_view_type", "") or "") != "floor_plan"
        or getattr(scope, "viewport_bbox", None) is None
        or not tuple(getattr(scope, "withheld_structural_segments", ()) or ())
    ):
        return {}

    allowed_reasons = {
        PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,
        PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_VIEWPORT_BOUNDARY,
        PHYSICAL_WALL_CANDIDATE_SOURCE_PRIMITIVE_OWNERSHIP_AMBIGUOUS,
    }
    if set(tuple(scope.reason_codes or ())) - allowed_reasons:
        return {}

    selected, rejected = _topology_representative_records(scope)
    if not selected:
        return {}

    withheld = tuple(scope.withheld_structural_segments or ())
    results = {}
    for component in _connected_record_components(selected):
        component_bbox = _bbox_union(component)
        if component_bbox is None:
            continue
        if any(
            _record_touches_viewport_boundary(record, scope.viewport_bbox)
            for record in component
        ):
            continue
        if any(
            _line_intersects_bbox(evidence.geometry, component_bbox)
            for evidence in withheld
        ):
            continue
        # An equivalence-abstained / non-representative wall remains potential
        # physical geometry. If its own bbox overlaps this component, do not
        # silently discard it from local topology.
        if any(
            (box := _record_bbox(record)) is not None
            and not (
                box[2] < component_bbox[0]
                or box[0] > component_bbox[2]
                or box[3] < component_bbox[1]
                or box[1] > component_bbox[3]
            )
            for record in rejected
            if record.wall_candidate_id
            not in set(tuple(getattr(scope.equivalence, "same_wall_ids", ()) or ()))
        ):
            continue

        local_scope = replace(
            scope,
            scope_complete=True,
            records=component,
            equivalence=None,
            reason_codes=(PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,),
            scope_boundary_observation_ids=(),
            ambiguous_source_observation_ids=(),
            withheld_structural_segments=(),
        )
        results.update(_derive_complete_scope_records(local_scope))
    return results


def _derive_scope_records(scope):
    if getattr(scope, "scope_complete", False):
        return _derive_complete_scope_records(scope)
    return _derive_incomplete_viewport_component_records(scope)


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
