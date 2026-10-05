"""Live source-owned cross-view room-area integration.

This composition does not discover rooms or dimensions independently. It joins:
- already-canonical source-owned rooms,
- the existing source room-face authority,
- authenticated cross-view figured-dimension area evidence, and
- the existing room-area quantity authority.

No scale is introduced by this path. A numeric quantity survives only when the
existing room-area authority returns a non-abstained FIRM QuantityEvidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import fitz

from pb_ceiling_lining_scope_binder import build_owned_source_room_face_index
from pb_geometry_takeoff_model import AuthorityStatus
from pb_hosted_opening_instance_adapter import authoritative_floor_plan_viewports
from pb_live_canonical_room_composition import LiveCanonicalRoomObject
from pb_live_wall_opening_authority_composition import LiveWallOpeningAuthorityComposition
from pb_migration_contracts import (
    DocumentEvidence,
    EvidenceResolutionStatus,
    QuantityEvidence,
    ViewportEvidence,
    ViewportResolutionStatus,
)
from pb_migration_provider_envelope import ProviderContext
from pb_source_room_area_bridge import build_source_room_area_bridge
from pb_source_room_cross_view_area_authority import (
    SOURCE_ROOM_CROSS_VIEW_AREA_RESOLVED,
    SourceRoomCrossViewAreaProducer,
    SourceRoomCrossViewAreaRecord,
)
from pb_source_room_face_authority import (
    SourceRoomFaceSelector,
    build_source_room_face_authority,
)
from pb_source_visibility_authority import SourceVisibilityProducer


LIVE_CROSS_VIEW_ROOM_AREA_SCHEMA_VERSION = "1.0.0"
LIVE_CROSS_VIEW_ROOM_AREA_RESOLVED = "live_cross_view_room_area_resolved"
LIVE_CROSS_VIEW_ROOM_AREA_UNAVAILABLE = "live_cross_view_room_area_unavailable"
LIVE_CROSS_VIEW_ROOM_AREA_QUANTITY_CONFLICT = (
    "live_cross_view_room_area_quantity_conflict"
)


@dataclass(frozen=True)
class LiveCrossViewRoomAreaResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    records: tuple[SourceRoomCrossViewAreaRecord, ...]
    quantities: tuple[QuantityEvidence, ...]
    schema_version: str = LIVE_CROSS_VIEW_ROOM_AREA_SCHEMA_VERSION


def _document_from_source(published) -> DocumentEvidence:
    page_count = int(published.coverage.total_pages)
    return DocumentEvidence(
        document_id=published.revision.document_id,
        source_sha256=published.revision.source_sha256,
        page_count=page_count,
        page_ids=tuple(str(index) for index in range(1, page_count + 1)),
        evidence_ids=(),
        producer=published.revision.producer_method,
        producer_version=published.revision.producer_version,
        metadata={
            "live_cross_view_room_area": True,
            "source_snapshot_id": published.snapshot.snapshot_id,
        },
    )


def collect_live_cross_view_room_area_quantities(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    wall_opening_composition: LiveWallOpeningAuthorityComposition,
    canonical_rooms: Sequence[LiveCanonicalRoomObject],
    source_bytes: bytes,
    topology_page_ids: Sequence[str],
) -> LiveCrossViewRoomAreaResult:
    """Publish firm room-area quantities from source-owned cross-view evidence."""

    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError("source_visibility_producer must be producer-owned")
    if type(wall_opening_composition) is not LiveWallOpeningAuthorityComposition:
        raise TypeError("wall_opening_composition must be producer-owned")
    if any(type(room) is not LiveCanonicalRoomObject for room in canonical_rooms):
        raise TypeError("canonical_rooms must contain LiveCanonicalRoomObject")

    revision_id = str(wall_opening_composition.revision_id or "").strip()
    published = source_visibility_producer.published_snapshot_for_revision(revision_id)
    if published is None or not canonical_rooms:
        return LiveCrossViewRoomAreaResult(
            EvidenceResolutionStatus.ABSTAINED,
            (LIVE_CROSS_VIEW_ROOM_AREA_UNAVAILABLE,),
            (),
            (),
        )

    room_face_authority = build_source_room_face_authority(
        wall_opening_composition.physical_wall_candidate_authority
    )
    cross_view = SourceRoomCrossViewAreaProducer.create(
        source_visibility=source_visibility_producer,
        room_face_authority=room_face_authority,
        canonical_rooms=canonical_rooms,
        source_bytes=source_bytes,
    ).publish(revision_id=revision_id)
    if not cross_view.records:
        return LiveCrossViewRoomAreaResult(
            cross_view.status,
            tuple(
                dict.fromkeys(
                    (
                        LIVE_CROSS_VIEW_ROOM_AREA_UNAVAILABLE,
                        *cross_view.reason_codes,
                    )
                )
            ),
            (),
            (),
        )

    records_by_room = {
        record.room_ref: record for record in cross_view.records
    }
    quantities_by_room: dict[str, QuantityEvidence] = {}
    conflicted_rooms: set[str] = set()
    reasons: list[str] = list(cross_view.reason_codes)

    pdf = fitz.open(stream=bytes(source_bytes), filetype="pdf")
    try:
        for page_id in tuple(dict.fromkeys(str(value) for value in topology_page_ids)):
            if not page_id.isdigit():
                continue
            page_no = int(page_id)
            page_index = page_no - 1
            if page_index < 0 or page_index >= len(pdf):
                continue

            rooms_on_page = tuple(
                room for room in canonical_rooms if str(room.page_id) == page_id
            )
            if not rooms_on_page:
                continue
            scope_keys = {
                (room.snapshot_id, room.decision_scope_id)
                for room in rooms_on_page
            }
            if len(scope_keys) != 1:
                continue
            snapshot_id, decision_scope_id = next(iter(scope_keys))
            selector = SourceRoomFaceSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=str(snapshot_id),
                page_id=page_id,
                decision_scope_id=str(decision_scope_id),
            )

            for segmented in authoritative_floor_plan_viewports(
                pdf[page_index],
                page_number=page_no,
            ):
                if segmented.bounding_box is None:
                    continue
                viewport_id = str(segmented.view_id or "").strip()
                if not viewport_id:
                    continue
                viewport = ViewportEvidence(
                    viewport_id=viewport_id,
                    document_id=published.revision.document_id,
                    page_id=page_id,
                    bbox=tuple(float(v) for v in segmented.bounding_box),
                    view_type="floor_plan",
                    status=ViewportResolutionStatus.RESOLVED,
                    evidence_ids=(),
                    confidence=float(segmented.confidence),
                )
                context = ProviderContext(
                    run_id=(
                        f"live-cross-room-area:{published.revision.revision_id}:"
                        f"{page_id}:{viewport_id}"
                    ),
                    workspace_id="live-extractor",
                    project_id="live-extractor",
                    document_id=published.revision.document_id,
                    source_sha256=published.revision.source_sha256,
                    revision_id=published.revision.revision_id,
                    current_revision_id=published.revision.revision_id,
                    selected_pages=(page_index,),
                    owned_viewport_ids=(viewport_id,),
                    evidence_snapshot_id=str(snapshot_id),
                    owned_page_numbers=(page_no,),
                    viewport_page_ownership=((viewport_id, page_no),),
                )
                room_index = build_owned_source_room_face_index(
                    room_face_authority=room_face_authority,
                    selector=selector,
                    context=context,
                    viewport=viewport,
                )
                if room_index is None:
                    continue
                scoped_records = {
                    room.room_ref: records_by_room[room.room_ref]
                    for room in room_index.rooms()
                    if room.room_ref in records_by_room
                }
                if not scoped_records:
                    continue

                bridge = build_source_room_area_bridge(
                    room_face_authority=room_face_authority,
                    selector=selector,
                    context=context,
                    document=_document_from_source(published),
                    viewport=viewport,
                    page_no=page_no,
                    scale_calibration=None,
                    cross_view_area_records_by_room_id=scoped_records,
                )
                if bridge.status is EvidenceResolutionStatus.CONFLICT:
                    reasons.extend(bridge.reason_codes)
                    conflicted_rooms.update(scoped_records)
                    continue

                for quantity in bridge.quantities:
                    if (
                        quantity.abstained
                        or quantity.value is None
                        or quantity.status != AuthorityStatus.FIRM.value
                        or len(quantity.input_entity_ids) != 1
                    ):
                        continue
                    room_ref = str(quantity.input_entity_ids[0])
                    if room_ref not in scoped_records:
                        continue
                    prior = quantities_by_room.get(room_ref)
                    if prior is None:
                        quantities_by_room[room_ref] = quantity
                    elif prior.to_dict() != quantity.to_dict():
                        quantities_by_room.pop(room_ref, None)
                        conflicted_rooms.add(room_ref)
                        reasons.append(LIVE_CROSS_VIEW_ROOM_AREA_QUANTITY_CONFLICT)
    finally:
        pdf.close()

    for room_ref in conflicted_rooms:
        quantities_by_room.pop(room_ref, None)

    quantities = tuple(
        quantities_by_room[room_ref]
        for room_ref in sorted(quantities_by_room)
    )
    records = tuple(
        record
        for record in sorted(
            cross_view.records,
            key=lambda item: item.room_ref,
        )
        if record.room_ref in quantities_by_room
    )
    if not quantities:
        return LiveCrossViewRoomAreaResult(
            EvidenceResolutionStatus.ABSTAINED,
            tuple(
                dict.fromkeys(
                    (
                        LIVE_CROSS_VIEW_ROOM_AREA_UNAVAILABLE,
                        *reasons,
                    )
                )
            ),
            (),
            (),
        )
    return LiveCrossViewRoomAreaResult(
        EvidenceResolutionStatus.CORROBORATED,
        tuple(
            dict.fromkeys(
                (
                    LIVE_CROSS_VIEW_ROOM_AREA_RESOLVED,
                    SOURCE_ROOM_CROSS_VIEW_AREA_RESOLVED,
                    *reasons,
                )
            )
        ),
        records,
        quantities,
    )


__all__ = [
    "LIVE_CROSS_VIEW_ROOM_AREA_QUANTITY_CONFLICT",
    "LIVE_CROSS_VIEW_ROOM_AREA_RESOLVED",
    "LIVE_CROSS_VIEW_ROOM_AREA_SCHEMA_VERSION",
    "LIVE_CROSS_VIEW_ROOM_AREA_UNAVAILABLE",
    "LiveCrossViewRoomAreaResult",
    "collect_live_cross_view_room_area_quantities",
]
