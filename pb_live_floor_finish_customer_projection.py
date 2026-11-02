"""Fail-closed final floor-finish QuantityEvidence -> customer projection."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from pb_customer_output_verification import verify_sealed_customer_output
from pb_geometry_takeoff_model import MeasurementAuthorityType

from pb_live_floor_finish_area_source_closed_export import (
    build_live_floor_finish_area_source_traces,
)
from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
from pb_migration_contracts import QuantityEvidence
from pb_source_closed_run_export import SourceClosedRunConflictError, seal_source_closed_run
from pb_quantity_takeoff_adapter import (
    CommercialMeasurementAuthority,
    MissingCommercialAuthorityError,
    quantities_to_takeoff_output_rows,
)


LIVE_FLOOR_FINISH_CUSTOMER_PROJECTION_SCHEMA_VERSION = "1.0.0"


def _clean(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _source_finish_element(metadata: Mapping[str, Any]) -> str:
    """Show the exact plan code without altering the signed material family.

    The signed semantic key authenticates code + family. Keep finish_system
    equal to that family's source semantic for the GPT3 material verifier,
    while making distinct scheduled FT codes visible in the customer element.
    """
    code = metadata.get("finish_code")
    family = metadata.get("semantic_finish")
    if any(
        type(value) is not str or not value or value != value.strip()
        for value in (code, family)
    ):
        raise MissingCommercialAuthorityError(
            "floor-finish customer element requires an exact source finish code"
        )
    return f"Floor finish area ({code})"


def _source_owned_customer_location(
    claim: LivePhysicalNetWallClaim,
    floor: Any,
    quantity_metadata: Mapping[str, Any],
) -> str:
    """Use a native room label only when one original room owns that label.

    The canonical room-face/geometry authority is independently rechecked
    by build_live_floor_finish_area_source_traces before this presentation
    step. Never project a finish into an unrelated identically named room.
    Missing/ambiguous label evidence retains the exact canonical room ID.
    """
    fallback = _clean(floor.room_entity_id)
    owners = [
        room for room in claim.canonical_rooms
        if getattr(room, "canonical_room_id", None) == floor.room_entity_id
    ]
    if len(owners) != 1:
        return fallback
    room = owners[0]
    source_label = getattr(room, "room_label", None)
    binding_id = getattr(room, "room_label_binding_record_id", None)
    receipts = getattr(room, "room_label_evidence_ids", None)
    if (
        type(source_label) is not str or not source_label
        or source_label != source_label.strip()
        or type(binding_id) is not str or not binding_id
        or binding_id != binding_id.strip()
        or type(receipts) not in (tuple, list) or not receipts
        or any(
            type(evidence_id) is not str or not evidence_id
            or evidence_id != evidence_id.strip()
            for evidence_id in receipts
        )
        or len(set(receipts)) != len(receipts)
    ):
        return fallback
    normalized = " ".join(source_label.casefold().split())
    if any(
        other is not room
        and isinstance(getattr(other, "room_label", None), str)
        and " ".join(other.room_label.casefold().split()) == normalized
        for other in claim.canonical_rooms
    ):
        # A repeated OFFICE/STORE label without a unique source room identity
        # is unsuitable as a standalone customer location.
        return fallback
    observed = quantity_metadata.get("room_label")
    if observed is not None and (
        type(observed) is not str
        or " ".join(observed.casefold().split()) != normalized
    ):
        raise SourceClosedRunConflictError(
            "floor-finish material room label contradicts authenticated physical room"
        )
    return source_label


def _measurement_authority(quantity: QuantityEvidence) -> CommercialMeasurementAuthority:
    metadata = quantity.metadata if isinstance(quantity.metadata, Mapping) else {}
    # A source-authenticated figured floor area requires two distinct native
    # dimension witnesses. Never reclassify a missing or malformed figured
    # system as generic direct evidence during final customer publication.
    if quantity.authority == MeasurementAuthorityType.DOCUMENTED_DIMENSION.value:
        raw = metadata.get("figured_dimension_ids")
        if (
            not isinstance(raw, (tuple, list))
            or len(raw) != 2
            or any(
                type(value) is not str or not value or value != value.strip()
                for value in raw
            )
            or len(set(raw)) != 2
        ):
            raise MissingCommercialAuthorityError(
                "floor-finish figured measurement requires two distinct source dimensions"
            )
        return CommercialMeasurementAuthority(
            method="figured_dimension",
            figured_dimension_ids=tuple(sorted(raw)),
            metadata={
                "source": "live_floor_finish_customer_projection",
                "quantity_id": quantity.quantity_id,
                "finish_code": metadata.get("finish_code"),
                "semantic_finish": metadata.get("semantic_finish"),
            },
        )
    if quantity.authority == MeasurementAuthorityType.PDF_SCALED.value:
        scale_id = metadata.get("resolved_scale_id")
        scale_status = metadata.get("scale_status")
        raw_conflicts = metadata.get("scale_conflicts")
        if (
            type(scale_id) is not str or not scale_id
            or scale_id != scale_id.strip()
            or type(scale_status) is not str
            or scale_status not in ("resolved", "verified")
            or type(raw_conflicts) not in (tuple, list)
            or raw_conflicts
        ):
            # Never rewrite foreign, ambiguous or coerced source scale
            # conflicts into a publishable physical floor-finish area.
            raise MissingCommercialAuthorityError(
                "floor-finish scaled measurement requires original resolved physical scale without conflict"
            )
        return CommercialMeasurementAuthority(
            method="scaled_geometry",
            resolved_scale_id=scale_id,
            scale_status=scale_status,
            scale_conflicts=(),
        )
    raise MissingCommercialAuthorityError(
        "floor-finish measurement is not source-authenticated"
    )


def project_live_floor_finish_customer_rows(
    claim: LivePhysicalNetWallClaim,
    *,
    workspace_id: int,
    project_id: str,
) -> tuple[dict[str, Any], ...]:
    """Project every final sealable floor-finish quantity to one AI-review row."""
    if type(claim) is not LivePhysicalNetWallClaim:
        raise TypeError("claim must be LivePhysicalNetWallClaim")
    if type(workspace_id) is not int or workspace_id <= 0:
        raise ValueError("workspace_id must be an authenticated positive integer")

    # Inspect the ENTIRE original source inventory before customer selection.
    # A duplicate or foreign record must not vanish merely because every
    # competing source quantity is ABSTAINED or otherwise nonpublishable.
    # The source-closed trace builder enforces the same original-ID contract
    # for positive rows; that builder is not called on an empty projection.
    original_quantity_ids: set[str] = set()
    for original in claim.floor_finish_quantity_evidence:
        if not isinstance(original, QuantityEvidence):
            raise TypeError("floor_finish_quantity_evidence must contain QuantityEvidence")
        if original.family != "floor_finish_area":
            raise SourceClosedRunConflictError(
                "floor finish customer inventory contains a non-floor-finish quantity"
            )
        source_id = original.quantity_id
        if type(source_id) is not str or not source_id or source_id != source_id.strip():
            raise SourceClosedRunConflictError(
                "invalid original floor-finish quantity id in customer projection"
            )
        if source_id in original_quantity_ids:
            raise SourceClosedRunConflictError(
                f"duplicate original floor-finish quantity id in customer projection: {source_id}"
            )
        original_quantity_ids.add(source_id)
        # A numeric original quantity retaining unresolved producer blockers
        # must never disappear from customer output via the later selection
        # filter. The real source-closed sealer still receives this member;
        # returning zero/fewer customer rows would violate whole-inventory
        # completeness even if another independent FIRM member is valid.
        if not original.abstained and original.value is not None and original.blocking_reasons:
            raise SourceClosedRunConflictError(
                "numeric floor-finish source quantity retains unresolved blockers: "
                f"{source_id}"
            )

    quantities = tuple(
        quantity
        for quantity in claim.floor_finish_quantity_evidence
        if (
            isinstance(quantity, QuantityEvidence)
            and quantity.family == "floor_finish_area"
            and not quantity.abstained
            and quantity.value is not None
            and not quantity.blocking_reasons
        )
    )
    if not quantities:
        return ()

    traces = build_live_floor_finish_area_source_traces(
        claim,
        workspace_id=workspace_id,
        project_id=project_id,
    )
    # Source-closed finish QuantityEvidence owns the canonical floor ID.
    # Physical floor IDs can differ; resolving them here silently drops
    # otherwise authenticated finish rows even though sealing uses canonical.
    floors = {}
    for floor in claim.canonical_floors:
        canonical_id = _clean(floor.canonical_floor_id)
        if not canonical_id:
            continue
        if canonical_id in floors:
            # The upstream source trace builder rejects duplicates too,
            # but never silently pick a last-writer-wins customer location.
            raise ValueError("duplicate canonical floor identity in finish projection")
        floors[canonical_id] = floor
    projected_quantities: list[QuantityEvidence] = []
    authorities: dict[str, CommercialMeasurementAuthority] = {}
    for quantity in quantities:
        if len(quantity.input_entity_ids) != 1:
            continue
        floor = floors.get(_clean(quantity.input_entity_ids[0]))
        if floor is None:
            continue
        metadata = (
            dict(quantity.metadata)
            if isinstance(quantity.metadata, Mapping)
            else {}
        )
        metadata.update(
            {
                "section": "Internal",
                "element": _source_finish_element(metadata),
                "location": _source_owned_customer_location(
                    claim, floor, metadata,
                ),
                "substrate": "Floor",
                "finish_system": _clean(metadata.get("semantic_finish")),
                "inclusion_status": "INCLUSION",
                "row_role": "floor_area",
                "commercial_projection_allowed": True,
            }
        )
        customer_quantity = replace(quantity, metadata=metadata)
        projected_quantities.append(customer_quantity)
        authorities[quantity.quantity_id] = _measurement_authority(
            customer_quantity
        )
    rows = tuple(
        quantities_to_takeoff_output_rows(
            tuple(projected_quantities),
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
    "LIVE_FLOOR_FINISH_CUSTOMER_PROJECTION_SCHEMA_VERSION",
    "project_live_floor_finish_customer_rows",
]
