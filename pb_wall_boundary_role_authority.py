"""Shadow wall-boundary role authority from planar half-edges and space role.

This does not publish quantities, mutate W1-W10 contracts, or treat
``WallCandidate.interior_exterior`` / room-count as authority.

Observed W5 already walks directed half-edges inside ``extract_planar_faces``
and drops the unbounded face. This module reuses that same rotation system
and **keeps** the unbounded face as a topological concept.

TOPOLOGICALLY_UNBOUNDED is not ARCHITECTURAL_EXTERIOR_OPEN_SPACE unless
independent viewport-coverage authority (or an explicit exterior space label)
proves the drawing coverage is complete. Crop contact alone never proves
EXTERNAL.

A corroborated physical wall may still have UNKNOWN role.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import atan2
from typing import Any, Mapping, Optional, Sequence, Union

from pb_migration_contracts import (
    DocumentEvidence,
    EvidenceAtom,
    EvidenceResolutionStatus,
    ViewportEvidence,
    stable_contract_id,
)
from pb_physical_wall_existence_authority import wall_physical_existence_status
from pb_wall_room_topology_contracts import WallCandidate
from pb_wall_room_topology_room_faces import _canonicalize_polygon, _point_in_polygon

WALL_BOUNDARY_ROLE_KIND = "wall_boundary_role"
WALL_BOUNDARY_ROLE_METHOD = "wall_boundary_role_authority"
WALL_BOUNDARY_ROLE_SCHEMA_VERSION = "1.1.0"
UNBOUNDED_FACE_KIND = "unbounded"
BOUNDED_FACE_KIND = "bounded"
SPACE_ROLE_LABEL_KIND = "space_role_label"
EXPLICIT_WALL_ROLE_KIND = "explicit_wall_role"
VIEWPORT_COVERAGE_KIND = "viewport_coverage"

_AtomLike = Union[EvidenceAtom, Mapping[str, Any]]


class WallBoundaryRole(str, Enum):
    EXTERNAL = "external"
    INTERNAL_PARTITION = "internal_partition"
    UNKNOWN = "unknown"
    CONFLICT = "conflict"


class SpaceRole(str, Enum):
    BUILDING_INTERIOR = "building_interior"
    EXTERIOR_OPEN_SPACE = "exterior_open_space"
    EXTERIOR_ENCLOSED_VOID = "exterior_enclosed_void"
    COVERED_OPEN_SPACE = "covered_open_space"
    UNKNOWN = "unknown"


_EXTERIOR_SPACE = frozenset(
    {
        SpaceRole.EXTERIOR_OPEN_SPACE,
        SpaceRole.EXTERIOR_ENCLOSED_VOID,
        SpaceRole.COVERED_OPEN_SPACE,
    }
)

_COURTYARD_LABELS = frozenset(
    {
        "courtyard",
        "light well",
        "lightwell",
        "light-well",
        "open to sky",
        "open courtyard",
        "yard",
        "court",
    }
)

_COVERED_LABELS = frozenset(
    {
        "verandah",
        "veranda",
        "porch",
        "covered way",
        "covered open space",
        "carport",
        "loggia",
    }
)

_NON_COURTYARD_VOID_LABELS = frozenset(
    {
        "lift shaft",
        "elevator shaft",
        "stair void",
        "stairwell void",
        "riser",
        "service shaft",
        "shaft",
    }
)


def _round8(point: tuple[float, float]) -> tuple[float, float]:
    return (round(float(point[0]), 8), round(float(point[1]), 8))


def _same(a: tuple[float, float], b: tuple[float, float], tol: float = 1e-6) -> bool:
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


def _atom_field(atom: _AtomLike, key: str, default: Any = None) -> Any:
    if isinstance(atom, EvidenceAtom):
        if key == "evidence_id":
            return atom.evidence_id
        if key == "kind":
            return atom.kind
        if key == "metadata":
            return atom.metadata
        if key == "raw_text":
            return atom.raw_text
        if key == "bbox":
            return atom.bbox
        return getattr(atom, key, default)
    return atom.get(key, default)


@dataclass(frozen=True)
class PlanarFaceRecord:
    face_id: str
    kind: str
    polygon: tuple[tuple[float, float], ...]
    adjacent_to_unbounded: bool


@dataclass(frozen=True)
class WallSideAssignment:
    wall_candidate_id: str
    left_face_ids: tuple[str, ...]
    right_face_ids: tuple[str, ...]
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class WallSideEmbedding:
    faces: Mapping[str, PlanarFaceRecord]
    assignments: Mapping[str, WallSideAssignment]
    unbounded_face_id: str


@dataclass(frozen=True)
class WallBoundaryRoleEvidence:
    wall_candidate_id: str
    viewport_id: str
    left_face_id: Optional[str]
    right_face_id: Optional[str]
    role: WallBoundaryRole
    status: EvidenceResolutionStatus
    supporting_evidence_ids: tuple[str, ...]
    conflicting_evidence_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    evidence_id: str
    left_space_role: Optional[str] = None
    right_space_role: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = WALL_BOUNDARY_ROLE_SCHEMA_VERSION


def _unbounded_face_id(viewport_id: str) -> str:
    return f"face:unbounded:{viewport_id}"


def _bounded_face_id(viewport_id: str, polygon: Sequence[tuple[float, float]]) -> str:
    return stable_contract_id(
        "face",
        {"viewport_id": viewport_id, "canonical_polygon": list(_canonicalize_polygon(polygon))},
    )


def _point_on_axis_aligned_bbox_boundary(
    point: tuple[float, float], bbox: tuple[float, float, float, float]
) -> bool:
    x, y = _round8(point)
    x0, y0, x1, y1 = (_round8((bbox[0], bbox[1]))[0], _round8((bbox[0], bbox[1]))[1], _round8((bbox[2], bbox[3]))[0], _round8((bbox[2], bbox[3]))[1])
    on_vertical = (x == x0 or x == x1) and min(y0, y1) <= y <= max(y0, y1)
    on_horizontal = (y == y0 or y == y1) and min(x0, x1) <= x <= max(x0, x1)
    return on_vertical or on_horizontal


def wall_lies_on_viewport_boundary(wall: WallCandidate, viewport: ViewportEvidence) -> bool:
    """True only when every centerline vertex lies on the viewport rectangle.

    Used as a coverage *blocker*, never as proof of EXTERNAL. This is not a
    distance-to-boundary heuristic.
    """
    bbox = viewport.bbox
    if bbox is None:
        return False
    pts = wall.centerline_pts
    if len(pts) < 2:
        return False
    return all(_point_on_axis_aligned_bbox_boundary(p, bbox) for p in pts)


def _build_rotation_system(
    segments: Sequence[tuple[tuple[float, float], tuple[float, float]]],
) -> dict[tuple[float, float], list[tuple[float, float]]]:
    adj: dict[tuple[float, float], list[tuple[float, float]]] = {}
    for raw_a, raw_b in segments:
        a, b = _round8(raw_a), _round8(raw_b)
        if _same(a, b):
            continue
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    for node, nbrs in adj.items():
        unique = []
        for nbr in nbrs:
            if not any(_same(nbr, existing) for existing in unique):
                unique.append(nbr)
        adj[node] = sorted(unique, key=lambda q: atan2(q[1] - node[1], q[0] - node[0]))
    return adj


def _signed_area(points: Sequence[tuple[float, float]]) -> float:
    n = len(points)
    total = 0.0
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return total / 2.0


def _centroid(points: Sequence[tuple[float, float]]) -> tuple[float, float]:
    return (
        sum(p[0] for p in points) / len(points),
        sum(p[1] for p in points) / len(points),
    )


def _vertex_key(points: Sequence[tuple[float, float]]) -> frozenset[tuple[float, float]]:
    return frozenset(_round8(p) for p in points)


def _walk_faces(
    adj: Mapping[tuple[float, float], Sequence[tuple[float, float]]],
    *,
    viewport_id: str,
    min_area: float = 1e-6,
) -> tuple[dict[tuple[tuple[float, float], tuple[float, float]], str], dict[str, PlanarFaceRecord]]:
    """Clockwise-predecessor walk matching extract_planar_faces, keeping holes.

    Reverse walks of an *outer* interior face are the unbounded face.
    Reverse walks of a hole contained in a larger interior face are assigned
    to that parent face (the building ring), not to unbounded.
    """
    used: set[tuple[tuple[float, float], tuple[float, float]]] = set()
    directed_to_face: dict[tuple[tuple[float, float], tuple[float, float]], str] = {}
    unbounded_id = _unbounded_face_id(viewport_id)
    edge_count = sum(len(v) for v in adj.values()) // 2
    cycles: list[tuple[str, tuple[tuple[float, float], ...], list[tuple[tuple[float, float], tuple[float, float]]]]] = []
    for u in list(adj):
        for v in adj[u]:
            if (u, v) in used:
                continue
            face_pts: list[tuple[float, float]] = []
            a, b = u, v
            closed = False
            for _ in range(max(8, edge_count * 4, 8)):
                if (a, b) in used:
                    break
                used.add((a, b))
                face_pts.append(a)
                nbrs = list(adj[b])
                try:
                    idx = nbrs.index(a)
                except ValueError:
                    break
                c = nbrs[(idx - 1) % len(nbrs)]
                a, b = b, c
                if _same(a, u) and _same(b, v):
                    closed = True
                    break
            if not closed or len(face_pts) < 3:
                continue
            signed = _signed_area(face_pts)
            walk = list(zip(face_pts, face_pts[1:] + face_pts[:1]))
            kind = "positive" if signed > 0 and abs(signed) >= min_area else "negative"
            cycles.append((kind, tuple(face_pts), walk))

    positives = [(pts, walk, abs(_signed_area(pts))) for kind, pts, walk in cycles if kind == "positive"]
    negatives = [(pts, walk) for kind, pts, walk in cycles if kind == "negative"]
    faces: dict[str, PlanarFaceRecord] = {}
    positive_ids: list[tuple[str, tuple[tuple[float, float], ...], float]] = []
    for pts, walk, area in positives:
        face_id = _bounded_face_id(viewport_id, pts)
        faces[face_id] = PlanarFaceRecord(
            face_id=face_id,
            kind=BOUNDED_FACE_KIND,
            polygon=pts,
            adjacent_to_unbounded=False,
        )
        positive_ids.append((face_id, pts, area))
        for p, q in walk:
            directed_to_face[(p, q)] = face_id

    def _smallest_container(pts: Sequence[tuple[float, float]]) -> Optional[str]:
        c = _centroid(pts)
        containers = [
            (area, face_id)
            for face_id, poly, area in positive_ids
            if _vertex_key(poly) != _vertex_key(pts)
            and area > abs(_signed_area(pts))
            and poly
            and _point_in_polygon(c, poly)
        ]
        if not containers:
            return None
        containers.sort()
        return containers[0][1]

    for pts, walk in negatives:
        matching_positive = next(
            (face_id for face_id, poly, _area in positive_ids if _vertex_key(poly) == _vertex_key(pts)),
            None,
        )
        if matching_positive is not None:
            parent = _smallest_container(pts)
            target = parent if parent is not None else unbounded_id
        else:
            parent = _smallest_container(pts)
            target = parent if parent is not None else unbounded_id
        for p, q in walk:
            directed_to_face[(p, q)] = target

    faces[unbounded_id] = PlanarFaceRecord(
        face_id=unbounded_id,
        kind=UNBOUNDED_FACE_KIND,
        polygon=(),
        adjacent_to_unbounded=True,
    )
    adjacency = {fid: rec.kind == UNBOUNDED_FACE_KIND for fid, rec in faces.items()}
    for (p, q), face_id in directed_to_face.items():
        twin = directed_to_face.get((q, p))
        rec = faces.get(face_id)
        if rec is None or rec.kind != BOUNDED_FACE_KIND:
            continue
        if twin == unbounded_id:
            adjacency[face_id] = True
    faces = {
        fid: PlanarFaceRecord(
            face_id=rec.face_id,
            kind=rec.kind,
            polygon=rec.polygon,
            adjacent_to_unbounded=adjacency.get(fid, rec.adjacent_to_unbounded),
        )
        for fid, rec in faces.items()
    }
    return directed_to_face, faces


def _wall_forward(wall: WallCandidate) -> tuple[float, float]:
    start, end = wall.centerline_pts[0], wall.centerline_pts[-1]
    return (float(end[0]) - float(start[0]), float(end[1]) - float(start[1]))


def build_wall_side_embedding(
    *,
    graph: Mapping[str, Any],
    edge_id_to_wall_id: Mapping[str, str],
    walls: Sequence[WallCandidate],
    viewport_id: str,
) -> WallSideEmbedding:
    """Directed left/right faces for each canonical wall from W2 edges."""
    walls_by_id = {wall.candidate_id: wall for wall in walls}
    live_edges = [e for e in graph.get("edges", []) if not e.get("_removed")]
    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    undirected_to_wall: dict[frozenset[tuple[float, float]], str] = {}
    undirected_conflict: set[frozenset[tuple[float, float]]] = set()
    for edge in live_edges:
        a = _round8((float(edge["x1"]), float(edge["y1"])))
        b = _round8((float(edge["x2"]), float(edge["y2"])))
        if _same(a, b):
            continue
        segments.append((a, b))
        wall_id = str(edge_id_to_wall_id.get(str(edge.get("id") or ""), "") or "")
        key = frozenset((a, b))
        existing = undirected_to_wall.get(key)
        if wall_id and existing and existing != wall_id:
            undirected_conflict.add(key)
        elif wall_id:
            undirected_to_wall[key] = wall_id

    adj = _build_rotation_system(segments)
    directed_to_face, faces = _walk_faces(adj, viewport_id=viewport_id)
    unbounded_id = _unbounded_face_id(viewport_id)

    per_wall_left: dict[str, list[str]] = {}
    per_wall_right: dict[str, list[str]] = {}
    per_wall_blockers: dict[str, list[str]] = {}

    seen_undirected: set[frozenset[tuple[float, float]]] = set()
    for (p, q), face_id in directed_to_face.items():
        key = frozenset((p, q))
        if key in seen_undirected:
            continue
        seen_undirected.add(key)
        if key in undirected_conflict:
            wall_id = undirected_to_wall.get(key)
            if wall_id:
                per_wall_blockers.setdefault(wall_id, []).append("overlapping_wall_half_edge")
            continue
        wall_id = undirected_to_wall.get(key)
        if not wall_id:
            continue
        twin_face = directed_to_face.get((q, p))
        if twin_face is None:
            per_wall_blockers.setdefault(wall_id, []).append("missing_twin_half_edge")
            continue
        wall = walls_by_id.get(wall_id)
        if wall is None or len(wall.centerline_pts) < 2:
            per_wall_blockers.setdefault(wall_id, []).append("wall_centerline_unresolved")
            continue
        fx, fy = _wall_forward(wall)
        along = (q[0] - p[0]) * fx + (q[1] - p[1]) * fy
        if along >= 0:
            left_face, right_face = face_id, twin_face
        else:
            left_face, right_face = twin_face, face_id
        per_wall_left.setdefault(wall_id, []).append(left_face)
        per_wall_right.setdefault(wall_id, []).append(right_face)

    assignments: dict[str, WallSideAssignment] = {}
    wall_ids = set(undirected_to_wall.values()) | set(per_wall_left) | set(per_wall_right)
    for wall_id in wall_ids:
        left_ids = tuple(dict.fromkeys(per_wall_left.get(wall_id, ())))
        right_ids = tuple(dict.fromkeys(per_wall_right.get(wall_id, ())))
        blockers = tuple(dict.fromkeys(per_wall_blockers.get(wall_id, ())))
        assignments[wall_id] = WallSideAssignment(
            wall_candidate_id=wall_id,
            left_face_ids=left_ids,
            right_face_ids=right_ids,
            blockers=blockers,
        )
    return WallSideEmbedding(
        faces=faces,
        assignments=assignments,
        unbounded_face_id=unbounded_id,
    )


def _label_space_role(text: str) -> Optional[SpaceRole]:
    normalized = " ".join(str(text or "").lower().split())
    if not normalized:
        return None
    if any(token in normalized for token in _NON_COURTYARD_VOID_LABELS):
        # Shaft/stair voids are not courtyard and not building interior.
        return None
    if any(token in normalized for token in _COVERED_LABELS):
        return SpaceRole.COVERED_OPEN_SPACE
    if any(token in normalized for token in _COURTYARD_LABELS):
        return SpaceRole.EXTERIOR_ENCLOSED_VOID
    return None


def _explicit_space_role_from_atom(atom: _AtomLike) -> Optional[SpaceRole]:
    if str(_atom_field(atom, "kind") or "") != SPACE_ROLE_LABEL_KIND:
        return None
    metadata = _atom_field(atom, "metadata") or {}
    raw = str(metadata.get("space_role") or "")
    if raw:
        try:
            return SpaceRole(raw)
        except ValueError:
            return None
    return _label_space_role(str(_atom_field(atom, "raw_text") or ""))


def _label_point(atom: _AtomLike) -> Optional[tuple[float, float]]:
    bbox = _atom_field(atom, "bbox")
    if bbox and len(bbox) == 4:
        return ((float(bbox[0]) + float(bbox[2])) / 2.0, (float(bbox[1]) + float(bbox[3])) / 2.0)
    metadata = _atom_field(atom, "metadata") or {}
    if "x" in metadata and "y" in metadata:
        return (float(metadata["x"]), float(metadata["y"]))
    return None


def resolve_viewport_coverage_authority(
    *,
    viewport: ViewportEvidence,
    coverage_atoms: Sequence[_AtomLike] = (),
) -> tuple[bool, tuple[str, ...]]:
    """Independent coverage proof. Crop/topology alone never establishes this.

    Returns ``(coverage_complete, reason_codes)``. Conflicting coverage atoms
    fail closed (incomplete). Missing atoms are incomplete.
    """
    statuses: list[str] = []
    reasons: list[str] = []
    for atom in coverage_atoms:
        if str(_atom_field(atom, "kind") or "") != VIEWPORT_COVERAGE_KIND:
            continue
        metadata = _atom_field(atom, "metadata") or {}
        atom_vp = str(metadata.get("viewport_id") or _atom_field(atom, "viewport_id") or "")
        if atom_vp and atom_vp != viewport.viewport_id:
            reasons.append("viewport_coverage_viewport_mismatch")
            continue
        status = str(metadata.get("coverage_status") or "").strip().lower()
        if status:
            statuses.append(status)
    distinct = tuple(dict.fromkeys(statuses))
    if not distinct:
        return False, tuple(dict.fromkeys(("viewport_coverage_unproven", *reasons)))
    if len(distinct) > 1:
        return False, tuple(dict.fromkeys(("conflicting_viewport_coverage_evidence", *reasons)))
    if distinct[0] == "complete":
        return True, ("viewport_coverage_complete",)
    if distinct[0] in {"incomplete", "partial", "cropped", "unknown"}:
        return False, tuple(dict.fromkeys(("viewport_coverage_incomplete", *reasons)))
    return False, tuple(dict.fromkeys(("viewport_coverage_unproven", *reasons)))


def resolve_space_roles(
    embedding: WallSideEmbedding,
    *,
    space_label_atoms: Sequence[_AtomLike] = (),
    coverage_complete: bool = False,
) -> dict[str, tuple[SpaceRole, tuple[str, ...]]]:
    """Space role per face.

    Unbounded is TOPOLOGICALLY_UNBOUNDED. It becomes ARCHITECTURAL
    ``EXTERIOR_OPEN_SPACE`` only when ``coverage_complete`` is proven.
    No flood-fill. No bbox-as-building-face.
    """
    out: dict[str, tuple[SpaceRole, tuple[str, ...]]] = {}
    labels = []
    for atom in space_label_atoms:
        role = _explicit_space_role_from_atom(atom)
        point = _label_point(atom)
        if role is None or point is None:
            continue
        labels.append((point, role, str(_atom_field(atom, "evidence_id") or "")))

    labeled_faces: dict[str, list[tuple[SpaceRole, str]]] = {
        face_id: [] for face_id, rec in embedding.faces.items() if rec.kind == BOUNDED_FACE_KIND
    }
    for point, role, evidence_id in labels:
        containers = []
        for face_id, rec in embedding.faces.items():
            if rec.kind != BOUNDED_FACE_KIND or not rec.polygon:
                continue
            if _point_in_polygon(point, rec.polygon):
                containers.append((abs(_signed_area(rec.polygon)), face_id))
        if not containers:
            continue
        containers.sort()
        labeled_faces.setdefault(containers[0][1], []).append((role, evidence_id))

    for face_id, rec in embedding.faces.items():
        if rec.kind == UNBOUNDED_FACE_KIND:
            if coverage_complete:
                out[face_id] = (
                    SpaceRole.EXTERIOR_OPEN_SPACE,
                    ("unbounded_face_with_complete_coverage",),
                )
            else:
                out[face_id] = (
                    SpaceRole.UNKNOWN,
                    ("topologically_unbounded_without_architectural_exterior",),
                )
            continue
        hits = labeled_faces.get(face_id, [])
        distinct = tuple(dict.fromkeys(role for role, _ in hits))
        if len(distinct) > 1:
            out[face_id] = (SpaceRole.UNKNOWN, ("conflicting_space_role_labels",))
            continue
        if len(distinct) == 1:
            out[face_id] = (distinct[0], ("explicit_space_role_label",))
            continue
        if rec.adjacent_to_unbounded:
            if coverage_complete:
                out[face_id] = (
                    SpaceRole.BUILDING_INTERIOR,
                    ("unlabeled_bounded_face_adjacent_to_unbounded",),
                )
            else:
                out[face_id] = (
                    SpaceRole.UNKNOWN,
                    ("bounded_face_adjacent_to_unbounded_without_coverage_authority",),
                )
            continue
        out[face_id] = (
            SpaceRole.UNKNOWN,
            ("unlabeled_bounded_face_not_adjacent_to_unbounded",),
        )
    return out


def _combine_side_roles(
    face_ids: Sequence[str],
    space_roles: Mapping[str, tuple[SpaceRole, tuple[str, ...]]],
) -> tuple[Optional[SpaceRole], tuple[str, ...]]:
    if not face_ids:
        return None, ("missing_incident_face",)
    roles = []
    reasons: list[str] = []
    for face_id in face_ids:
        if face_id not in space_roles:
            return None, ("incident_face_space_role_missing",)
        role, face_reasons = space_roles[face_id]
        roles.append(role)
        reasons.extend(face_reasons)
    distinct = tuple(dict.fromkeys(roles))
    if SpaceRole.UNKNOWN in distinct and len(distinct) > 1:
        return None, tuple(dict.fromkeys(("mixed_unknown_space_role_on_side", *reasons)))
    if len(distinct) > 1:
        return None, tuple(dict.fromkeys(("conflicting_space_roles_on_same_side", *reasons)))
    if distinct[0] == SpaceRole.UNKNOWN:
        return SpaceRole.UNKNOWN, tuple(dict.fromkeys(reasons))
    return distinct[0], tuple(dict.fromkeys(reasons))


def _role_from_sides(
    left: Optional[SpaceRole], right: Optional[SpaceRole]
) -> tuple[WallBoundaryRole, tuple[str, ...]]:
    if left is None or right is None:
        return WallBoundaryRole.UNKNOWN, ("incomplete_wall_side_relation",)
    if left == SpaceRole.UNKNOWN or right == SpaceRole.UNKNOWN:
        return WallBoundaryRole.UNKNOWN, ("ambiguous_space_role",)
    if left == right:
        if left == SpaceRole.BUILDING_INTERIOR:
            return WallBoundaryRole.INTERNAL_PARTITION, ("both_sides_building_interior",)
        return WallBoundaryRole.UNKNOWN, ("both_sides_non_building",)
    left_ext = left in _EXTERIOR_SPACE
    right_ext = right in _EXTERIOR_SPACE
    left_int = left == SpaceRole.BUILDING_INTERIOR
    right_int = right == SpaceRole.BUILDING_INTERIOR
    if (left_int and right_ext) or (right_int and left_ext):
        return WallBoundaryRole.EXTERNAL, ("building_interior_opposite_exterior_space",)
    return WallBoundaryRole.UNKNOWN, ("unhandled_space_role_pair",)


def _wall_source_ids(wall: WallCandidate) -> frozenset[str]:
    ids = set(wall.face_a_segment_ids)
    if wall.face_b_segment_ids:
        ids.update(wall.face_b_segment_ids)
    return frozenset(ids)


def _explicit_roles_for_wall(
    wall: WallCandidate, atoms: Sequence[_AtomLike]
) -> tuple[tuple[WallBoundaryRole, ...], tuple[str, ...]]:
    roles: list[WallBoundaryRole] = []
    ids: list[str] = []
    for atom in atoms:
        if str(_atom_field(atom, "kind") or "") != EXPLICIT_WALL_ROLE_KIND:
            continue
        metadata = _atom_field(atom, "metadata") or {}
        if str(metadata.get("wall_candidate_id") or "") not in ("", wall.candidate_id):
            if str(metadata.get("wall_candidate_id") or "") != wall.candidate_id:
                continue
        raw = str(metadata.get("role") or "")
        try:
            roles.append(WallBoundaryRole(raw))
        except ValueError:
            continue
        ids.append(str(_atom_field(atom, "evidence_id") or ""))
    return tuple(roles), tuple(i for i in ids if i)


def resolve_wall_boundary_roles(
    *,
    walls: Sequence[WallCandidate],
    graph: Mapping[str, Any],
    edge_id_to_wall_id: Mapping[str, str],
    evidence_atoms: Sequence[_AtomLike],
    document: DocumentEvidence,
    viewport: ViewportEvidence,
    space_label_atoms: Sequence[_AtomLike] = (),
    explicit_role_atoms: Sequence[_AtomLike] = (),
    coverage_atoms: Sequence[_AtomLike] = (),
) -> tuple[WallBoundaryRoleEvidence, ...]:
    """Typed wall-role evidence. Shadow only. Existence stays independent."""
    embedding = build_wall_side_embedding(
        graph=graph,
        edge_id_to_wall_id=edge_id_to_wall_id,
        walls=walls,
        viewport_id=viewport.viewport_id,
    )
    # Coverage atoms may also arrive mixed into evidence_atoms / space labels.
    merged_coverage = tuple(coverage_atoms) + tuple(
        atom
        for atom in (*evidence_atoms, *space_label_atoms)
        if str(_atom_field(atom, "kind") or "") == VIEWPORT_COVERAGE_KIND
    )
    coverage_complete, coverage_reasons = resolve_viewport_coverage_authority(
        viewport=viewport,
        coverage_atoms=merged_coverage,
    )
    space_roles = resolve_space_roles(
        embedding,
        space_label_atoms=space_label_atoms,
        coverage_complete=coverage_complete,
    )

    overlapping: set[str] = set()
    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    for wall in walls:
        if wall.candidate_id in seen_ids:
            duplicate_ids.add(wall.candidate_id)
        seen_ids.add(wall.candidate_id)
    for i, left in enumerate(walls):
        left_segs = _wall_source_ids(left)
        for right in walls[i + 1 :]:
            if left.candidate_id == right.candidate_id:
                continue
            if left_segs & _wall_source_ids(right):
                overlapping.add(left.candidate_id)
                overlapping.add(right.candidate_id)

    records: list[WallBoundaryRoleEvidence] = []
    for wall in walls:
        reasons: list[str] = []
        supporting: list[str] = []
        conflicting: list[str] = []
        role = WallBoundaryRole.UNKNOWN
        status = EvidenceResolutionStatus.ABSTAINED
        left_face_id = None
        right_face_id = None
        left_space = None
        right_space = None

        if wall.viewport_id != viewport.viewport_id:
            reasons.append("wall_viewport_mismatch")
        if viewport.document_id != document.document_id:
            reasons.append("viewport_document_mismatch")
        if wall.candidate_id in duplicate_ids:
            reasons.append("duplicate_wall_identity")
        if wall.candidate_id in overlapping:
            reasons.append("overlapping_wall_source_segments")
        if wall_lies_on_viewport_boundary(wall, viewport):
            reasons.append("insufficient_viewport_coverage")
        reasons.extend(coverage_reasons)

        existence = wall_physical_existence_status(
            wall,
            evidence_atoms=evidence_atoms,
            document=document,
            viewport=viewport,
        )
        if existence != EvidenceResolutionStatus.CORROBORATED:
            reasons.append("physical_wall_existence_not_corroborated")
            if existence == EvidenceResolutionStatus.CONFLICT:
                reasons.append("physical_wall_existence_conflict")
                status = EvidenceResolutionStatus.CONFLICT
                role = WallBoundaryRole.CONFLICT

        assignment = embedding.assignments.get(wall.candidate_id)
        if assignment is None:
            reasons.append("wall_missing_from_planar_embedding")
        else:
            reasons.extend(assignment.blockers)
            if len(assignment.left_face_ids) == 1:
                left_face_id = assignment.left_face_ids[0]
            if len(assignment.right_face_ids) == 1:
                right_face_id = assignment.right_face_ids[0]
            left_space, left_reasons = _combine_side_roles(assignment.left_face_ids, space_roles)
            right_space, right_reasons = _combine_side_roles(assignment.right_face_ids, space_roles)
            reasons.extend(left_reasons)
            reasons.extend(right_reasons)
            if left_face_id is not None and left_face_id == right_face_id:
                reasons.append("same_face_both_sides")

        explicit_roles, explicit_ids = _explicit_roles_for_wall(wall, explicit_role_atoms)
        if len(set(explicit_roles)) > 1:
            reasons.append("conflicting_explicit_wall_role_evidence")
            conflicting.extend(explicit_ids)
            role = WallBoundaryRole.CONFLICT
            status = EvidenceResolutionStatus.CONFLICT
        elif len(set(explicit_roles)) == 1:
            supporting.extend(explicit_ids)

        topology_role, topology_reasons = _role_from_sides(left_space, right_space)
        reasons.extend(topology_reasons)

        blocker_set = {
            "wall_viewport_mismatch",
            "viewport_document_mismatch",
            "duplicate_wall_identity",
            "overlapping_wall_source_segments",
            "insufficient_viewport_coverage",
            "physical_wall_existence_not_corroborated",
            "physical_wall_existence_conflict",
            "wall_missing_from_planar_embedding",
            "missing_twin_half_edge",
            "same_face_both_sides",
            "conflicting_explicit_wall_role_evidence",
            "conflicting_space_roles_on_same_side",
            "viewport_coverage_unproven",
            "viewport_coverage_incomplete",
            "conflicting_viewport_coverage_evidence",
            "viewport_coverage_viewport_mismatch",
            "topologically_unbounded_without_architectural_exterior",
            "bounded_face_adjacent_to_unbounded_without_coverage_authority",
            "ambiguous_space_role",
        }
        hard_block = any(r in blocker_set for r in reasons)
        if role != WallBoundaryRole.CONFLICT and not hard_block:
            if explicit_roles:
                declared = explicit_roles[0]
                if topology_role in (WallBoundaryRole.UNKNOWN, declared):
                    if topology_role == declared or (
                        topology_role == WallBoundaryRole.UNKNOWN and declared in (WallBoundaryRole.EXTERNAL, WallBoundaryRole.INTERNAL_PARTITION)
                    ):
                        # Explicit role cannot override missing sides into firm EXTERNAL
                        # unless topology already produced the same role.
                        if topology_role == declared:
                            role = declared
                            status = EvidenceResolutionStatus.CORROBORATED
                        else:
                            role = WallBoundaryRole.UNKNOWN
                            status = EvidenceResolutionStatus.ABSTAINED
                            reasons.append("explicit_role_without_authoritative_sides")
                    else:
                        role = WallBoundaryRole.CONFLICT
                        status = EvidenceResolutionStatus.CONFLICT
                        reasons.append("explicit_role_conflicts_with_topology")
                        conflicting.extend(explicit_ids)
                elif topology_role != declared:
                    role = WallBoundaryRole.CONFLICT
                    status = EvidenceResolutionStatus.CONFLICT
                    reasons.append("explicit_role_conflicts_with_topology")
                    conflicting.extend(explicit_ids)
            elif topology_role in (WallBoundaryRole.EXTERNAL, WallBoundaryRole.INTERNAL_PARTITION):
                role = topology_role
                status = EvidenceResolutionStatus.CORROBORATED
            else:
                role = WallBoundaryRole.UNKNOWN
                status = EvidenceResolutionStatus.ABSTAINED
        elif role != WallBoundaryRole.CONFLICT:
            role = WallBoundaryRole.UNKNOWN
            status = EvidenceResolutionStatus.ABSTAINED
            if existence == EvidenceResolutionStatus.CONFLICT:
                role = WallBoundaryRole.CONFLICT
                status = EvidenceResolutionStatus.CONFLICT

        if status == EvidenceResolutionStatus.CORROBORATED:
            conflicting = []
        reason_codes = tuple(dict.fromkeys(reasons))
        payload = {
            "kind": WALL_BOUNDARY_ROLE_KIND,
            "wall_candidate_id": wall.candidate_id,
            "viewport_id": viewport.viewport_id,
            "left_face_id": left_face_id,
            "right_face_id": right_face_id,
            "role": role.value,
            "status": status.value,
            "reason_codes": list(reason_codes),
            "schema_version": WALL_BOUNDARY_ROLE_SCHEMA_VERSION,
            "coverage_complete": coverage_complete,
        }
        records.append(
            WallBoundaryRoleEvidence(
                wall_candidate_id=wall.candidate_id,
                viewport_id=viewport.viewport_id,
                left_face_id=left_face_id,
                right_face_id=right_face_id,
                role=role,
                status=status,
                supporting_evidence_ids=tuple(dict.fromkeys(supporting)),
                conflicting_evidence_ids=tuple(dict.fromkeys(conflicting)),
                reason_codes=reason_codes,
                evidence_id=stable_contract_id("wrole", payload),
                left_space_role=left_space.value if left_space else None,
                right_space_role=right_space.value if right_space else None,
                metadata={
                    "existence_status": existence.value,
                    "coverage_complete": coverage_complete,
                    "schema_version": WALL_BOUNDARY_ROLE_SCHEMA_VERSION,
                },
            )
        )
    return tuple(records)