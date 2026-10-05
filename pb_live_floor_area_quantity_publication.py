"""Canonical-floor QuantityEvidence from already-FIRM live room-area authority.

This adapter does not measure floor area. It reissues a room-area quantity only
when the live claim already proves that exact quantity maps one-to-one to one
canonical floor and the floor retains the same value, authority, source lineage
and evidence.
"""
from __future__ import annotations

import math
from collections.abc import Mapping

from pb_geometry_takeoff_model import AuthorityStatus
from pb_live_canonical_floor_surface import LiveCanonicalFloorSurfaceObject
from pb_live_canonical_room_composition import LiveCanonicalRoomObject
from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
from pb_migration_contracts import QuantityEvidence, stable_contract_id


LIVE_FLOOR_AREA_QUANTITY_SCHEMA_VERSION = "1.0.0"


def _clean(value: object) -> str:
    return str(value or "").strip()


def _canonical_rooms_by_id(
    claim: LivePhysicalNetWallClaim,
) -> dict[str, LiveCanonicalRoomObject]:
    rooms: dict[str, LiveCanonicalRoomObject] = {}
    for room in claim.canonical_rooms:
        if type(room) is not LiveCanonicalRoomObject:
            raise TypeError("canonical_rooms must contain LiveCanonicalRoomObject")
        room_id = _clean(room.canonical_room_id)
        if not room_id:
            continue
        if room_id in rooms:
            raise ValueError(f"duplicate canonical room identity: {room_id}")
        rooms[room_id] = room
    return rooms


def publish_live_floor_area_quantities(
    claim: LivePhysicalNetWallClaim,
) -> tuple[QuantityEvidence, ...]:
    if type(claim) is not LivePhysicalNetWallClaim:
        raise TypeError("claim must be LivePhysicalNetWallClaim")

    source_quantities: dict[str, QuantityEvidence] = {}
    for quantity in claim.room_area_quantity_evidence:
        if not isinstance(quantity, QuantityEvidence):
            raise TypeError("room_area_quantity_evidence must contain QuantityEvidence")
        if (
            quantity.family != "room_area"
            or quantity.abstained
            or quantity.value is None
            or _clean(quantity.status).lower() != AuthorityStatus.FIRM.value
        ):
            continue
        qid = _clean(quantity.quantity_id)
        if not qid:
            continue
        if qid in source_quantities:
            raise ValueError(f"duplicate firm room-area quantity id: {qid}")
        source_quantities[qid] = quantity

    floors_by_quantity: dict[str, list[LiveCanonicalFloorSurfaceObject]] = {}
    for floor in claim.canonical_floors:
        if type(floor) is not LiveCanonicalFloorSurfaceObject:
            raise TypeError("canonical_floors must contain LiveCanonicalFloorSurfaceObject")
        qid = _clean(floor.metric_area_quantity_id)
        if qid:
            floors_by_quantity.setdefault(qid, []).append(floor)

    out: list[QuantityEvidence] = []
    for source_id, quantity in sorted(source_quantities.items()):
        floors = floors_by_quantity.get(source_id, ())
        if len(floors) != 1:
            continue
        floor = floors[0]
        if not floor.physical_floor_surface_identity_resolved:
            continue
        if not floor.physical_floor_surface_id or not floor.canonical_floor_id:
            continue
        try:
            qvalue = float(quantity.value)
            fvalue = float(floor.metric_area_m2)
        except (TypeError, ValueError, OverflowError):
            continue
        if (
            not math.isfinite(qvalue)
            or qvalue <= 0.0
            or not math.isfinite(fvalue)
            or abs(qvalue - fvalue) > 1e-9
        ):
            continue
        if _clean(floor.metric_area_authority) != _clean(quantity.authority):
            continue

        metadata = quantity.metadata if isinstance(quantity.metadata, Mapping) else {}
        if _clean(metadata.get("source_sha256")).lower() != floor.source_sha256.lower():
            continue
        if _clean(metadata.get("revision_id")) != floor.revision_id:
            continue
        if _clean(metadata.get("page_no")) != str(floor.page_id):
            continue
        q_viewport = _clean(metadata.get("viewport_id"))
        if not q_viewport:
            continue
        if floor.viewport_id and _clean(floor.viewport_id) != q_viewport:
            continue
        if not set(quantity.evidence_ids).issubset(set(floor.evidence_ids)):
            continue

        payload = {
            "schema_version": LIVE_FLOOR_AREA_QUANTITY_SCHEMA_VERSION,
            "upstream_room_area_quantity_id": source_id,
            "canonical_floor_id": floor.canonical_floor_id,
            "physical_floor_surface_id": floor.physical_floor_surface_id,
            "value_m2": qvalue,
            "authority": quantity.authority,
            "source_sha256": floor.source_sha256,
            "revision_id": floor.revision_id,
        }
        out.append(
            QuantityEvidence(
                quantity_id=stable_contract_id("floor_area_quantity", payload),
                family="floor_area",
                semantic_key=f"floor_area:{floor.physical_floor_surface_id}",
                value=qvalue,
                unit="m2",
                input_entity_ids=(floor.physical_floor_surface_id,),
                formula="reuse exact firm room-area authority for its one-to-one canonical floor",
                formula_version=LIVE_FLOOR_AREA_QUANTITY_SCHEMA_VERSION,
                evidence_ids=tuple(quantity.evidence_ids),
                authority=quantity.authority,
                status=AuthorityStatus.FIRM.value,
                confidence=float(quantity.confidence),
                abstained=False,
                blocking_reasons=(),
                reason_codes=tuple(quantity.reason_codes),
                metadata={
                    **dict(metadata),
                    "upstream_room_area_quantity_id": source_id,
                    "canonical_floor_id": floor.canonical_floor_id,
                    "physical_floor_surface_id": floor.physical_floor_surface_id,
                    "room_entity_id": floor.room_entity_id,
                    "source_room_face_record_id": floor.source_room_face_record_id,
                    "commercial_projection_allowed": True,
                    "row_role": "floor_area",
                },
            )
        )
    return tuple(sorted(out, key=lambda item: item.quantity_id))


