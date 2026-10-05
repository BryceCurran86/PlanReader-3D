"""Benchmark-neutral source-closed export for live physical room areas.

This module does not discover rooms, dimensions, areas, benchmark identities, or
customer mappings. It only seals the room-area QuantityEvidence already emitted
by the live source-owned room pipeline and proves each quantity against the exact
source-room record plus its corroborating physical room and floor identities.
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from pb_live_canonical_floor_surface import LiveCanonicalFloorSurfaceObject
from pb_live_canonical_room_composition import LiveCanonicalRoomObject
from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
from pb_migration_contracts import QuantityEvidence
from pb_quantity_takeoff_adapter import CommercialTakeoffSourceTrace
from pb_source_closed_run_export import (
    SealedSourceClosedRun,
    SourceClosedRunConflictError,
    seal_source_closed_run,
)


def _clean(value: object) -> str:
    return str(value or "").strip()


def _room_and_floor_for_quantity(
    claim: LivePhysicalNetWallClaim,
    quantity: QuantityEvidence,
) -> tuple[LiveCanonicalRoomObject, LiveCanonicalFloorSurfaceObject]:
    if len(quantity.input_entity_ids) != 1:
        raise SourceClosedRunConflictError(
            "room-area quantity must reference exactly one source-room identity"
        )

    quantity_evidence_ids = {
        _clean(value) for value in quantity.evidence_ids if _clean(value)
    }
    if not quantity_evidence_ids:
        raise SourceClosedRunConflictError(
            f"room-area quantity has no evidence trace: {quantity.quantity_id}"
        )

    rooms = [
        room
        for room in claim.canonical_rooms
        if (
            type(room) is LiveCanonicalRoomObject
            and _clean(room.source_room_face_record_id) in quantity_evidence_ids
        )
    ]
    if len(rooms) != 1:
        raise SourceClosedRunConflictError(
            f"room-area quantity must map to exactly one canonical room: "
            f"{quantity.quantity_id}"
        )
    room = rooms[0]

    floors = [
        floor
        for floor in claim.canonical_floors
        if (
            type(floor) is LiveCanonicalFloorSurfaceObject
            and _clean(floor.source_room_face_record_id)
            == _clean(room.source_room_face_record_id)
            and _clean(floor.room_entity_id) == _clean(room.physical_room_id)
        )
    ]
    if len(floors) != 1:
        raise SourceClosedRunConflictError(
            f"room-area quantity must map to exactly one canonical floor: "
            f"{quantity.quantity_id}"
        )
    floor = floors[0]

    if (
        room.document_id != floor.document_id
        or room.revision_id != floor.revision_id
        or room.source_sha256.lower() != floor.source_sha256.lower()
        or str(room.page_id) != str(floor.page_id)
    ):
        raise SourceClosedRunConflictError(
            f"room/floor lineage mismatch for quantity {quantity.quantity_id}"
        )
    if not _clean(room.physical_room_id) or not _clean(floor.physical_floor_surface_id):
        raise SourceClosedRunConflictError(
            f"physical room/floor identity unavailable for quantity {quantity.quantity_id}"
        )
    return room, floor


def _source_closed_room_area_quantities(
    claim: LivePhysicalNetWallClaim,
) -> tuple[QuantityEvidence, ...]:
    """Return only positive source-closed quantities.

    Missing/blocked rooms remain absent from the sealed production run. They are
    not coerced to zero and are not manufactured as customer quantities.
    """
    return tuple(
        quantity
        for quantity in claim.room_area_quantity_evidence
        if (
            type(quantity) is QuantityEvidence
            and not quantity.abstained
            and quantity.value is not None
        )
    )


def build_live_room_area_source_traces(
    claim: LivePhysicalNetWallClaim,
    *,
    workspace_id: int,
    project_id: str,
) -> Mapping[str, CommercialTakeoffSourceTrace]:
    """Build exact benchmark-neutral source traces for live room-area quantities."""

    if type(claim) is not LivePhysicalNetWallClaim:
        raise TypeError("claim must be exact LivePhysicalNetWallClaim")

    traces: dict[str, CommercialTakeoffSourceTrace] = {}
    for quantity in _source_closed_room_area_quantities(claim):
        if type(quantity) is not QuantityEvidence:
            raise TypeError(
                "room_area_quantity_evidence must contain exact QuantityEvidence"
            )
        if _clean(quantity.family) != "room_area":
            raise SourceClosedRunConflictError(
                f"unexpected room-area quantity family: {quantity.family!r}"
            )
        room, floor = _room_and_floor_for_quantity(claim, quantity)

        metadata = dict(quantity.metadata or {})
        quantity_sha = _clean(metadata.get("source_sha256")).lower()
        quantity_revision = _clean(metadata.get("revision_id"))
        quantity_page = _clean(metadata.get("page_no"))
        quantity_viewport = _clean(metadata.get("viewport_id"))
        if not quantity_sha or quantity_sha != room.source_sha256.lower():
            raise SourceClosedRunConflictError(
                f"quantity/source SHA mismatch: {quantity.quantity_id}"
            )
        if not quantity_revision or quantity_revision != room.revision_id:
            raise SourceClosedRunConflictError(
                f"quantity/revision mismatch: {quantity.quantity_id}"
            )
        if not quantity_page or quantity_page != str(room.page_id):
            raise SourceClosedRunConflictError(
                f"quantity/page mismatch: {quantity.quantity_id}"
            )
        if not quantity_viewport:
            raise SourceClosedRunConflictError(
                f"quantity viewport unavailable: {quantity.quantity_id}"
            )

        source_room_identity = _clean(quantity.input_entity_ids[0])
        canonical_entity_ids = tuple(
            dict.fromkeys(
                (
                    source_room_identity,
                    _clean(room.physical_room_id),
                    _clean(floor.physical_floor_surface_id),
                )
            )
        )
        evidence_ids = tuple(
            dict.fromkeys(
                (
                    *(_clean(value) for value in quantity.evidence_ids),
                    _clean(room.source_room_face_record_id),
                    *(_clean(value) for value in room.evidence_ids),
                    *(_clean(value) for value in floor.evidence_ids),
                )
            )
        )
        canonical_entity_ids = tuple(value for value in canonical_entity_ids if value)
        evidence_ids = tuple(value for value in evidence_ids if value)

        trace = CommercialTakeoffSourceTrace(
            workspace_id=workspace_id,
            project_id=project_id,
            document_id=room.document_id,
            source_sha256=room.source_sha256,
            source_page=str(room.page_id),
            viewport_id=quantity_viewport,
            revision_id=room.revision_id,
            current_revision_id=room.revision_id,
            evidence_ids=evidence_ids,
            canonical_entity_ids=canonical_entity_ids,
            metadata={
                "family": quantity.family,
                "semantic_key": quantity.semantic_key,
                "source_room_identity": source_room_identity,
                "source_room_face_record_id": room.source_room_face_record_id,
                "physical_room_id": room.physical_room_id,
                "physical_floor_surface_id": floor.physical_floor_surface_id,
                "metric_floor_area_quantity_id": floor.metric_area_quantity_id,
            },
        )
        if quantity.quantity_id in traces:
            raise SourceClosedRunConflictError(
                f"duplicate room-area quantity id: {quantity.quantity_id}"
            )
        traces[quantity.quantity_id] = trace

    return MappingProxyType(traces)


def seal_live_room_area_run(
    claim: LivePhysicalNetWallClaim,
    *,
    workspace_id: int,
    project_id: str,
) -> SealedSourceClosedRun:
    """Seal current room-area quantities for later independent reconciliation."""

    if type(claim) is not LivePhysicalNetWallClaim:
        raise TypeError("claim must be exact LivePhysicalNetWallClaim")
    quantities = _source_closed_room_area_quantities(claim)
    traces = build_live_room_area_source_traces(
        claim,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    return seal_source_closed_run(
        quantities,
        project_id=project_id,
        traces_by_quantity_id=traces,
    )


__all__ = [
    "build_live_room_area_source_traces",
    "seal_live_room_area_run",
]
