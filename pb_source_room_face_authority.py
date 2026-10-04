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
import math
from types import MappingProxyType
from typing import Iterable, Mapping

from pb_accuracy_v13_engines_v145 import extract_planar_faces
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_wall_candidate_authority import PhysicalWallCandidateAuthority


SOURCE_ROOM_FACE_SCHEMA_VERSION = "1.0.0"
SOURCE_ROOM_FACE_SCOPE_RESOLVED = "source_room_face_scope_resolved"
SOURCE_ROOM_FACE_UNIVERSE_PARTIAL = "source_room_face_universe_partial"
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


def _edge_contains_edge(parent: Edge, child: Edge) -> bool:
    """Return True only when a child edge is a quantized subsegment of parent.

    ``extract_planar_faces`` may split an authenticated wall centerline at an
    intersection. Those split points are rounded through the same six-decimal
    page-space contract as wall edges, so containment is allowed only within
    the maximum error implied by that quantization. No geometric extension,
    nearest-edge selection, or angle-only matching is permitted.
    """
    (ax, ay), (bx, by) = parent
    tolerance = 4.0 * math.sqrt(2.0) * (10.0 ** -_NDIGITS)
    dx, dy = bx - ax, by - ay
    length = math.hypot(dx, dy)
    if length <= tolerance:
        return False

    xmin, xmax = min(ax, bx) - tolerance, max(ax, bx) + tolerance
    ymin, ymax = min(ay, by) - tolerance, max(ay, by) + tolerance

    for px, py in child:
        if not (xmin <= px <= xmax and ymin <= py <= ymax):
            return False
        perpendicular_distance = abs((px - ax) * dy - (py - ay) * dx) / length
        if perpendicular_distance > tolerance:
            return False
    return child[0] != child[1]


