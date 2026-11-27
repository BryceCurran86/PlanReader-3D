"""Report only (#4764 7209088255): page wall scopes against authenticated plan-view scopes, with and without non-wall paint.

For each page it summarises the page wall scope the live composition reads; the authenticated floor-plan viewport scopes (the
existing viewport builder) and the stricter source-owned proven physical plan-view scopes, each ``no_plan_view`` when there is
none; and each of those keeping only source paths the repository's wall-ink rule admits (raster segments, whose paint is
unknown, are kept). Each scope is reported as candidate counts, boundary taint, equivalence outcome,
the walls the live canonical rule would resolve (host frames are not considered, so this is a lower bound) and the room faces
whose every bounding wall is one of them. Nothing on a live path imports this; it changes, publishes and promotes nothing.
"""
from __future__ import annotations

import fitz

from pb_drawing_evidence_binding import DrawingViewType
from pb_layered_wall_doorway_room_ring_shadow import _source_wall_ink_role
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
    _build_authenticated_viewport_scope_results,
)
from pb_source_room_face_authority import _derive_scope
from pb_source_visibility_authority import SourceVisibilityProducer

NO_PLAN_VIEW = "no_plan_view"
PLAN_VIEW_TYPES = (DrawingViewType.FLOOR_PLAN.value, DrawingViewType.FLOOR_FINISH_PLAN.value)
VIEW_VARIANTS = ("authenticated_plan_views", "authenticated_plan_views_wall_ink", "proven_plan_views",
                 "proven_plan_views_wall_ink")


def resolved_wall_ids(scope) -> frozenset[str]:
    """The walls the live canonical composition would call resolved by equivalence in this scope."""
    equivalence = scope.equivalence
    if scope.status is not EvidenceResolutionStatus.CORROBORATED or not scope.scope_complete or equivalence is None:
        return frozenset()
    groups = [set(group) for group in equivalence.equivalence_groups]
    resolved: set[str] = set()
    for representative in equivalence.representative_wall_ids:
        resolved.update(next((group for group in groups if representative in group), {representative}))
    return frozenset(resolved)


def scope_summary(scope) -> dict:
    boundary, equivalence = scope.boundary_evaluation, scope.equivalence
    resolved = resolved_wall_ids(scope)
    faces = _derive_scope(scope)
    return {
        "view_type": scope.viewport_view_type,
        "status": scope.status.value,
        "scope_complete": bool(scope.scope_complete),
        "reason_codes": list(scope.reason_codes),
        "candidates": len(scope.records),
        "boundary_tainted": len(set(boundary.boundary_tainted_wall_candidate_ids)) if boundary is not None else None,
        # what keeps a bounded scope from being complete
        "primitives_crossing_boundary": len(scope.scope_boundary_observation_ids),
        "primitives_ownership_ambiguous": len(scope.ambiguous_source_observation_ids),
        "equivalence_representatives": len(equivalence.representative_wall_ids) if equivalence is not None else None,
        "equivalence_ambiguous": len(equivalence.ambiguous_wall_ids) if equivalence is not None else None,
        "resolved_walls": len(resolved),
        "room_faces_status": faces.status.value,
        "room_faces": len(faces.records),
        "room_faces_withheld": len(faces.abstained_faces),
        "room_faces_with_all_walls_resolved": sum(
            bool(face.bounding_wall_ids) and set(face.bounding_wall_ids) <= resolved for face in faces.records),
    }


def wall_plan_view_scope_report(source_producer: SourceVisibilityProducer, *, revision_id: str,
                                page_ids: tuple[str, ...]) -> dict:
    # the producer itself refuses anything but a source visibility producer
    page_authority = PhysicalWallCandidateProducer.from_source_visibility_producer(
        source_producer, page_ids=page_ids).authority()
    published = source_producer.published_snapshot_for_revision(revision_id)
    source_bytes = source_producer._producer._store.source_bytes_by_revision[revision_id]
    with fitz.open(stream=source_bytes, filetype="pdf") as document:
        drawings = {page_id: document[int(page_id) - 1].get_drawings() for page_id in page_ids}
    pages = []
    for page_id in page_ids:
        page_scope = page_authority.resolve_scope(PhysicalWallCandidateSelector(
            document_id=published.revision.document_id, revision_id=revision_id,
            source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
            page_id=page_id, decision_scope_id=f"wall-source:page-{page_id}"))

        def wall_ink(segment, rows=drawings[page_id]):
            index = segment.get("path_index")
            return index is None or _source_wall_ink_role(rows[index]) == "wall_support"

        row = {"page_id": page_id, "page_scope": scope_summary(page_scope)}
        for name in VIEW_VARIANTS:
            scopes = _build_authenticated_viewport_scope_results(
                source_producer=source_producer, published=published, source_bytes=source_bytes, page_id=page_id,
                physical_plan_view_shadow=name.startswith("proven"),
                source_segment_filter_shadow=wall_ink if name.endswith("wall_ink") else None)
            row[name] = [scope_summary(scope) for scope in scopes
                         if scope.viewport_view_type in PLAN_VIEW_TYPES] or NO_PLAN_VIEW
        pages.append(row)
    return {"source_sha256": published.revision.source_sha256, "revision_id": revision_id, "pages": pages}
