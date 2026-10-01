"""Live canonical room/space projection from source-authenticated room faces.

This module preserves producer-owned physical room identity and exact page-space
geometry for downstream canonical-building consumers. It does not mint metric
geometry, names, levels, finishes, quantities, or commercial authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pb_live_wall_opening_authority_composition import (
    LiveWallOpeningAuthorityComposition,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_room_face_authority import (
    SourceRoomFaceSelector,
    build_source_room_face_authority,
)
from pb_source_visibility_authority import SourceVisibilityProducer


LIVE_CANONICAL_ROOM_SCHEMA_VERSION = "1.0.0"
LIVE_CANONICAL_ROOM_RESOLVED = "live_canonical_room_composition_resolved"
LIVE_CANONICAL_ROOM_PARTIAL = "live_canonical_room_composition_partial"
LIVE_CANONICAL_ROOM_UNAVAILABLE = "live_canonical_room_composition_unavailable"

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
    area_page_pts2: float
    source_room_face_record_id: str
    evidence_ids: tuple[str, ...]
    geometry_complete: bool
    metric_geometry_complete: bool
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
            "area_page_pts2": self.area_page_pts2,
            "source_room_face_record_id": self.source_room_face_record_id,
            "evidence_ids": list(self.evidence_ids),
            "geometry_complete": self.geometry_complete,
            "metric_geometry_complete": self.metric_geometry_complete,
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

def compose_live_canonical_rooms(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    wall_opening_composition: LiveWallOpeningAuthorityComposition,
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
    rooms: list[LiveCanonicalRoomObject] = []
    reasons: list[str] = []
    resolved_pages: set[int] = set()

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
                resolved_pages.add(int(page_id))
            for record in result.records:
                rooms.append(
                    LiveCanonicalRoomObject(
                        canonical_room_id=record.face_id,
                        physical_room_id=record.face_id,
                        document_id=record.document_id,
                        revision_id=record.revision_id,
                        source_sha256=record.source_sha256,
                        snapshot_id=record.snapshot_id,
                        page_id=record.page_id,
                        viewport_id=None,
                        decision_scope_id=record.decision_scope_id,
                        polygon_pdf_pts=record.polygon_pdf_pts,
                        bounding_wall_ids=record.bounding_wall_ids,
                        area_page_pts2=float(record.area_page_pts2),
                        source_room_face_record_id=record.record_id,
                        evidence_ids=(record.record_id,),
                        geometry_complete=True,
                        metric_geometry_complete=False,
                    )
                )
        else:
            reasons.extend(result.reason_codes)

    rooms.sort(key=lambda room: (room.page_id, room.canonical_room_id))
    if rooms and len(resolved_pages) == len(wall_opening_composition.page_ids):
        return LiveCanonicalRoomComposition(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(LIVE_CANONICAL_ROOM_RESOLVED,),
            rooms=tuple(rooms),
            source_pages=tuple(sorted(resolved_pages)),
        )
    if rooms:
        return LiveCanonicalRoomComposition(
            status=EvidenceResolutionStatus.CANDIDATE,
            reason_codes=(LIVE_CANONICAL_ROOM_PARTIAL, *_dedupe(reasons)),
            rooms=tuple(rooms),
            source_pages=tuple(sorted(resolved_pages)),
        )
    return LiveCanonicalRoomComposition(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=(LIVE_CANONICAL_ROOM_UNAVAILABLE, *_dedupe(reasons)),
        rooms=(),
        source_pages=(),
    )


__all__ = [
    "LIVE_CANONICAL_ROOM_PARTIAL",
    "LIVE_CANONICAL_ROOM_RESOLVED",
    "LIVE_CANONICAL_ROOM_SCHEMA_VERSION",
    "LIVE_CANONICAL_ROOM_UNAVAILABLE",
    "LiveCanonicalRoomComposition",
    "LiveCanonicalRoomObject",
    "compose_live_canonical_rooms",
]
