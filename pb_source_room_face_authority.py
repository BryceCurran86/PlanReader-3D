"""Source-authenticated room-face authority derived from physical wall topology.

Consumes only producer-owned PhysicalWallCandidateAuthority scopes. It derives
bounded planar room faces from authenticated physical wall centerlines and
publishes exact page-space polygons only where the enclosing wall component is
topologically resolved.

Positive publication is intentionally narrow:
- the physical-wall scope is CORROBORATED and complete;
- every bounded-face edge belongs to exactly one authenticated physical wall;
- tiny/degenerate faces fail closed;
- a connected component contains at least two bounded faces and at least one
  wall shared by two faces, preventing isolated boxes/title blocks from
  becoming room authority;
- no caller room polygon, label, benchmark value, material, finish, scale or
  expected quantity participates in the proof.

This authority establishes room-face geometry and lineage only. It does not
establish ceiling finish, room use, metric area, wall finish, or commercial
quantity.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Mapping

from pb_accuracy_v13_engines_v145 import extract_planar_faces
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_wall_candidate_authority import PhysicalWallCandidateAuthority


SOURCE_ROOM_FACE_SCHEMA_VERSION = "1.0.0"
SOURCE_ROOM_FACE_SCOPE_RESOLVED = "source_room_face_scope_resolved"
SOURCE_ROOM_FACE_SCOPE_UNAVAILABLE = "source_room_face_scope_unavailable"
SOURCE_ROOM_FACE_BOUNDARY_UNRESOLVED = "source_room_face_boundary_unresolved"
SOURCE_ROOM_FACE_DUPLICATE_EDGE = "source_room_face_duplicate_edge_ownership"
SOURCE_ROOM_FACE_DEGENERATE = "source_room_face_tiny_or_degenerate"
SOURCE_ROOM_FACE_COMPONENT_AMBIGUOUS = "source_room_face_component_ambiguous"

_AUTHORITY_SEAL = object()
_ABSOLUTE_DEGENERATE_AREA_PT2 = 1.0
_TINY_RELATIVE_THRESHOLD = 0.01
_NDIGITS = 6

Point = tuple[float, float]
Edge = tuple[Point, Point]
_ScopeKey = tuple[str, str, str, str, str, str]


def _clean(value: object) -> str:
    return str(value or "").strip()


def _point(value: Iterable[float]) -> Point:
    x, y = value
    return (round(float(x), _NDIGITS), round(float(y), _NDIGITS))


def _edge(first: Iterable[float], second: Iterable[float]) -> Edge:
    a, b = _point(first), _point(second)
    return (a, b) if a <= b else (b, a)


def _canonical_polygon(points: Iterable[Iterable[float]]) -> tuple[Point, ...]:
    cleaned = tuple(_point(point) for point in points)
    if len(cleaned) < 3:
        return ()
    variants: list[tuple[Point, ...]] = []
    for start in range(len(cleaned)):
        variants.append(
            tuple(cleaned[(start + i) % len(cleaned)] for i in range(len(cleaned)))
        )
        variants.append(
            tuple(cleaned[(start - i) % len(cleaned)] for i in range(len(cleaned)))
        )
    return min(variants)


def _polygon_area(points: tuple[Point, ...]) -> float:
    total = 0.0
    for index, (x1, y1) in enumerate(points):
        x2, y2 = points[(index + 1) % len(points)]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def _wall_edges(record: object) -> tuple[Edge, ...]:
    wall_candidate = getattr(record, "wall_candidate", None)
    points = tuple(getattr(wall_candidate, "centerline_pts", ()) or ())
    if len(points) < 2:
        return ()
    result: list[Edge] = []
    for first, second in zip(points, points[1:]):
        edge = _edge(first, second)
        if edge[0] != edge[1]:
            result.append(edge)
    return tuple(result)


@dataclass(frozen=True)
class SourceRoomFaceSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str

    @property
    def key(self) -> _ScopeKey:
        return (
            _clean(self.document_id),
            _clean(self.revision_id),
            _clean(self.source_sha256),
            _clean(self.snapshot_id),
            _clean(self.page_id),
            _clean(self.decision_scope_id),
        )


@dataclass(frozen=True)
class SourceRoomFaceRecord:
    record_id: str
    face_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    polygon_pdf_pts: tuple[Point, ...]
    bounding_wall_ids: tuple[str, ...]
    area_page_pts2: float
    schema_version: str = SOURCE_ROOM_FACE_SCHEMA_VERSION


@dataclass(frozen=True)
class SourceRoomFaceScopeResult:
    status: EvidenceResolutionStatus
    scope_complete: bool
    records: tuple[SourceRoomFaceRecord, ...]
    reason_codes: tuple[str, ...]
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    schema_version: str = SOURCE_ROOM_FACE_SCHEMA_VERSION


class SourceRoomFaceAuthority:
    def __init__(
        self,
        results: Mapping[_ScopeKey, SourceRoomFaceScopeResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("SourceRoomFaceAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve_scope(
        self, selector: SourceRoomFaceSelector
    ) -> SourceRoomFaceScopeResult:
        if type(selector) is not SourceRoomFaceSelector:
            raise TypeError("selector must be SourceRoomFaceSelector")
        result = self._results.get(selector.key)
        if result is not None:
            return result
        return SourceRoomFaceScopeResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            scope_complete=False,
            records=(),
            reason_codes=(SOURCE_ROOM_FACE_SCOPE_UNAVAILABLE,),
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
        )


def _blocked(scope: object, reason: str) -> SourceRoomFaceScopeResult:
    return SourceRoomFaceScopeResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        scope_complete=False,
        records=(),
        reason_codes=(reason,),
        document_id=_clean(getattr(scope, "document_id", "")),
        revision_id=_clean(getattr(scope, "revision_id", "")),
        source_sha256=_clean(getattr(scope, "source_sha256", "")),
        snapshot_id=_clean(getattr(scope, "snapshot_id", "")),
        page_id=_clean(getattr(scope, "page_id", "")),
        decision_scope_id=_clean(getattr(scope, "decision_scope_id", "")),
    )


def _derive_scope(scope: object) -> SourceRoomFaceScopeResult:
    if (
        getattr(scope, "status", None) is not EvidenceResolutionStatus.CORROBORATED
        or not bool(getattr(scope, "scope_complete", False))
        or not tuple(getattr(scope, "records", ()) or ())
    ):
        return _blocked(scope, SOURCE_ROOM_FACE_SCOPE_UNAVAILABLE)

    records = tuple(getattr(scope, "records", ()) or ())
    wall_edges: dict[str, tuple[Edge, ...]] = {}
    edge_owner: dict[Edge, str] = {}
    duplicate_edges: set[Edge] = set()
    endpoints_by_wall: dict[str, set[Point]] = {}

    for record in records:
        wall_id = _clean(getattr(record, "wall_candidate_id", ""))
        edges = _wall_edges(record)
        if not wall_id or not edges:
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
        return _blocked(scope, SOURCE_ROOM_FACE_SCOPE_UNAVAILABLE)
    if duplicate_edges:
        return _blocked(scope, SOURCE_ROOM_FACE_DUPLICATE_EDGE)

    raw_segments = [
        (edge[0], edge[1]) for wall_id in wall_ids for edge in wall_edges[wall_id]
    ]
    raw_faces = extract_planar_faces(raw_segments, min_area=1e-6)

    polygons: dict[str, tuple[Point, ...]] = {}
    face_walls: dict[str, tuple[str, ...]] = {}
    face_areas: dict[str, float] = {}

    for raw_face in raw_faces:
        polygon = _canonical_polygon(raw_face)
        if not polygon:
            continue
        owners: list[str] = []
        for index, first in enumerate(polygon):
            second = polygon[(index + 1) % len(polygon)]
            owner = edge_owner.get(_edge(first, second))
            if owner is None:
                return _blocked(scope, SOURCE_ROOM_FACE_BOUNDARY_UNRESOLVED)
            owners.append(owner)
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
        polygons[face_id] = polygon
        face_walls[face_id] = tuple(sorted(set(owners)))
        face_areas[face_id] = _polygon_area(polygon)

    if not polygons:
        return _blocked(scope, SOURCE_ROOM_FACE_BOUNDARY_UNRESOLVED)

    largest_area = max(face_areas.values())
    if any(
        area < _ABSOLUTE_DEGENERATE_AREA_PT2
        or (
            largest_area > 0.0
            and area < _TINY_RELATIVE_THRESHOLD * largest_area
        )
        for area in face_areas.values()
    ):
        return _blocked(scope, SOURCE_ROOM_FACE_DEGENERATE)

    wall_faces: dict[str, set[str]] = {wall_id: set() for wall_id in wall_ids}
    for face_id, owners in face_walls.items():
        for wall_id in owners:
            if wall_id in wall_faces:
                wall_faces[wall_id].add(face_id)

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

    resolved_faces: set[str] = set()
    for component in component_walls.values():
        component_faces = set().union(
            *(wall_faces[wall_id] for wall_id in component)
        )
        has_two_sided_wall = any(
            len(wall_faces[wall_id]) == 2 for wall_id in component
        )
        if len(component_faces) >= 2 and has_two_sided_wall:
            resolved_faces.update(component_faces)

    if not resolved_faces:
        return _blocked(scope, SOURCE_ROOM_FACE_COMPONENT_AMBIGUOUS)

    output: list[SourceRoomFaceRecord] = []
    for face_id in sorted(resolved_faces):
        polygon = polygons.get(face_id)
        if polygon is None:
            return _blocked(scope, SOURCE_ROOM_FACE_BOUNDARY_UNRESOLVED)
        payload = {
            "face_id": face_id,
            "document_id": scope.document_id,
            "revision_id": scope.revision_id,
            "source_sha256": scope.source_sha256,
            "snapshot_id": scope.snapshot_id,
            "page_id": scope.page_id,
            "decision_scope_id": scope.decision_scope_id,
            "polygon": polygon,
            "bounding_wall_ids": face_walls[face_id],
            "area_page_pts2": face_areas[face_id],
        }
        output.append(
            SourceRoomFaceRecord(
                record_id=stable_contract_id(
                    "source_room_face_record", payload, digest_chars=32
                ),
                face_id=face_id,
                document_id=scope.document_id,
                revision_id=scope.revision_id,
                source_sha256=scope.source_sha256,
                snapshot_id=scope.snapshot_id,
                page_id=scope.page_id,
                decision_scope_id=scope.decision_scope_id,
                polygon_pdf_pts=polygon,
                bounding_wall_ids=face_walls[face_id],
                area_page_pts2=face_areas[face_id],
            )
        )

    return SourceRoomFaceScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=True,
        records=tuple(output),
        reason_codes=(SOURCE_ROOM_FACE_SCOPE_RESOLVED,),
        document_id=scope.document_id,
        revision_id=scope.revision_id,
        source_sha256=scope.source_sha256,
        snapshot_id=scope.snapshot_id,
        page_id=scope.page_id,
        decision_scope_id=scope.decision_scope_id,
    )


def build_source_room_face_authority(
    physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
) -> SourceRoomFaceAuthority:
    """Build sealed room-face results from all producer-owned wall scopes."""

    if type(physical_wall_candidate_authority) is not PhysicalWallCandidateAuthority:
        raise TypeError(
            "physical_wall_candidate_authority must be producer-owned "
            "PhysicalWallCandidateAuthority"
        )

    results: dict[_ScopeKey, SourceRoomFaceScopeResult] = {}
    for scope in physical_wall_candidate_authority._scopes.values():
        result = _derive_scope(scope)
        key: _ScopeKey = (
            _clean(scope.document_id),
            _clean(scope.revision_id),
            _clean(scope.source_sha256),
            _clean(scope.snapshot_id),
            _clean(scope.page_id),
            _clean(scope.decision_scope_id),
        )
        results[key] = result
    return SourceRoomFaceAuthority(results, _seal=_AUTHORITY_SEAL)


__all__ = [
    "SOURCE_ROOM_FACE_BOUNDARY_UNRESOLVED",
    "SOURCE_ROOM_FACE_COMPONENT_AMBIGUOUS",
    "SOURCE_ROOM_FACE_DEGENERATE",
    "SOURCE_ROOM_FACE_DUPLICATE_EDGE",
    "SOURCE_ROOM_FACE_SCHEMA_VERSION",
    "SOURCE_ROOM_FACE_SCOPE_RESOLVED",
    "SOURCE_ROOM_FACE_SCOPE_UNAVAILABLE",
    "SourceRoomFaceAuthority",
    "SourceRoomFaceRecord",
    "SourceRoomFaceScopeResult",
    "SourceRoomFaceSelector",
    "build_source_room_face_authority",
]
