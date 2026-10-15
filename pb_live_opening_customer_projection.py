"""Fail-closed live opening QuantityEvidence -> customer draft projection.

Only opening quantities that satisfy the same source-owned trace requirements as
source-closed sealing may enter this bridge. It creates no geometry, identities,
counts, measurements, or estimator approval.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

from pb_customer_output_verification import verify_sealed_customer_output

from pb_live_opening_area_quantity_publication import _opening_quantity
from pb_live_opening_count_source_closed_export import (
    build_live_opening_count_source_traces,
)
from pb_live_opening_source_closed_export import (
    build_live_opening_area_claim_source_traces,
)
from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
from pb_migration_contracts import QuantityEvidence
from pb_source_closed_run_export import seal_source_closed_run
from pb_quantity_takeoff_adapter import (
    CommercialMeasurementAuthority,
    quantities_to_takeoff_output_rows,
)


LIVE_OPENING_CUSTOMER_PROJECTION_SCHEMA_VERSION = "1.0.0"


def _clean(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _authentic_positive_quantity_value(value: object, *, integer: bool = False) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        measured = float(value)
    except (TypeError, ValueError, OverflowError):
        return False
    return (math.isfinite(measured) and measured > 0.0
            and (not integer or measured.is_integer()))


def _eligible_area_quantities(
    claim: LivePhysicalNetWallClaim,
) -> tuple[QuantityEvidence, ...]:
    return tuple(
        quantity
        for quantity in claim.opening_quantity_evidence
        if isinstance(quantity, QuantityEvidence)
        and quantity.family == "opening_area"
        and not quantity.abstained
        and quantity.status == "corroborated"
        and quantity.unit in {"m2", "m²"}
        and _authentic_positive_quantity_value(quantity.value)
        and not quantity.blocking_reasons
        and isinstance(quantity.metadata, Mapping)
        and quantity.metadata.get("commercial_projection_allowed") is True
    )


def _eligible_count_quantities(
    claim: LivePhysicalNetWallClaim,
) -> tuple[QuantityEvidence, ...]:
    quantities: list[QuantityEvidence] = []
    for quantity in claim.opening_count_quantity_evidence:
        if not isinstance(quantity, QuantityEvidence):
            continue
        metadata = quantity.metadata if isinstance(quantity.metadata, Mapping) else {}
        if (
            quantity.family != "opening_count"
            or quantity.abstained
            or not _authentic_positive_quantity_value(quantity.value, integer=True)
            or quantity.status != "firm"
            or quantity.unit != "ea"
            or quantity.blocking_reasons
            or metadata.get("schedule_corroborated") is not True
            or metadata.get("commercial_projection_allowed") is not True
            or not _clean(metadata.get("opening_mark"))
        ):
            continue
        quantities.append(quantity)
    return tuple(quantities)


def project_live_opening_customer_rows(
    claim: LivePhysicalNetWallClaim,
    *,
    workspace_id: int,
    project_id: str,
) -> tuple[dict[str, Any], ...]:
    """Project all currently sealable opening quantities to AI-review rows."""
    if type(claim) is not LivePhysicalNetWallClaim:
        raise TypeError("claim must be LivePhysicalNetWallClaim")
    if type(workspace_id) is not int or workspace_id <= 0:
        raise ValueError("workspace_id must be an authenticated positive integer")

    # Validate every ORIGINAL area and count source record before eligibility
    # selection. An invalid object, wrong-family record or duplicate source ID
    # must not disappear merely because it was provisional or ABSTAINED.
    # These producer-owned inventories are family-typed; a customer adapter
    # never migrates a misplaced area record into a count or vice versa.
    source_ids: set[str] = set()
    for inventory, family in (
        (claim.opening_quantity_evidence, "opening_area"),
        (claim.opening_count_quantity_evidence, "opening_count"),
    ):
        for original in inventory:
            if not isinstance(original, QuantityEvidence):
                raise TypeError(
                    "opening customer source inventory must contain QuantityEvidence"
                )
            if original.family != family:
                raise ValueError(
                    "opening customer source inventory contains a foreign quantity family"
                )
            original_id = original.quantity_id
            if (
                type(original_id) is not str
                or not original_id
                or original_id != original_id.strip()
                or original_id in source_ids
            ):
                raise ValueError(
                    "opening customer quantity identities collide before commercial filtering"
                )
            source_ids.add(original_id)

    area_quantities = _eligible_area_quantities(claim)
    count_quantities = _eligible_count_quantities(claim)
    if not area_quantities and not count_quantities:
        return ()

    # Verify the actual canonical source producer's area, not merely a copied
    # quantity ID or evidence list. A changed m² value cannot inherit a seal.
    physical_by_id = {}
    for opening in claim.canonical_openings:
        oid = opening.canonical_opening_id
        if type(oid) is not str or not oid or oid != oid.strip() or oid in physical_by_id:
            raise ValueError("opening customer physical source identities are ambiguous")
        physical_by_id[oid] = opening
    for quantity in area_quantities:
        if (
            not isinstance(quantity.input_entity_ids, (tuple, list))
            or len(quantity.input_entity_ids) != 1
            or type(quantity.input_entity_ids[0]) is not str
        ):
            raise ValueError("opening customer area physical source identity is missing")
        original_source = physical_by_id.get(quantity.input_entity_ids[0])
        original = _opening_quantity(original_source) if original_source is not None else None
        if original is None or original.to_dict() != quantity.to_dict():
            raise ValueError("opening customer area claim differs from physical source producer")
    quantities = (*area_quantities, *count_quantities)
    ids = tuple(q.quantity_id for q in quantities)
    if (
        any(type(i) is not str or not i or i != i.strip() for i in ids)
        or len(set(ids)) != len(ids)
    ):
        raise ValueError("opening customer quantity identities collide across source claims")

    traces = {}
    if area_quantities:
        area_traces = build_live_opening_area_claim_source_traces(
            claim,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        traces.update(
            (quantity.quantity_id, area_traces[quantity.quantity_id])
            for quantity in area_quantities
        )
    if count_quantities:
        count_traces = build_live_opening_count_source_traces(
            claim,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        traces.update(
            (quantity.quantity_id, count_traces[quantity.quantity_id])
            for quantity in count_quantities
        )

    authorities = {}
    for quantity in quantities:
        metadata = quantity.metadata if isinstance(quantity.metadata, Mapping) else {}
        basis = _clean(metadata.get("area_basis")).lower()
        measurement_record_id = _clean(metadata.get("measurement_record_id"))
        if (
            quantity.family == "opening_area"
            and basis == "figured_opening_label"
            and measurement_record_id
        ):
            authority = CommercialMeasurementAuthority(
                method="figured_dimension",
                figured_dimension_ids=(measurement_record_id,),
                metadata={
                    "source": "live_opening_customer_projection",
                    "quantity_id": quantity.quantity_id,
                    "area_basis": basis,
                },
            )
        else:
            authority = CommercialMeasurementAuthority(
                method="direct_evidence",
                metadata={
                    "source": "live_opening_customer_projection",
                    "quantity_id": quantity.quantity_id,
                    "area_basis": basis or None,
                },
            )
        authorities[quantity.quantity_id] = authority
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
    "LIVE_OPENING_CUSTOMER_PROJECTION_SCHEMA_VERSION",
    "project_live_opening_customer_rows",
]
