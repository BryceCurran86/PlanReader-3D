"""Live canonical room/space projection from source-authenticated room faces.

This module preserves producer-owned physical room identity and exact page-space
geometry for downstream canonical-building consumers. It does not mint metric
geometry, names, levels, finishes, quantities, or commercial authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Collection, Mapping, Optional

from pb_drawing_evidence_binding import DrawingViewType
from pb_live_wall_opening_authority_composition import (
    LiveWallOpeningAuthorityComposition,
)
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_room_face_authority import (
    SourceRoomFaceSelector,
    build_source_room_face_authority,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_source_room_label_authority import (
    SourceRoomLabelProducer,
    SourceRoomLabelRecord,
    SourceRoomLabelSelector,
)


LIVE_CANONICAL_ROOM_SCHEMA_VERSION = "1.2.0"
LIVE_PHYSICAL_ROOM_IDENTITY_SCHEMA_VERSION = "1.0.0"
LIVE_CANONICAL_ROOM_RESOLVED = "live_canonical_room_composition_resolved"
LIVE_CANONICAL_ROOM_PARTIAL = "live_canonical_room_composition_partial"
LIVE_CANONICAL_ROOM_FACE_UNIVERSE_PARTIAL = "live_canonical_room_face_universe_partial"
LIVE_CANONICAL_ROOM_UNAVAILABLE = "live_canonical_room_composition_unavailable"
LIVE_CANONICAL_ROOM_VIEWPORT_FALLBACK_RESOLVED = (
    "live_canonical_room_viewport_fallback_resolved"
)

@dataclass(frozen=True)
class LiveCanonicalRoomObject:
    """Stable physical room identity with source-owned page-space geometry."""

    canonical_room_id: str
    physical_room_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: Optional[str]
    decision_scope_id: str
    polygon_pdf_pts: tuple[tuple[float, float], ...]
    bounding_wall_ids: tuple[str, ...]
    canonical_bounding_wall_ids: tuple[str, ...]
    wall_relationships_complete: bool
    area_page_pts2: float
    source_room_face_record_id: str
    evidence_ids: tuple[str, ...]
    geometry_complete: bool
    metric_geometry_complete: bool
    room_label: Optional[str] = None
    room_label_binding_record_id: Optional[str] = None
    room_label_evidence_ids: tuple[str, ...] = ()
    room_label_reason_codes: tuple[str, ...] = ()
    coordinate_unit: str = "pdf_pt"
    schema_version: str = LIVE_CANONICAL_ROOM_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "canonical_room_id": self.canonical_room_id,
            "physical_room_id": self.physical_room_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "snapshot_id": self.snapshot_id,
            "page_id": self.page_id,
            "viewport_id": self.viewport_id,
            "decision_scope_id": self.decision_scope_id,
            "polygon_pdf_pts": [list(point) for point in self.polygon_pdf_pts],
            "bounding_wall_ids": list(self.bounding_wall_ids),
            "canonical_bounding_wall_ids": list(self.canonical_bounding_wall_ids),
            "wall_relationships_complete": self.wall_relationships_complete,
            "area_page_pts2": self.area_page_pts2,
            "source_room_face_record_id": self.source_room_face_record_id,
            "evidence_ids": list(self.evidence_ids),
            "geometry_complete": self.geometry_complete,
            "metric_geometry_complete": self.metric_geometry_complete,
            "room_label": self.room_label,
            "room_label_binding_record_id": self.room_label_binding_record_id,
            "room_label_evidence_ids": list(self.room_label_evidence_ids),
            "room_label_reason_codes": list(self.room_label_reason_codes),
            "coordinate_unit": self.coordinate_unit,
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True)
class LiveCanonicalRoomComposition:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    rooms: tuple[LiveCanonicalRoomObject, ...]
    source_pages: tuple[int, ...]
    schema_version: str = LIVE_CANONICAL_ROOM_SCHEMA_VERSION


def _dedupe(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _physical_room_id(record, *, viewport_id: Optional[str]) -> str:
    """Physical room identity separate from revision/evidence fingerprints.

    SourceRoomFace record ids deliberately remain revision/snapshot specific for
    reproducibility. A canonical physical room is instead scoped by the logical
    document, source page/view and the already-canonical source-room polygon.
    Producer version, revision SHA, snapshot id, source-face record id and wall
    evidence ids therefore cannot churn the physical room id when geometry is
    unchanged.
    """
    return stable_contract_id(
        "live_physical_room",
        {
            "identity_schema_version": LIVE_PHYSICAL_ROOM_IDENTITY_SCHEMA_VERSION,
            "document_id": str(record.document_id),
            "page_id": str(record.page_id),
            "viewport_id": str(viewport_id or ""),
            "polygon_pdf_pts": tuple(
                (float(point[0]), float(point[1]))
                for point in record.polygon_pdf_pts
            ),
        },
        digest_chars=32,
    )


def _room_object_from_record(
    record,
    *,
    viewport_id: Optional[str],
    canonical_wall_ids_by_candidate: Optional[Mapping[str, str]],
    unresolved_wall_candidate_ids: Optional[Collection[str]],
    room_label_record: Optional[SourceRoomLabelRecord] = None,
) -> LiveCanonicalRoomObject:
    canonical_boundary_ids: tuple[str, ...] = ()
    wall_relationships_complete = False
    if canonical_wall_ids_by_candidate is not None:
        mapped = [
            str(canonical_wall_ids_by_candidate.get(wall_id) or "")
            for wall_id in record.bounding_wall_ids
        ]
        if mapped and all(mapped):
            canonical_boundary_ids = tuple(dict.fromkeys(mapped))
            unresolved_ids = {
                str(value)
                for value in (unresolved_wall_candidate_ids or ())
                if str(value)
            }
            wall_relationships_complete = not any(
                wall_id in unresolved_ids for wall_id in record.bounding_wall_ids
            )

    physical_room_id = _physical_room_id(record, viewport_id=viewport_id)
    label_evidence_ids: tuple[str, ...] = ()
    label_reason_codes: tuple[str, ...] = ()
    if room_label_record is not None:
        label_evidence_ids = _dedupe(
            [
                *[str(value) for value in room_label_record.observation_ids],
                *[
                    str(word.authority_record_id)
                    for word in room_label_record.word_evidence
                ],
            ]
        )
        label_reason_codes = tuple(room_label_record.reason_codes)

    return LiveCanonicalRoomObject(
        canonical_room_id=physical_room_id,
        physical_room_id=physical_room_id,
        document_id=record.document_id,
        revision_id=record.revision_id,
        source_sha256=record.source_sha256,
        snapshot_id=record.snapshot_id,
        page_id=record.page_id,
        viewport_id=viewport_id,
        decision_scope_id=record.decision_scope_id,
        polygon_pdf_pts=record.polygon_pdf_pts,
        bounding_wall_ids=record.bounding_wall_ids,
        canonical_bounding_wall_ids=canonical_boundary_ids,
        wall_relationships_complete=wall_relationships_complete,
        area_page_pts2=float(record.area_page_pts2),
        source_room_face_record_id=record.record_id,
        evidence_ids=(record.record_id,),
        geometry_complete=True,
        metric_geometry_complete=False,
        room_label=(
            str(room_label_record.label)
            if room_label_record is not None
            else None
        ),
        room_label_binding_record_id=(
            str(room_label_record.record_id)
            if room_label_record is not None
            else None
        ),
        room_label_evidence_ids=label_evidence_ids,
        room_label_reason_codes=label_reason_codes,
    )


def compose_live_canonical_rooms(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    wall_opening_composition: LiveWallOpeningAuthorityComposition,
    canonical_wall_ids_by_candidate: Optional[Mapping[str, str]] = None,
    unresolved_wall_candidate_ids: Optional[Collection[str]] = None,
) -> LiveCanonicalRoomComposition:
    """Project sealed room-face authority into persistent canonical room objects."""

    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError("source_visibility_producer must be producer-owned")
    if type(wall_opening_composition) is not LiveWallOpeningAuthorityComposition:
        raise TypeError("wall_opening_composition must be live producer-owned composition")

    published = source_visibility_producer.published_snapshot_for_revision(
        wall_opening_composition.revision_id
    )
    if published is None:
        return LiveCanonicalRoomComposition(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(LIVE_CANONICAL_ROOM_UNAVAILABLE,),
            rooms=(),
            source_pages=(),
        )

    authority = build_source_room_face_authority(
        wall_opening_composition.physical_wall_candidate_authority
    )
    try:
        page_label_authority = SourceRoomLabelProducer.from_authorities(
            source_visibility_producer,
            authority,
            page_ids=tuple(wall_opening_composition.page_ids),
        ).authority()
    except Exception:
        # Room labels are semantic annotation only. A label-authority failure
        # must never destroy already-proven room geometry.
        page_label_authority = None

    rooms: list[LiveCanonicalRoomObject] = []
    reasons: list[str] = []
    resolved_pages: set[int] = set()
    room_pages: set[int] = set()
    unresolved_pages: list[str] = []
    viewport_fallback_used = False

    for page_id in wall_opening_composition.page_ids:
        selector = SourceRoomFaceSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id=page_id,
            decision_scope_id=f"wall-source:page-{page_id}",
        )
        result = authority.resolve_scope(selector)
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.scope_complete
            and result.records
        ):
            if str(page_id).isdigit():
                room_pages.add(int(page_id))
                if result.face_universe_complete:
                    resolved_pages.add(int(page_id))
                else:
                    reasons.append(LIVE_CANONICAL_ROOM_FACE_UNIVERSE_PARTIAL)
            label_records_by_face: dict[str, SourceRoomLabelRecord] = {}
            if page_label_authority is not None:
                label_result = page_label_authority.resolve_scope(
                    SourceRoomLabelSelector(
                        document_id=selector.document_id,
                        revision_id=selector.revision_id,
                        source_sha256=selector.source_sha256,
                        snapshot_id=selector.snapshot_id,
                        page_id=selector.page_id,
                        decision_scope_id=selector.decision_scope_id,
                    )
                )
                label_records_by_face = {
                    str(label.face_id): label for label in label_result.records
                }

            rooms.extend(
                _room_object_from_record(
                    record,
                    viewport_id=None,
                    canonical_wall_ids_by_candidate=canonical_wall_ids_by_candidate,
                    unresolved_wall_candidate_ids=unresolved_wall_candidate_ids,
                    room_label_record=label_records_by_face.get(str(record.face_id)),
                )
                for record in result.records
            )
        else:
            reasons.extend(result.reason_codes)
            unresolved_pages.append(str(page_id))

    # Page-wide ownership can abstain when unrelated reference furniture shares
    # the sheet with a physical drawing. Only for those pages, ask the existing
    # producer-owned viewport wall authority for authenticated floor-plan scopes.
    # No caller-supplied title, bbox, geometry, wall list, or completeness flag
    # enters this fallback.
    if unresolved_pages:
        viewport_wall_producer = (
            PhysicalWallCandidateProducer.from_authenticated_viewports(
                source_visibility_producer,
                page_ids=tuple(unresolved_pages),
            )
        )
        viewport_wall_authority = viewport_wall_producer.authority()
        viewport_published = source_visibility_producer.published_snapshot_for_revision(
            wall_opening_composition.revision_id
        )
        if (
            viewport_published is not None
            and viewport_published.revision.document_id
            == published.revision.document_id
            and viewport_published.revision.revision_id
            == published.revision.revision_id
            and viewport_published.revision.source_sha256
            == published.revision.source_sha256
        ):
            viewport_room_authority = build_source_room_face_authority(
                viewport_wall_authority
            )
            try:
                viewport_label_authority = SourceRoomLabelProducer.from_authorities(
                    source_visibility_producer,
                    viewport_room_authority,
                    page_ids=tuple(unresolved_pages),
                ).authority()
            except Exception:
                viewport_label_authority = None

            for page_id in unresolved_pages:
                selectors = (
                    viewport_wall_authority.selectors_for_authenticated_viewports(
                        document_id=viewport_published.revision.document_id,
                        revision_id=viewport_published.revision.revision_id,
                        source_sha256=viewport_published.revision.source_sha256,
                        snapshot_id=viewport_published.snapshot.snapshot_id,
                        page_id=page_id,
                        view_type=DrawingViewType.FLOOR_PLAN.value,
                    )
                )
                page_resolved = False
                page_face_universe_complete = True
                for wall_selector in selectors:
                    wall_scope = viewport_wall_authority.resolve_scope(wall_selector)
                    if (
                        wall_scope.status is not EvidenceResolutionStatus.CORROBORATED
                        or not wall_scope.records
                    ):
                        reasons.extend(wall_scope.reason_codes)
                        continue

                    room_result = viewport_room_authority.resolve_scope(
                        SourceRoomFaceSelector(
                            document_id=wall_selector.document_id,
                            revision_id=wall_selector.revision_id,
                            source_sha256=wall_selector.source_sha256,
                            snapshot_id=wall_selector.snapshot_id,
                            page_id=wall_selector.page_id,
                            decision_scope_id=wall_selector.decision_scope_id,
                        )
                    )
                    if (
                        room_result.status is not EvidenceResolutionStatus.CORROBORATED
                        or not room_result.scope_complete
                        or not room_result.records
                    ):
                        reasons.extend(room_result.reason_codes)
                        continue

                    label_records_by_face: dict[str, SourceRoomLabelRecord] = {}
                    if viewport_label_authority is not None:
                        label_result = viewport_label_authority.resolve_scope(
                            SourceRoomLabelSelector(
                                document_id=wall_selector.document_id,
                                revision_id=wall_selector.revision_id,
                                source_sha256=wall_selector.source_sha256,
                                snapshot_id=wall_selector.snapshot_id,
                                page_id=wall_selector.page_id,
                                decision_scope_id=wall_selector.decision_scope_id,
                            )
                        )
                        label_records_by_face = {
                            str(label.face_id): label
                            for label in label_result.records
                        }

                    rooms.extend(
                        _room_object_from_record(
                            record,
                            viewport_id=wall_scope.viewport_id,
                            canonical_wall_ids_by_candidate=canonical_wall_ids_by_candidate,
                            unresolved_wall_candidate_ids=unresolved_wall_candidate_ids,
                            room_label_record=label_records_by_face.get(str(record.face_id)),
                        )
                        for record in room_result.records
                    )
                    page_resolved = True
                    if not room_result.face_universe_complete:
                        page_face_universe_complete = False
                        reasons.append(LIVE_CANONICAL_ROOM_FACE_UNIVERSE_PARTIAL)
                    viewport_fallback_used = True

                if page_resolved and str(page_id).isdigit():
                    room_pages.add(int(page_id))
                    if page_face_universe_complete:
                        resolved_pages.add(int(page_id))

    rooms.sort(key=lambda room: (room.page_id, room.canonical_room_id))
    if rooms and len(resolved_pages) == len(wall_opening_composition.page_ids):
        return LiveCanonicalRoomComposition(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(
                (LIVE_CANONICAL_ROOM_RESOLVED,)
                if not viewport_fallback_used
                else (
                    LIVE_CANONICAL_ROOM_RESOLVED,
                    LIVE_CANONICAL_ROOM_VIEWPORT_FALLBACK_RESOLVED,
                )
            ),
            rooms=tuple(rooms),
            source_pages=tuple(sorted(room_pages)),
        )
    if rooms:
        return LiveCanonicalRoomComposition(
            status=EvidenceResolutionStatus.CANDIDATE,
            reason_codes=(
                LIVE_CANONICAL_ROOM_PARTIAL,
                *(
                    (LIVE_CANONICAL_ROOM_VIEWPORT_FALLBACK_RESOLVED,)
                    if viewport_fallback_used
                    else ()
                ),
                *_dedupe(reasons),
            ),
            rooms=tuple(rooms),
            source_pages=tuple(sorted(room_pages)),
        )
    return LiveCanonicalRoomComposition(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=(LIVE_CANONICAL_ROOM_UNAVAILABLE, *_dedupe(reasons)),
        rooms=(),
        source_pages=(),
    )


__all__ = [
    "LIVE_CANONICAL_ROOM_PARTIAL",
    "LIVE_CANONICAL_ROOM_FACE_UNIVERSE_PARTIAL",
    "LIVE_CANONICAL_ROOM_RESOLVED",
    "LIVE_CANONICAL_ROOM_SCHEMA_VERSION",
    "LIVE_CANONICAL_ROOM_UNAVAILABLE",
    "LIVE_CANONICAL_ROOM_VIEWPORT_FALLBACK_RESOLVED",
    "LIVE_PHYSICAL_ROOM_IDENTITY_SCHEMA_VERSION",
    "LiveCanonicalRoomComposition",
    "LiveCanonicalRoomObject",
    "compose_live_canonical_rooms",
]
