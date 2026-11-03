"""Fail-closed canonical floor-area -> customer draft projection.

Consumes only final floor_area QuantityEvidence already published on physical
canonical floor identity plus the exact source-closed floor trace. It does not
measure rooms/floors, infer scale, create identity, or grant estimator approval.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from pb_customer_output_verification import verify_sealed_customer_output

from pb_live_floor_area_quantity_publication import (
    publish_live_floor_area_quantities,
)
from pb_live_floor_area_source_closed_export import (
    build_live_floor_area_source_traces,
)
from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
from pb_migration_contracts import QuantityEvidence
from pb_source_closed_run_export import SourceClosedRunConflictError, seal_source_closed_run
from pb_quantity_takeoff_adapter import (
    CommercialMeasurementAuthority,
    quantities_to_takeoff_output_rows,
)


LIVE_FLOOR_AREA_CUSTOMER_PROJECTION_SCHEMA_VERSION = "1.0.0"


def _clean(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _source_floor_area_customer_fields(
    claim: LivePhysicalNetWallClaim,
    quantity: QuantityEvidence,
) -> dict[str, Any]:
    """Supply required workspace fields from a uniquely authenticated floor.

    The original room-area producer signs measurement/source lineage, but
    may not supply presentation fields. A correct FIRM m² was previously
    discarded by the real workspace adapter because 'location', 'section'
    or 'substrate' was empty. Never fabricate a room name: use original
    bound label when unique, otherwise the canonical source room identity.
    """
    metadata = (
        dict(quantity.metadata)
        if isinstance(quantity.metadata, Mapping) else {}
    )
    canonical_id = metadata.get("canonical_floor_id")
    physical_id = metadata.get("physical_floor_surface_id")
    floors = [
        floor for floor in claim.canonical_floors
        if (
            floor.canonical_floor_id == canonical_id
            and floor.physical_floor_surface_id == physical_id
            and floor.physical_floor_surface_id in quantity.input_entity_ids
        )
    ]
    if len(floors) != 1:
        raise SourceClosedRunConflictError(
            "floor-area customer row lacks unique original canonical floor"
        )
    floor = floors[0]
    room_id = floor.room_entity_id
    if type(room_id) is not str or not room_id or room_id != room_id.strip():
        raise SourceClosedRunConflictError(
            "floor-area customer row lacks original physical room identity"
        )
    rooms = [
        room for room in claim.canonical_rooms
        if getattr(room, "canonical_room_id", None) == room_id
    ]
    bound_label = None
    if len(rooms) == 1:
        room = rooms[0]
        label = getattr(room, "room_label", None)
        receipt = getattr(room, "room_label_binding_record_id", None)
        receipts = getattr(room, "room_label_evidence_ids", None)
        if (
            type(label) is str and label and label == label.strip()
            and type(receipt) is str and receipt and receipt == receipt.strip()
            and type(receipts) in (tuple, list) and receipts
            and all(
                type(value) is str and value and value == value.strip()
                for value in receipts
            )
            and len(set(receipts)) == len(receipts)
            and room.document_id == floor.document_id
            and room.revision_id == floor.revision_id
            and room.source_sha256.lower() == floor.source_sha256.lower()
            and room.snapshot_id == floor.snapshot_id
            and room.source_room_face_record_id == floor.source_room_face_record_id
            and not any(
                other is not room
                and type(getattr(other, "room_label", None)) is str
                and " ".join(other.room_label.casefold().split())
                == " ".join(label.casefold().split())
                for other in claim.canonical_rooms
            )
        ):
            bound_label = label

    original_location = metadata.get("location")
    if original_location is not None and (
        type(original_location) is not str
        or original_location != original_location.strip()
    ):
        raise SourceClosedRunConflictError(
            "floor-area original customer location is not canonical source text"
        )
    if (
        bound_label and original_location
        and " ".join(original_location.casefold().split())
        != " ".join(bound_label.casefold().split())
    ):
        raise SourceClosedRunConflictError(
            "floor-area original customer location contradicts canonical room"
        )

    # The source-reissued location/section/element are presentation fields.
    # Never change signed value, source SHA, evidence or area authority.
    metadata["location"] = original_location or bound_label or room_id
    for field, default in (
        ("section", "Internal"),
        ("element", "Floor area"),
        ("substrate", "Floor"),
    ):
        current = metadata.get(field)
        if current is not None and (
            type(current) is not str
            or current != current.strip()
        ):
            raise SourceClosedRunConflictError(
                f"floor-area original customer {field} is malformed"
            )
        metadata[field] = current or default
    metadata["row_role"] = "floor_area"
    # Source-authenticated ROOM area is a measured physical surface, not
    # an authenticated FT2/FT3 material occurrence. An inherited material
    # string on the upstream room record must not create a false priced
    # floor-finish claim. The separately sealed floor_finish_area family
    # owns exact FT source code and material attribution.
    metadata["finish_system"] = ""
    original_inclusion = metadata.get("inclusion_status")
    if original_inclusion is not None and (
        type(original_inclusion) is not str
        or original_inclusion != original_inclusion.strip()
    ):
        raise SourceClosedRunConflictError(
            "floor-area original inclusion status is malformed"
        )
    metadata["inclusion_status"] = original_inclusion or "INCLUSION"
    metadata["commercial_projection_allowed"] = True
    return metadata


def _measurement_authority(
    quantity: QuantityEvidence,
) -> CommercialMeasurementAuthority | None:
    metadata = quantity.metadata if isinstance(quantity.metadata, Mapping) else {}
    authority = (
        _clean(quantity.authority)
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    if authority in {
        "documented_dimension",
        "figured_dimension",
        "documented/figured",
    } or "figured" in authority:
        raw_ids = metadata.get("figured_dimension_ids")
        if (
            not isinstance(raw_ids, (tuple, list))
            or len(raw_ids) != 2
            or any(
                type(value) is not str or not value or value != value.strip()
                for value in raw_ids
            )
            or len(set(raw_ids)) != 2
        ):
            # One raw string, one source tick, or competing dimension
            # systems cannot authorize physical m² at customer projection.
            return None
        figured_ids = tuple(sorted(raw_ids))
        return CommercialMeasurementAuthority(
            method="figured_dimension",
            figured_dimension_ids=figured_ids,
            metadata={
                "source": "live_floor_area_customer_projection",
                "quantity_id": quantity.quantity_id,
                "upstream_room_area_quantity_id": metadata.get(
                    "upstream_room_area_quantity_id"
                ),
            },
        )

    if "scale" in authority or "geometry" in authority:
        scale_id = metadata.get("resolved_scale_id")
        scale_status = metadata.get("scale_status")
        raw_conflicts = metadata.get("scale_conflicts", ())
        if (
            type(scale_id) is not str or not scale_id
            or scale_id != scale_id.strip()
            or type(scale_status) is not str
            or scale_status not in {"resolved", "verified"}
            or type(raw_conflicts) not in (list, tuple)
            or raw_conflicts
        ):
            # A canonical floor may be measured only by a source-resolved
            # physical scale. Do not reclassify an unresolved source scope or
            # silently erase original conflicts in its customer metadata.
            return None
        conflicts = ()
        return CommercialMeasurementAuthority(
            method="scaled_geometry",
            resolved_scale_id=scale_id,
            scale_status=scale_status,
            scale_conflicts=conflicts,
            metadata={
                "source": "live_floor_area_customer_projection",
                "quantity_id": quantity.quantity_id,
                "scale_fingerprint": _clean(metadata.get("scale_fingerprint")),
            },
        )

    return None


def project_live_floor_area_customer_rows(
    claim: LivePhysicalNetWallClaim,
    *,
    workspace_id: int,
    project_id: str,
) -> tuple[dict[str, Any], ...]:
    """Project every final sealable floor_area quantity to one AI review row."""
    if type(claim) is not LivePhysicalNetWallClaim:
        raise TypeError("claim must be LivePhysicalNetWallClaim")
    if type(workspace_id) is not int or workspace_id <= 0:
        raise ValueError("workspace_id must be an authenticated positive integer")

    # The canonical room-area producer may intentionally abstain on an
    # identical provisional replay. The *final customer boundary* cannot
    # silently discard a duplicate source identity merely because NO room
    # survived the FIRM floor filter. Mirror the source-closed exporter's
    # original family and exact-ID census before the empty-return path.
    original_room_area_ids: set[str] = set()
    for source in claim.room_area_quantity_evidence:
        if not isinstance(source, QuantityEvidence):
            raise TypeError("room_area_quantity_evidence must contain QuantityEvidence")
        if source.family != "room_area":
            raise SourceClosedRunConflictError(
                "floor customer source inventory contains non-room-area quantity"
            )
        source_id = source.quantity_id
        if (
            type(source_id) is not str
            or not source_id
            or source_id != source_id.strip()
            or source_id in original_room_area_ids
        ):
            raise SourceClosedRunConflictError(
                f"duplicate or invalid original room-area source ID in customer projection: {source_id}"
            )
        original_room_area_ids.add(source_id)

        # This customer boundary returns early when no FIRM floor survives.
        # Retain contradictory original numeric FIRM source blockers instead
        # of misrepresenting a filtered partial/empty inventory as clean.
        # Ordinary provisional/ABSTAINED original sources stay unpublished.
        if (
            not source.abstained
            and source.value is not None
            and _clean(source.status).casefold() == "firm"
            and source.blocking_reasons
        ):
            raise SourceClosedRunConflictError(
                "original numeric firm room-area source retains unresolved blockers: "
                f"{source_id}"
            )

    quantities = tuple(
        quantity
        for quantity in publish_live_floor_area_quantities(claim)
        if (
            isinstance(quantity, QuantityEvidence)
            and not quantity.abstained
            and quantity.value is not None
            and not quantity.blocking_reasons
        )
    )
    if not quantities:
        return ()

    traces = build_live_floor_area_source_traces(
        claim,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    authorities = {
        quantity.quantity_id: authority
        for quantity in quantities
        for authority in (_measurement_authority(quantity),)
        if authority is not None
    }

    # Keep the already-FIRM source QuantityEvidence immutable. Only the
    # customer presentation copy gains source-backed location and required
    # workspace fields; the independently signed run below still uses the
    # original production quantity IDs/values/evidence.
    customer_quantities = tuple(
        replace(
            quantity,
            metadata=_source_floor_area_customer_fields(claim, quantity),
        )
        for quantity in quantities
    )
    # Missing measurement authority remains a hard adapter failure rather than
    # silently dropping an otherwise valid sealed floor quantity.
    rows = tuple(
        quantities_to_takeoff_output_rows(
            customer_quantities,
            traces_by_quantity_id=traces,
            authorities_by_quantity_id=authorities,
        )
    )
    sealed = seal_source_closed_run(
        quantities,
        project_id=project_id,
        traces_by_quantity_id=traces,
    )
    verify_sealed_customer_output(sealed, rows)
    return rows


__all__ = [
    "LIVE_FLOOR_AREA_CUSTOMER_PROJECTION_SCHEMA_VERSION",
    "project_live_floor_area_customer_rows",
]