def publish_live_canonical_room_area_quantities(
    claim: LivePhysicalNetWallClaim,
) -> tuple[QuantityEvidence, ...]:
    """Reissue already-FIRM room area onto exact canonical room identity."""
    if type(claim) is not LivePhysicalNetWallClaim:
        raise TypeError("claim must be LivePhysicalNetWallClaim")

    rooms = _canonical_rooms_by_id(claim)
    floor_quantities = publish_live_floor_area_quantities(claim)
    source_by_id = {
        _clean(quantity.quantity_id): quantity
        for quantity in claim.room_area_quantity_evidence
        if isinstance(quantity, QuantityEvidence)
    }

    out: list[QuantityEvidence] = []
    for floor_quantity in floor_quantities:
        metadata = (
            floor_quantity.metadata
            if isinstance(floor_quantity.metadata, Mapping)
            else {}
        )
        room_id = _clean(metadata.get("room_entity_id"))
        source_id = _clean(metadata.get("upstream_room_area_quantity_id"))
        room = rooms.get(room_id)
        source = source_by_id.get(source_id)
        if room is None or source is None:
            continue
        if not room.physical_room_id or not room.canonical_room_id:
            continue
        if _clean(room.source_room_face_record_id) != _clean(
            metadata.get("source_room_face_record_id")
        ):
            continue
        if room.source_sha256.lower() != floor_quantity.metadata.get(
            "source_sha256", ""
        ).lower():
            continue
        if room.revision_id != _clean(
            floor_quantity.metadata.get("revision_id")
        ):
            continue
        if str(room.page_id) != _clean(
            floor_quantity.metadata.get("page_no")
        ):
            continue
        if not set(source.evidence_ids).issubset(set(room.evidence_ids)):
            continue

        payload = {
            "schema_version": LIVE_FLOOR_AREA_QUANTITY_SCHEMA_VERSION,
            "upstream_room_area_quantity_id": source_id,
            "canonical_room_id": room.canonical_room_id,
            "physical_room_id": room.physical_room_id,
            "value_m2": float(floor_quantity.value),
            "authority": floor_quantity.authority,
            "source_sha256": room.source_sha256,
            "revision_id": room.revision_id,
        }
        out.append(
            QuantityEvidence(
                quantity_id=stable_contract_id(
                    "canonical_room_area_quantity",
                    payload,
                ),
                family="room_area",
                semantic_key=f"room_area:{room.physical_room_id}",
                value=float(floor_quantity.value),
                unit="m2",
                input_entity_ids=(room.physical_room_id,),
                formula=(
                    "reuse exact firm room-area authority for its one-to-one "
                    "canonical room"
                ),
                formula_version=LIVE_FLOOR_AREA_QUANTITY_SCHEMA_VERSION,
                evidence_ids=tuple(source.evidence_ids),
                authority=source.authority,
                status=AuthorityStatus.FIRM.value,
                confidence=float(source.confidence),
                abstained=False,
                blocking_reasons=(),
                reason_codes=tuple(source.reason_codes),
                metadata={
                    **(
                        dict(source.metadata)
                        if isinstance(source.metadata, Mapping)
                        else {}
                    ),
                    "upstream_room_area_quantity_id": source_id,
                    "canonical_room_id": room.canonical_room_id,
                    "physical_room_id": room.physical_room_id,
                    "source_room_face_record_id": room.source_room_face_record_id,
                    "commercial_projection_allowed": True,
                    "row_role": "floor_area",
                },
            )
        )
    return tuple(sorted(out, key=lambda item: item.quantity_id))


__all__ = [
    "LIVE_FLOOR_AREA_QUANTITY_SCHEMA_VERSION",
    "publish_live_canonical_room_area_quantities",
    "publish_live_floor_area_quantities",
]
