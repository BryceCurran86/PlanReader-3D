"""Shadow bridge from source-authenticated room faces to room-area quantities.

This module does not create a new room, scale, measurement, or quantity
authority. It composes existing producer-owned seams only:

    SourceRoomFaceAuthority
      -> build_owned_source_room_face_index
      -> EntityEvidence for each sealed room face
      -> build_room_area_quantities

The bridge is intentionally shadow/development infrastructure. It never
writes GenericPlanReaderExtractor predictions, benchmark definitions,
commercial rows, or JobHub payloads.

A room entity may be CORROBORATED here only because its geometry came from the
sealed SourceRoomFaceAuthority. Metric area remains governed by the existing
pb_room_area_quantity contract: without a current FIRM ScaleCalibration (or an
owned corroborated explicit area EvidenceAtom supplied by the caller), the
resulting room-area quantity abstains.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional

from pb_ceiling_lining_scope_binder import (
    OwnedTopologyRoomIndex,
    build_owned_source_room_face_index,
)
from pb_geometry_takeoff_model import ScaleCalibration
from pb_migration_contracts import (
    DocumentEvidence,
    EntityEvidence,
    EvidenceAtom,
    EvidenceResolutionStatus,
    QuantityEvidence,
    ViewportEvidence,
)
from pb_migration_provider_envelope import ProviderContext
from pb_room_area_quantity import build_room_area_quantities
from pb_source_room_face_authority import (
    SourceRoomFaceAuthority,
    SourceRoomFaceSelector,
)


SOURCE_ROOM_AREA_BRIDGE_SCHEMA_VERSION = "1.0.0"
SOURCE_ROOM_AREA_BRIDGE_RESOLVED = "source_room_area_bridge_resolved"
SOURCE_ROOM_AREA_BRIDGE_INDEX_UNAVAILABLE = "source_room_area_bridge_index_unavailable"
SOURCE_ROOM_AREA_BRIDGE_CONTEXT_MISMATCH = "source_room_area_bridge_context_mismatch"
SOURCE_ROOM_AREA_ENTITY_BOUND = "source_room_face_entity_bound"


@dataclass(frozen=True)
class SourceRoomAreaBridgeResult:
    """Immutable shadow composition result.

    status reports whether producer-owned room identity was established.
    Individual quantities may still be BLOCKED by the existing room-area
    authority, for example when scale is missing or provisional.
    """

    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    room_index: Optional[OwnedTopologyRoomIndex]
    document: DocumentEvidence
    entities: tuple[EntityEvidence, ...]
    quantities: tuple[QuantityEvidence, ...]
    schema_version: str = SOURCE_ROOM_AREA_BRIDGE_SCHEMA_VERSION

    @property
    def entities_by_room_id(self) -> Mapping[str, EntityEvidence]:
        return MappingProxyType(
            {entity.candidate_entity_id: entity for entity in self.entities}
        )


def _derived_document(
    document: DocumentEvidence,
    *,
    room_index: OwnedTopologyRoomIndex,
) -> DocumentEvidence:
    evidence_ids = set(document.evidence_ids)
    for room in room_index.rooms():
        evidence_ids.update(room.evidence)
    metadata = dict(document.metadata or {})
    metadata.update(
        {
            "source_room_area_bridge": True,
            "source_room_index_id": room_index.index_id,
            "source_room_geometry_source": room_index.geometry_source,
        }
    )
    return DocumentEvidence(
        document_id=document.document_id,
        source_sha256=document.source_sha256,
        page_count=document.page_count,
        page_ids=document.page_ids,
        evidence_ids=tuple(sorted(evidence_ids)),
        producer=document.producer,
        producer_version=document.producer_version,
        metadata=metadata,
    )


def _context_matches(
    *,
    room_index: OwnedTopologyRoomIndex,
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
    page_no: int,
) -> bool:
    if room_index.document_id != context.document_id:
        return False
    if document.document_id != context.document_id:
        return False
    if document.source_sha256.lower() != context.source_sha256.lower():
        return False
    if room_index.source_sha256.lower() != context.source_sha256.lower():
        return False
    if room_index.revision_id != str(context.current_revision_id or ""):
        return False
    if room_index.viewport_id != viewport.viewport_id:
        return False
    if room_index.page_id != viewport.page_id:
        return False
    if int(room_index.page_no) != int(page_no):
        return False
    return True


def build_source_room_area_bridge(
    *,
    room_face_authority: SourceRoomFaceAuthority,
    selector: SourceRoomFaceSelector,
    context: ProviderContext,
    document: DocumentEvidence,
    viewport: ViewportEvidence,
    page_no: int,
    scale_calibration: Optional[ScaleCalibration] = None,
    explicit_area_evidence_by_room_id: Optional[Mapping[str, EvidenceAtom]] = None,
) -> SourceRoomAreaBridgeResult:
    """Compose sealed room faces into existing room-area QuantityEvidence.

    No caller room polygon, room status, area value, scale factor, or entity
    status is accepted. The only room bodies consumed are those returned by
    build_owned_source_room_face_index from SourceRoomFaceAuthority.

    scale_calibration is passed unchanged to the existing room-area authority,
    which independently enforces freshness, viewport binding, and FIRM
    measurement authority. This bridge never promotes it.
    """

    room_index = build_owned_source_room_face_index(
        room_face_authority=room_face_authority,
        selector=selector,
        context=context,
        viewport=viewport,
    )
    if room_index is None or not room_index.is_producer_owned:
        return SourceRoomAreaBridgeResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(SOURCE_ROOM_AREA_BRIDGE_INDEX_UNAVAILABLE,),
            room_index=None,
            document=document,
            entities=(),
            quantities=(),
        )

    if not _context_matches(
        room_index=room_index,
        context=context,
        document=document,
        viewport=viewport,
        page_no=page_no,
    ):
        return SourceRoomAreaBridgeResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(SOURCE_ROOM_AREA_BRIDGE_CONTEXT_MISMATCH,),
            room_index=room_index,
            document=document,
            entities=(),
            quantities=(),
        )

    rooms = room_index.rooms()
    if not rooms:
        return SourceRoomAreaBridgeResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(SOURCE_ROOM_AREA_BRIDGE_INDEX_UNAVAILABLE,),
            room_index=room_index,
            document=document,
            entities=(),
            quantities=(),
        )

    owned_document = _derived_document(document, room_index=room_index)
    entities = tuple(
        EntityEvidence(
            candidate_entity_id=room.room_ref,
            candidate_type="room",
            evidence_ids=tuple(room.evidence),
            status=EvidenceResolutionStatus.CORROBORATED,
            confidence=float(room.geometry_confidence),
            reason_codes=(SOURCE_ROOM_AREA_ENTITY_BOUND,),
            metadata={
                "source_room_index_id": room_index.index_id,
                "source_room_geometry_source": room_index.geometry_source,
                "source_sha256": room_index.source_sha256,
                "revision_id": room_index.revision_id,
                "page_no": room_index.page_no,
                "page_id": room_index.page_id,
                "viewport_id": room_index.viewport_id,
            },
        )
        for room in rooms
    )
    entities_by_room_id = {
        entity.candidate_entity_id: entity for entity in entities
    }

    quantities = build_room_area_quantities(
        rooms=rooms,
        entities_by_room_id=entities_by_room_id,
        context=context,
        document=owned_document,
        viewport=viewport,
        page_no=page_no,
        scale_calibration=scale_calibration,
        explicit_area_evidence_by_room_id=(
            None
            if explicit_area_evidence_by_room_id is None
            else dict(explicit_area_evidence_by_room_id)
        ),
    )

    return SourceRoomAreaBridgeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(SOURCE_ROOM_AREA_BRIDGE_RESOLVED,),
        room_index=room_index,
        document=owned_document,
        entities=entities,
        quantities=quantities,
    )


__all__ = [
    "SOURCE_ROOM_AREA_BRIDGE_CONTEXT_MISMATCH",
    "SOURCE_ROOM_AREA_BRIDGE_INDEX_UNAVAILABLE",
    "SOURCE_ROOM_AREA_BRIDGE_RESOLVED",
    "SOURCE_ROOM_AREA_BRIDGE_SCHEMA_VERSION",
    "SOURCE_ROOM_AREA_ENTITY_BOUND",
    "SourceRoomAreaBridgeResult",
    "build_source_room_area_bridge",
]
