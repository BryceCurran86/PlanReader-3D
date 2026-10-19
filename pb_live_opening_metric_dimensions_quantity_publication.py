"""Original-source opening width and height quantity publication.

Only measured axes with their own original receipts or an explicitly FRAME
dimensioned schedule are emitted. A figured area product does NOT prove which
edge is width or height; it is never decomposed by assumption.
"""
from __future__ import annotations

import math

from pb_live_opening_area_quantity_publication import (
    publish_live_opening_area_quantities,
)
from pb_live_physical_opening_void_composition import (
    LivePhysicalOpeningVoidComposition, LiveCanonicalOpeningObject,
)
from pb_migration_contracts import QuantityEvidence, stable_contract_id


OPENING_SOURCE_DIMENSION_AUTHORITY = (
    "pb_live_opening_metric_dimensions_quantity_publication."
    "publish_live_opening_dimension_quantities"
)


def _positive_axis(value: object) -> float | None:
    if type(value) not in (int, float):
        return None
    try:
        axis = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return axis if math.isfinite(axis) and axis > 0.0 else None


def _measurement_axes(opening: LiveCanonicalOpeningObject):
    """Return axis m plus independent ORIGINAL source receipts, or abstain."""
    basis = opening.area_basis
    if basis == "authenticated_frame_schedule":
        if (
            opening.schedule_row_dimension_basis != "frame"
            or not opening.schedule_binding_record_id
            or opening.schedule_binding_record_id not in opening.evidence_ids
        ):
            return None
        wmm = _positive_axis(opening.schedule_declared_width_mm)
        hmm = _positive_axis(opening.schedule_declared_height_mm)
        if wmm is None or hmm is None:
            return None
        return (wmm / 1000.0, hmm / 1000.0,
                (opening.schedule_binding_record_id,))
    if basis not in {"resolved_opening_geometry", "figured_opening_label"}:
        return None
    if basis == "resolved_opening_geometry" and opening.geometry_complete is not True:
        return None
    width = _positive_axis(opening.width_m)
    height = _positive_axis(opening.height_m)
    originals = (opening.width_record_id, opening.height_record_id)
    if (
        width is None or height is None
        or any(type(receipt) is not str or not receipt
               or receipt != receipt.strip() or receipt not in opening.evidence_ids
               for receipt in originals)
        or originals[0] == originals[1]
    ):
        return None
    return width, height, originals


def publish_live_opening_dimension_quantities(
    composition: LivePhysicalOpeningVoidComposition,
) -> tuple[QuantityEvidence, ...]:
    """Publish metres ONLY where existing original signed area plus axes agree.

    Signed area identities are neither copied nor changed. Some openings have
    genuine figured m² but unresolved axis orientation; those yield zero width/
    height records. Other independently dimensioned openings can still emit.
    """
    if type(composition) is not LivePhysicalOpeningVoidComposition:
        raise TypeError("composition must be LivePhysicalOpeningVoidComposition")
    area_quantities = publish_live_opening_area_quantities(composition)
    area_by_opening = {
        q.input_entity_ids[0]: q for q in area_quantities
        if q.family == "opening_area" and len(q.input_entity_ids) == 1
    }
    output: list[QuantityEvidence] = []
    for opening in composition.canonical_openings:
        area = area_by_opening.get(opening.canonical_opening_id)
        if area is None or area.abstained or area.status != "corroborated":
            continue
        resolved = _measurement_axes(opening)
        if resolved is None:
            continue
        width, height, axis_receipts = resolved
        measured_area = _positive_axis(opening.area_m2)
        if (
            measured_area is None
            or not math.isfinite(width * height)
            or not math.isclose(
                measured_area, width * height,
                rel_tol=0.0,
                abs_tol=0.0050001 if opening.area_basis == "figured_opening_label"
                else 1e-6,
            )
        ):
            continue
        evidence_ids = tuple(sorted(set((*area.evidence_ids, *axis_receipts))))
        if len(evidence_ids) < len(axis_receipts):
            continue
        for axis_name, metres in (("width", width), ("height", height)):
            value = round(metres, 6)
            if value <= 0.0 or not math.isclose(value, metres, rel_tol=0, abs_tol=1e-6):
                continue
            record = QuantityEvidence(
                quantity_id=stable_contract_id("opening_metric_axis", {
                    "opening_area_quantity_id": area.quantity_id,
                    "physical_opening_id": opening.physical_opening_id,
                    "axis": axis_name,
                    "value_m": value,
                    "original_receipts": axis_receipts,
                }),
                family=f"opening_{axis_name}",
                semantic_key=f"opening_{axis_name}:{opening.physical_opening_id}",
                value=value,
                unit="lm",
                input_entity_ids=(opening.physical_opening_id,),
                formula=(
                    "original_schedule_outer_frame_dimension_mm / 1000"
                    if opening.area_basis == "authenticated_frame_schedule"
                    else f"original_source_owned_{axis_name}_metres"
                ),
                formula_version="1.0.0",
                evidence_ids=evidence_ids,
                authority=OPENING_SOURCE_DIMENSION_AUTHORITY,
                status="corroborated",
                confidence=1.0,
                abstained=False,
                blocking_reasons=(),
                reason_codes=("original_metric_opening_axis_resolved",),
                metadata={
                    "document_id": opening.document_id,
                    "revision_id": opening.revision_id,
                    "source_sha256": opening.source_sha256,
                    "snapshot_id": opening.snapshot_id,
                    "page_no": opening.page_id,
                    "viewport_id": opening.viewport_id,
                    "canonical_opening_id": opening.canonical_opening_id,
                    "physical_opening_id": opening.physical_opening_id,
                    "opening_kind": opening.opening_kind,
                    "host_wall_id": opening.host_wall_id,
                    "area_basis": opening.area_basis,
                    "source_area_quantity_id": area.quantity_id,
                    "source_axis_record_ids": axis_receipts,
                    "material_finish_authority": "unavailable",
                    "commercial_projection_allowed": False,
                    "do_not_infer_opening_count": True,
                },
            )
            output.append(record)
    return tuple(sorted(output, key=lambda q: q.quantity_id))


__all__ = [
    "OPENING_SOURCE_DIMENSION_AUTHORITY",
    "publish_live_opening_dimension_quantities",
]
