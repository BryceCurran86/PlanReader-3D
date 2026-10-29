"""Fail-closed canonical floor-area -> customer draft projection.

Consumes only final floor_area QuantityEvidence already published on physical
canonical floor identity plus the exact source-closed floor trace. It does not
measure rooms/floors, infer scale, create identity, or grant estimator approval.
"""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
from typing import Any

from pb_customer_output_verification import verify_sealed_customer_output
from pb_geometry_takeoff_model import MeasurementAuthorityType

from pb_live_floor_area_quantity_publication import (
    publish_live_floor_area_quantities,
)
from pb_live_floor_area_source_closed_export import (
    build_live_floor_area_source_traces,
)
from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
from pb_migration_contracts import QuantityEvidence, canonical_contract_json, stable_contract_id
from pb_room_area_quantity import _canonical_ring
from pb_source_closed_run_export import SourceClosedRunConflictError, seal_source_closed_run
from pb_quantity_takeoff_adapter import (
    CommercialMeasurementAuthority,
    quantities_to_takeoff_output_rows,
)


LIVE_FLOOR_AREA_CUSTOMER_PROJECTION_SCHEMA_VERSION = "1.0.0"


def _clean(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _measurement_authority(
    quantity: QuantityEvidence,
) -> CommercialMeasurementAuthority | None:
    metadata = quantity.metadata if isinstance(quantity.metadata, Mapping) else {}
    # This is the final commercial measurement-method authority boundary.
    # The original room-area producer has only two permitted source methods;
    # never turn a padded, imported, or substring-matching method token into
    # a source-authenticated customer measurement.
    authority = quantity.authority
    if type(authority) is not str:
        return None

    if authority == MeasurementAuthorityType.DOCUMENTED_DIMENSION.value:
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

    if authority == MeasurementAuthorityType.PDF_SCALED.value:
        scale_id = metadata.get("resolved_scale_id")
        scale_status = metadata.get("scale_status")
        raw_conflicts = metadata.get("scale_conflicts", ())
        # Optional original calibration lineage must remain literal; do not
        # clean a padded/imported source fingerprint into customer metadata.
        scale_fingerprint = metadata.get("scale_fingerprint")
        if scale_fingerprint is not None and (
            type(scale_fingerprint) is not str
            or not scale_fingerprint
            or scale_fingerprint != scale_fingerprint.strip()
        ):
            return None
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
                "scale_fingerprint": scale_fingerprint or "",
            },
        )

    return None



def _require_original_scaled_room_area_identity(
    claim: LivePhysicalNetWallClaim,
    quantity: QuantityEvidence,
) -> None:
    """Negative-only source-ID reproof; never issues geometry or a scale.

    The original PDF-scaled room-area producer binds its calibration
    fingerprint AND canonical original PDF ring into the source quantity ID.
    A floor publisher's copied metadata is not independent proof of either.
    """
    if quantity.authority != MeasurementAuthorityType.PDF_SCALED.value:
        return
    metadata = quantity.metadata if isinstance(quantity.metadata, Mapping) else {}
    source_id = metadata.get("upstream_room_area_quantity_id")
    room_id = metadata.get("room_entity_id")
    originals = tuple(
        source for source in claim.room_area_quantity_evidence
        if type(source) is QuantityEvidence and source.quantity_id == source_id
    )
    rooms = tuple(
        room for room in claim.canonical_rooms
        if room.canonical_room_id == room_id
    )
    if (
        type(source_id) is not str or not source_id
        or len(originals) != 1 or len(rooms) != 1
    ):
        raise SourceClosedRunConflictError(
            "scaled floor original source/room identity missing or ambiguous"
        )
    source = originals[0]
    room = rooms[0]
    original = source.metadata if isinstance(source.metadata, Mapping) else {}
    fingerprint = original.get("scale_fingerprint")
    source_sha = original.get("source_sha256")
    revision = original.get("revision_id")
    viewport = original.get("viewport_id")
    if (
        source.authority != MeasurementAuthorityType.PDF_SCALED.value
        or type(fingerprint) is not str or not fingerprint
        or fingerprint != fingerprint.strip()
        or type(metadata.get("scale_fingerprint")) is not str
        or metadata["scale_fingerprint"] != fingerprint
        or type(source_sha) is not str or not source_sha
        or type(revision) is not str or not revision
        or type(viewport) is not str or not viewport
        or type(source.value) not in (int, float)
        or len(source.input_entity_ids) != 1
        or type(source.input_entity_ids[0]) is not str
        or not source.input_entity_ids[0]
        or room.source_sha256 != source_sha
        or room.revision_id != revision
        or room.viewport_id != viewport
    ):
        raise SourceClosedRunConflictError(
            "scaled floor original calibration/source metadata mismatch"
        )

    ring = _canonical_ring(room.polygon_pdf_pts)
    ring_signature = hashlib.sha256(
        canonical_contract_json(ring).encode("utf-8")
    ).hexdigest()
    if not ring or original.get("ring_signature") != ring_signature:
        raise SourceClosedRunConflictError(
            "scaled floor original room-ring receipt mismatch"
        )
    # Exactly the stable payload of pb_room_area_quantity.build_room_area_quantity
    # for PDF_SCALED, using the ORIGINAL room receipt and independently
    # source-owned canonical room polygon, never the customer's copied ID.
    expected = stable_contract_id("qty", {
        "family": "room_area",
        "room_id": source.input_entity_ids[0],
        "value_m2": source.value,
        "scale_fingerprint": fingerprint,
        "ring": ring,
        "source_sha256": source_sha,
        "revision_id": revision,
        "viewport_id": viewport,
    })
    if source.quantity_id != expected:
        raise SourceClosedRunConflictError(
            "scaled floor original quantity ID does not bind calibration fingerprint"
        )


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
    # Reprove the producer's original scaled quantity identity before any
    # customer method can borrow the publisher's copied calibration label.
    for quantity in quantities:
        _require_original_scaled_room_area_identity(claim, quantity)
    authorities = {
        quantity.quantity_id: authority
        for quantity in quantities
        for authority in (_measurement_authority(quantity),)
        if authority is not None
    }

    # Missing measurement authority remains a hard adapter failure rather than
    # silently dropping an otherwise valid sealed floor quantity.
    rows = tuple(
        quantities_to_takeoff_output_rows(
            quantities,
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