def _unique_containing_wall_owner(
    edge: Edge,
    *,
    edge_owner: Mapping[Edge, str],
    wall_edges: Mapping[str, tuple[Edge, ...]],
) -> str | None:
    """Resolve a planarized face edge to exactly one authenticated wall.

    Exact ownership remains authoritative. A fallback is used only when the
    face edge is wholly contained by an original collinear authenticated wall
    edge. Competing physical wall ids fail closed instead of selecting first,
    nearest, shortest, or longest.
    """
    exact = edge_owner.get(edge)
    if exact is not None:
        return exact

    owner: str | None = None
    for wall_id in sorted(wall_edges):
        if not any(
            _edge_contains_edge(parent, edge) for parent in wall_edges[wall_id]
        ):
            continue
        if owner is not None and owner != wall_id:
            return None
        owner = wall_id
    return owner


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
class SourceRoomFaceAbstention:
    """A planar face withheld from publication, with its provenance.

    Abstention is candidate-local: it never publishes the face and never
    deletes it silently, and it does not by itself invalidate unrelated faces.
    """

    face_id: str
    reason: str
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
    abstained_faces: tuple[SourceRoomFaceAbstention, ...] = ()
    @property
    def face_universe_complete(self) -> bool:
        """True only when no discovered face was withheld locally."""
        return (
            self.status is EvidenceResolutionStatus.CORROBORATED
            and bool(self.scope_complete)
            and not self.abstained_faces
        )


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
    face_wall_edges: dict[str, tuple[tuple[str, Edge], ...]] = {}
    face_areas: dict[str, float] = {}

    for raw_face in raw_faces:
        polygon = _canonical_polygon(raw_face)
        if not polygon:
            continue
        owners: list[str] = []
        owned_edges: list[tuple[str, Edge]] = []
        for index, first in enumerate(polygon):
            second = polygon[(index + 1) % len(polygon)]
            face_edge = _edge(first, second)
            owner = _unique_containing_wall_owner(
                face_edge,
                edge_owner=edge_owner,
                wall_edges=wall_edges,
            )
            if owner is None:
                return _blocked(scope, SOURCE_ROOM_FACE_BOUNDARY_UNRESOLVED)
            owners.append(owner)
            owned_edges.append((owner, face_edge))
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
        face_wall_edges[face_id] = tuple(owned_edges)
        face_areas[face_id] = _polygon_area(polygon)

    if not polygons:
        return _blocked(scope, SOURCE_ROOM_FACE_BOUNDARY_UNRESOLVED)

    # A tiny or degenerate face is a candidate-local abstention: it is neither
    # published nor allowed to supply topology evidence (two-sidedness) for any
    # other face, but an ISOLATED one does not by itself make unrelated,
    # independently authenticated faces untrustworthy. Thresholds are unchanged.
    # Failures that genuinely invalidate shared topology (boundary ownership,
    # duplicate edge ownership, ambiguous components, a polluted majority) still
    # fail the whole scope.
    largest_area = max(face_areas.values())
    degenerate_face_ids = {
        face_id
        for face_id, area in face_areas.items()
        if area < _ABSOLUTE_DEGENERATE_AREA_PT2
        or (
            largest_area > 0.0
            and area < _TINY_RELATIVE_THRESHOLD * largest_area
        )
    }
    # Isolation is sound only for an ISOLATED defect. When degenerate faces are
    # not a strict minority of the scope, the wall-candidate pool itself is
    # polluted by non-room linework (tile grids, hatch, fixtures, annotation)
    # and the surviving cells carry no evidence of being rooms. Fail the whole
    # scope exactly as before candidate-local isolation existed.
    if degenerate_face_ids and 2 * len(degenerate_face_ids) >= len(polygons):
        return _blocked(scope, SOURCE_ROOM_FACE_DEGENERATE)
    valid_face_ids = tuple(
        sorted(face_id for face_id in polygons if face_id not in degenerate_face_ids)
    )
    if not valid_face_ids:
        return _blocked(scope, SOURCE_ROOM_FACE_DEGENERATE)

    wall_faces: dict[str, set[str]] = {wall_id: set() for wall_id in wall_ids}
    wall_face_edges: dict[str, dict[Edge, set[str]]] = {
        wall_id: defaultdict(set) for wall_id in wall_ids
    }
    for face_id in valid_face_ids:
        for wall_id in face_walls[face_id]:
            if wall_id in wall_faces:
                wall_faces[wall_id].add(face_id)
        for wall_id, face_edge in face_wall_edges[face_id]:
            if wall_id in wall_face_edges:
                wall_face_edges[wall_id][face_edge].add(face_id)

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
        # A long physical wall may own disjoint subedges of several rooms on
        # the same side. That is not a shared interior boundary. Require the
        # exact same planarized subedge to bound two faces before treating a
        # wall as two-sided for the anti-box/component gate.
        has_two_sided_wall = any(
            len(face_ids) == 2
            for wall_id in component
            for face_ids in wall_face_edges[wall_id].values()
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

    abstained = tuple(
        SourceRoomFaceAbstention(
            face_id=face_id,
            reason=SOURCE_ROOM_FACE_DEGENERATE,
            document_id=scope.document_id,
            revision_id=scope.revision_id,
            source_sha256=scope.source_sha256,
            snapshot_id=scope.snapshot_id,
            page_id=scope.page_id,
            decision_scope_id=scope.decision_scope_id,
            polygon_pdf_pts=polygons[face_id],
            bounding_wall_ids=face_walls[face_id],
            area_page_pts2=face_areas[face_id],
        )
        for face_id in sorted(degenerate_face_ids)
    )
    return SourceRoomFaceScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=True,
        records=tuple(output),
        reason_codes=(
            SOURCE_ROOM_FACE_SCOPE_RESOLVED,
            *((SOURCE_ROOM_FACE_UNIVERSE_PARTIAL,) if abstained else ()),
        ),
        document_id=scope.document_id,
        revision_id=scope.revision_id,
        source_sha256=scope.source_sha256,
        snapshot_id=scope.snapshot_id,
        page_id=scope.page_id,
        decision_scope_id=scope.decision_scope_id,
        abstained_faces=abstained,
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
    "SOURCE_ROOM_FACE_UNIVERSE_PARTIAL",
    "SOURCE_ROOM_FACE_SCOPE_UNAVAILABLE",
    "SourceRoomFaceAuthority",
    "SourceRoomFaceAbstention",
    "SourceRoomFaceRecord",
    "SourceRoomFaceScopeResult",
    "SourceRoomFaceSelector",
    "build_source_room_face_authority",
]
