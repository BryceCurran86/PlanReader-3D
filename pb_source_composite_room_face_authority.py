"""Fail-closed composite source-room faces for grid-split room labels.

This producer repairs one narrow topology failure without deleting wall geometry:
an independently authenticated multi-word room label may be split across adjacent
SourceRoomFace records by drafting-grid walls. A composite is published only
when every internal face transition is separated exclusively by W4 candidates
whose contributing W2 edges all carry producer-owned source-lineage KIND_GRID
opposition. When the authenticated label words occupy only part of that grid
component, the producer completes the exact connected component through those
same proven grid separators. The final constituent union must be one valid
polygon, contain no conflicting authenticated room label, and expose no
remaining grid-opposed external boundary.

The producer never invents dimensions, metric area, room semantics, nearest-face
matches, or project-specific rules. Original wall and room-face authorities stay
unchanged and remain available for audit.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Mapping

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_wall_candidate_authority import PhysicalWallCandidateScopeResult
from pb_source_room_face_authority import SourceRoomFaceScopeResult
from pb_source_room_label_authority import (
    SourceRoomLabelScopeResult,
    SourceRoomSplitLabelCandidate,
)
from pb_wall_room_topology_typed_negative_evidence import (
    KIND_GRID,
    POLARITY_OPPOSING,
)


SOURCE_COMPOSITE_ROOM_FACE_SCHEMA_VERSION = "1.0.0"
SOURCE_COMPOSITE_ROOM_FACE_RESOLVED = "source_composite_room_face_resolved"
SOURCE_COMPOSITE_ROOM_FACE_UNAVAILABLE = "source_composite_room_face_unavailable"
SOURCE_COMPOSITE_ROOM_FACE_LINEAGE_CONFLICT = (
    "source_composite_room_face_lineage_conflict"
)
SOURCE_COMPOSITE_ROOM_FACE_SEPARATOR_UNRESOLVED = (
    "source_composite_room_face_separator_unresolved"
)
SOURCE_COMPOSITE_ROOM_FACE_UNION_UNRESOLVED = (
    "source_composite_room_face_union_unresolved"
)
SOURCE_LINEAGE_GRID_REASON = "source_lineage_dense_orthogonal_lattice"


@dataclass(frozen=True)
class CompositeSourceRoomFaceRecord:
    record_id: str
    face_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    polygon_pdf_pts: tuple[tuple[float, float], ...]
    bounding_wall_ids: tuple[str, ...]
    area_page_pts2: float
    label: str
    label_candidate_record_id: str
    label_evidence_ids: tuple[str, ...]
    constituent_face_ids: tuple[str, ...]
    constituent_source_room_face_record_ids: tuple[str, ...]
    separator_wall_ids: tuple[str, ...]
    grid_evidence_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    schema_version: str = SOURCE_COMPOSITE_ROOM_FACE_SCHEMA_VERSION


@dataclass(frozen=True)
class CompositeSourceRoomFaceResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    records: tuple[CompositeSourceRoomFaceRecord, ...]
    unresolved_label_candidate_ids: tuple[str, ...]
    schema_version: str = SOURCE_COMPOSITE_ROOM_FACE_SCHEMA_VERSION


def _lineage(value) -> tuple[str, str, str, str, str, str]:
    return (
        str(value.document_id),
        str(value.revision_id),
        str(value.source_sha256),
        str(value.snapshot_id),
        str(value.page_id),
        str(value.decision_scope_id),
    )


def _wall_edge_ids(record) -> tuple[str, ...]:
    wall = record.wall_candidate
    return tuple(
        dict.fromkeys(
            (
                *tuple(str(v) for v in (wall.face_a_segment_ids or ())),
                *tuple(str(v) for v in (wall.face_b_segment_ids or ())),
            )
        )
    )


def _fully_grid_opposed_wall_evidence(
    wall_scope: PhysicalWallCandidateScopeResult,
) -> tuple[set[str], Mapping[str, tuple[str, ...]]]:
    grid_evidence_by_edge: dict[str, set[str]] = defaultdict(set)
    for atom in tuple(wall_scope.typed_semantic_evidence_atoms or ()):
        metadata = dict(getattr(atom, "metadata", {}) or {})
        if (
            getattr(atom, "kind", None) != KIND_GRID
            or getattr(atom, "status", None) is not EvidenceResolutionStatus.CANDIDATE
            or str(metadata.get("polarity") or "") != POLARITY_OPPOSING
            or SOURCE_LINEAGE_GRID_REASON
            not in tuple(getattr(atom, "reason_codes", ()) or ())
        ):
            continue
        edge_id = str(metadata.get("target_edge_id") or "").strip()
        evidence_id = str(getattr(atom, "evidence_id", "") or "").strip()
        if edge_id and evidence_id:
            grid_evidence_by_edge[edge_id].add(evidence_id)

    fully: set[str] = set()
    evidence_by_wall: dict[str, tuple[str, ...]] = {}
    for record in wall_scope.records:
        wall_id = str(record.wall_candidate_id)
        edge_ids = _wall_edge_ids(record)
        if not edge_ids or not all(edge_id in grid_evidence_by_edge for edge_id in edge_ids):
            continue
        evidence_ids = tuple(
            sorted(
                {
                    evidence_id
                    for edge_id in edge_ids
                    for evidence_id in grid_evidence_by_edge.get(edge_id, ())
                }
            )
        )
        if evidence_ids:
            fully.add(wall_id)
            evidence_by_wall[wall_id] = evidence_ids
    return fully, evidence_by_wall


def _room_faces_by_wall(
    room_scope: SourceRoomFaceScopeResult,
) -> Mapping[str, tuple[str, ...]]:
    faces_by_wall: dict[str, list[str]] = defaultdict(list)
    for record in room_scope.records:
        face_id = str(record.face_id)
        for wall_id in tuple(str(value) for value in record.bounding_wall_ids):
            faces_by_wall[wall_id].append(face_id)
    return {
        wall_id: tuple(sorted(dict.fromkeys(face_ids)))
        for wall_id, face_ids in faces_by_wall.items()
    }


def _faces_share_positive_boundary_on_wall(left, right, wall_record) -> bool:
    """Require a shared edge that lies on the cited grid wall itself."""

    try:
        shared = Polygon(left.polygon_pdf_pts).boundary.intersection(
            Polygon(right.polygon_pdf_pts).boundary
        )
        points = tuple(
            (float(point[0]), float(point[1]))
            for point in wall_record.wall_candidate.centerline_pts
        )
        if len(points) < 2:
            return False
        wall_line = LineString(points)
        on_wall = shared.intersection(wall_line)
    except Exception:
        return False
    return not on_wall.is_empty and float(on_wall.length) > 1e-6


def _grid_local_adjacency(
    room_scope: SourceRoomFaceScopeResult,
    wall_scope: PhysicalWallCandidateScopeResult,
    fully_grid_wall_ids: set[str],
) -> Mapping[str, tuple[tuple[str, str], ...]]:
    """Return local face neighbours proven across a grid wall.

    One W4 wall candidate may span many drafting cells, so global owner count is
    not a valid adjacency test. Two faces are neighbours only when they both
    cite the same fully-grid wall *and* their exact polygons share a positive-
    length boundary segment.
    """

    room_by_face = {str(record.face_id): record for record in room_scope.records}
    faces_by_wall = _room_faces_by_wall(room_scope)
    wall_record_by_id = {
        str(record.wall_candidate_id): record for record in wall_scope.records
    }
    adjacency: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for wall_id in sorted(fully_grid_wall_ids):
        wall_record = wall_record_by_id.get(wall_id)
        if wall_record is None:
            continue
        owners = faces_by_wall.get(wall_id, ())
        for index, left_id in enumerate(owners):
            left = room_by_face[left_id]
            for right_id in owners[index + 1 :]:
                right = room_by_face[right_id]
                if not _faces_share_positive_boundary_on_wall(
                    left, right, wall_record
                ):
                    continue
                adjacency[left_id].add((right_id, wall_id))
                adjacency[right_id].add((left_id, wall_id))
    return {
        face_id: tuple(sorted(values))
        for face_id, values in adjacency.items()
    }


def _grid_connected_component(
    seed_face_ids: tuple[str, ...],
    *,
    room_scope: SourceRoomFaceScopeResult,
    wall_scope: PhysicalWallCandidateScopeResult,
    fully_grid_wall_ids: set[str],
) -> tuple[str, ...] | None:
    """Complete one room through locally-proven drafting-grid separators."""

    room_by_face = {str(record.face_id): record for record in room_scope.records}
    seeds = tuple(dict.fromkeys(str(value) for value in seed_face_ids))
    if len(seeds) < 2 or any(face_id not in room_by_face for face_id in seeds):
        return None

    adjacency = _grid_local_adjacency(
        room_scope, wall_scope, fully_grid_wall_ids
    )
    visited: set[str] = {seeds[0]}
    pending = [seeds[0]]
    while pending:
        face_id = pending.pop()
        for neighbour, _wall_id in adjacency.get(face_id, ()):
            if neighbour not in visited:
                visited.add(neighbour)
                pending.append(neighbour)

    if any(seed not in visited for seed in seeds):
        return None
    return tuple(sorted(visited))


def _grid_wall_persists_on_union_boundary(
    wall_record,
    merged: Polygon,
) -> bool:
    """Whether source-proven grid centerline remains on the composite exterior."""

    try:
        points = tuple(
            (float(point[0]), float(point[1]))
            for point in wall_record.wall_candidate.centerline_pts
        )
        if len(points) < 2:
            return True
        line = LineString(points)
        overlap = merged.boundary.intersection(line)
    except Exception:
        return True
    return not overlap.is_empty and float(overlap.length) > 1e-6


def _component_has_conflicting_label(
    component_face_ids: tuple[str, ...],
    candidate: SourceRoomSplitLabelCandidate,
    *,
    label_scope: SourceRoomLabelScopeResult,
) -> bool:
    """Block a completed grid component that contains another room identity."""

    component = set(component_face_ids)
    if any(
        str(record.face_id) in component
        for record in tuple(label_scope.records or ())
    ):
        return True

    for other in tuple(label_scope.split_face_candidates or ()):
        if str(other.record_id) == str(candidate.record_id):
            continue
        if component.intersection(str(value) for value in other.word_face_ids):
            return True
    return False


def _candidate_record(
    candidate: SourceRoomSplitLabelCandidate,
    *,
    wall_scope: PhysicalWallCandidateScopeResult,
    room_scope: SourceRoomFaceScopeResult,
    label_scope: SourceRoomLabelScopeResult,
    fully_grid_wall_ids: set[str],
    grid_evidence_by_wall: Mapping[str, tuple[str, ...]],
) -> CompositeSourceRoomFaceRecord | None:
    room_by_face = {str(record.face_id): record for record in room_scope.records}
    seed_face_ids = tuple(str(value) for value in candidate.word_face_ids)
    constituent_face_ids = _grid_connected_component(
        seed_face_ids,
        room_scope=room_scope,
        wall_scope=wall_scope,
        fully_grid_wall_ids=fully_grid_wall_ids,
    )
    if constituent_face_ids is None:
        return None
    if _component_has_conflicting_label(
        constituent_face_ids,
        candidate,
        label_scope=label_scope,
    ):
        return None

    constituent = [room_by_face[face_id] for face_id in constituent_face_ids]
    polygons = [Polygon(record.polygon_pdf_pts) for record in constituent]
    if any(poly.is_empty or not poly.is_valid or poly.area <= 0.0 for poly in polygons):
        return None
    merged = unary_union(polygons)
    if (
        merged.geom_type != "Polygon"
        or merged.is_empty
        or not merged.is_valid
        or merged.area <= 0.0
        or len(tuple(merged.interiors)) != 0
    ):
        return None

    polygon = tuple(
        (round(float(x), 6), round(float(y), 6))
        for x, y in tuple(merged.exterior.coords)[:-1]
    )
    if len(polygon) < 3:
        return None

    wall_counts = Counter(
        str(wall_id)
        for record in constituent
        for wall_id in record.bounding_wall_ids
    )
    component_face_set = set(constituent_face_ids)
    adjacency = _grid_local_adjacency(
        room_scope, wall_scope, fully_grid_wall_ids
    )
    separator_wall_ids = {
        wall_id
        for face_id in component_face_set
        for neighbour, wall_id in adjacency.get(face_id, ())
        if neighbour in component_face_set
    }
    if not separator_wall_ids:
        return None

    # Preserve #1683 using actual source wall geometry rather than wall-owner
    # counts. A long grid candidate may separate multiple local cells, but it
    # cannot remain coincident with any positive-length segment of the final
    # room exterior.
    wall_record_by_id = {
        str(record.wall_candidate_id): record for record in wall_scope.records
    }
    for wall_id in fully_grid_wall_ids:
        wall_record = wall_record_by_id.get(wall_id)
        if wall_record is None:
            continue
        if _grid_wall_persists_on_union_boundary(wall_record, merged):
            return None

    # Non-grid walls remain physical boundary candidates even when the same
    # long wall id bounds several constituent cells.
    external_walls = tuple(
        sorted(
            wall_id
            for wall_id in wall_counts
            if wall_id not in separator_wall_ids
        )
    )
    if not external_walls:
        return None

    grid_evidence_ids: set[str] = set()
    for wall_id in separator_wall_ids:
        grid_evidence_ids.update(grid_evidence_by_wall.get(wall_id, ()))
    if not grid_evidence_ids:
        return None

    constituent_record_ids = tuple(
        room_by_face[face_id].record_id for face_id in constituent_face_ids
    )
    decision_scope_id = stable_contract_id(
        "composite_source_room_face_scope",
        {
            "document_id": candidate.document_id,
            "page_id": candidate.page_id,
            "parent_decision_scope_id": candidate.decision_scope_id,
            "label_candidate_record_id": candidate.record_id,
            "constituent_source_room_face_record_ids": constituent_record_ids,
        },
        digest_chars=32,
    )
    face_id = stable_contract_id(
        "composite_source_room_face",
        {
            "document_id": candidate.document_id,
            "revision_id": candidate.revision_id,
            "source_sha256": candidate.source_sha256,
            "snapshot_id": candidate.snapshot_id,
            "page_id": candidate.page_id,
            "decision_scope_id": decision_scope_id,
            "polygon_pdf_pts": polygon,
        },
        digest_chars=32,
    )
    label_evidence_ids = tuple(
        dict.fromkeys(
            (
                *candidate.observation_ids,
                *(str(word.authority_record_id) for word in candidate.word_evidence),
            )
        )
    )
    grid_ids = tuple(sorted(grid_evidence_ids))
    evidence_ids = tuple(
        dict.fromkeys(
            (
                *constituent_record_ids,
                candidate.record_id,
                *label_evidence_ids,
                *grid_ids,
            )
        )
    )
    record_id = stable_contract_id(
        "composite_source_room_face_record",
        {
            "face_id": face_id,
            "label_candidate_record_id": candidate.record_id,
            "constituent_source_room_face_record_ids": constituent_record_ids,
            "separator_wall_ids": tuple(sorted(separator_wall_ids)),
            "grid_evidence_ids": grid_ids,
        },
        digest_chars=32,
    )
    return CompositeSourceRoomFaceRecord(
        record_id=record_id,
        face_id=face_id,
        document_id=candidate.document_id,
        revision_id=candidate.revision_id,
        source_sha256=candidate.source_sha256,
        snapshot_id=candidate.snapshot_id,
        page_id=candidate.page_id,
        decision_scope_id=decision_scope_id,
        polygon_pdf_pts=polygon,
        bounding_wall_ids=external_walls,
        area_page_pts2=float(merged.area),
        label=candidate.label,
        label_candidate_record_id=candidate.record_id,
        label_evidence_ids=label_evidence_ids,
        constituent_face_ids=constituent_face_ids,
        constituent_source_room_face_record_ids=constituent_record_ids,
        separator_wall_ids=tuple(sorted(separator_wall_ids)),
        grid_evidence_ids=grid_ids,
        evidence_ids=evidence_ids,
    )


def compose_grid_separated_room_faces(
    *,
    wall_scope: PhysicalWallCandidateScopeResult,
    room_scope: SourceRoomFaceScopeResult,
    label_scope: SourceRoomLabelScopeResult,
) -> CompositeSourceRoomFaceResult:
    """Publish only exact, connected composites of authenticated split labels."""

    if (
        type(wall_scope) is not PhysicalWallCandidateScopeResult
        or type(room_scope) is not SourceRoomFaceScopeResult
        or type(label_scope) is not SourceRoomLabelScopeResult
    ):
        raise TypeError("composite room inputs must be exact producer-owned scope results")
    if not (_lineage(wall_scope) == _lineage(room_scope) == _lineage(label_scope)):
        return CompositeSourceRoomFaceResult(
            status=EvidenceResolutionStatus.CONFLICT,
            reason_codes=(SOURCE_COMPOSITE_ROOM_FACE_LINEAGE_CONFLICT,),
            records=(),
            unresolved_label_candidate_ids=tuple(
                candidate.record_id for candidate in label_scope.split_face_candidates
            ),
        )
    if (
        wall_scope.status is not EvidenceResolutionStatus.CORROBORATED
        or room_scope.status is not EvidenceResolutionStatus.CORROBORATED
        or not room_scope.scope_complete
        or not room_scope.records
        or not label_scope.split_face_candidates
    ):
        return CompositeSourceRoomFaceResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(SOURCE_COMPOSITE_ROOM_FACE_UNAVAILABLE,),
            records=(),
            unresolved_label_candidate_ids=tuple(
                candidate.record_id for candidate in label_scope.split_face_candidates
            ),
        )

    fully_grid, evidence_by_wall = _fully_grid_opposed_wall_evidence(wall_scope)
    records: list[CompositeSourceRoomFaceRecord] = []
    unresolved: list[str] = []
    for candidate in label_scope.split_face_candidates:
        record = _candidate_record(
            candidate,
            wall_scope=wall_scope,
            room_scope=room_scope,
            label_scope=label_scope,
            fully_grid_wall_ids=fully_grid,
            grid_evidence_by_wall=evidence_by_wall,
        )
        if record is None:
            unresolved.append(candidate.record_id)
        else:
            records.append(record)

    records.sort(key=lambda record: (record.label, record.record_id))
    if records and not unresolved:
        status = EvidenceResolutionStatus.CORROBORATED
        reasons = (SOURCE_COMPOSITE_ROOM_FACE_RESOLVED,)
    elif records:
        status = EvidenceResolutionStatus.CANDIDATE
        reasons = (
            SOURCE_COMPOSITE_ROOM_FACE_RESOLVED,
            SOURCE_COMPOSITE_ROOM_FACE_SEPARATOR_UNRESOLVED,
        )
    else:
        status = EvidenceResolutionStatus.ABSTAINED
        reasons = (
            SOURCE_COMPOSITE_ROOM_FACE_SEPARATOR_UNRESOLVED,
            SOURCE_COMPOSITE_ROOM_FACE_UNION_UNRESOLVED,
        )
    return CompositeSourceRoomFaceResult(
        status=status,
        reason_codes=reasons,
        records=tuple(records),
        unresolved_label_candidate_ids=tuple(sorted(unresolved)),
    )


__all__ = [
    "SOURCE_COMPOSITE_ROOM_FACE_SCHEMA_VERSION",
    "SOURCE_COMPOSITE_ROOM_FACE_RESOLVED",
    "SOURCE_COMPOSITE_ROOM_FACE_UNAVAILABLE",
    "SOURCE_COMPOSITE_ROOM_FACE_LINEAGE_CONFLICT",
    "SOURCE_COMPOSITE_ROOM_FACE_SEPARATOR_UNRESOLVED",
    "SOURCE_COMPOSITE_ROOM_FACE_UNION_UNRESOLVED",
    "CompositeSourceRoomFaceRecord",
    "CompositeSourceRoomFaceResult",
    "compose_grid_separated_room_faces",
]
