"""Shadow: width/height axis ownership without inventing the missing axis.

Mission items 10–12 (Cursor batch). Reuses figured-pair evidence only.
A single authenticated length is never promoted to an opening area. Axis order
must be source-owned; product equality alone does not assign width vs height.
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence


def _positive(value: object) -> bool:
    return type(value) in (float, int) and math.isfinite(float(value)) and float(value) > 0


def assess_opening_axis_ownership_shadow(
    *,
    physical_opening_id: str,
    dimension_values_mm: Sequence[float] | None,
    axis_order_resolved: bool,
    width_record_id: str | None,
    height_record_id: str | None,
    width_m: float | None,
    height_m: float | None,
    area_m2: float | None,
    canonical_evidence_ids: Sequence[str] | None = None,
    geometry_complete: bool | None = None,
) -> dict[str, Any]:
    """Classify axis/area readiness; never invent height from width."""
    oid = str(physical_opening_id or "").strip()
    if not oid:
        raise ValueError("physical opening identity required")

    values = tuple(dimension_values_mm or ())
    if len(values) == 0:
        gate = "source_figured_dimension_pair_unproven"
    elif len(values) == 1:
        gate = "single_figured_dimension_second_axis_unproven"
    elif len(values) != 2 or not all(_positive(v) for v in values):
        gate = "source_figured_dimension_pair_unproven"
    elif area_m2 is not None and _positive(area_m2):
        a, b = float(values[0]), float(values[1])
        if not math.isclose(a * b / 1_000_000.0, float(area_m2), rel_tol=1e-9):
            gate = "figured_area_product_disagrees_with_pair"
        elif (
            type(width_record_id) is not str or not width_record_id
            or width_record_id != width_record_id.strip()
            or type(height_record_id) is not str or not height_record_id
            or height_record_id != height_record_id.strip()
            or width_record_id == height_record_id
            or not (_positive(width_m) and _positive(height_m))
        ):
            gate = "width_height_axis_authority_unproven"
        elif geometry_complete is not True:
            gate = "opening_geometry_axis_scope_unavailable"
        elif (
            type(canonical_evidence_ids) not in (tuple, list)
            or width_record_id not in canonical_evidence_ids
            or height_record_id not in canonical_evidence_ids
        ):
            gate = "original_axis_receipts_unbound"
        # Source-owned independently ordered canonical axes can corroborate an
        # UNORDERED printed pair, but the actual dimension values must match.
        # Equal areas from different axis pairs are never identity evidence.
        elif not all(math.isclose(c, d, rel_tol=1e-8, abs_tol=1e-9)
                     for c, d in zip(
                         sorted((float(width_m), float(height_m))),
                         sorted((a / 1000.0, b / 1000.0)))):
            gate = "independent_axes_disagree_with_figured_pair"
        elif not math.isclose(float(width_m) * float(height_m), float(area_m2), rel_tol=1e-8):
            gate = "axis_ordered_area_disagrees_with_figured_product"
        else:
            gate = "independent_gpt1_measurement_validation_required"
    else:
        gate = "source_figured_dimension_pair_unproven"

    return {
        "physical_opening_id": oid,
        "first_remaining_gate": gate,
        "figured_value_count": len(values),
        "axis_order_authenticated": gate == "independent_gpt1_measurement_validation_required",
        "original_figured_label_order_source_resolved": axis_order_resolved is True,
        "opening_area_publication_allowed": False,
        "invented_second_axis": False,
        "measurement_published": False,
        "customer_seal_granted": False,
        "shadow_only": True,
    }


def refuse_area_from_width_only(
    *,
    physical_opening_id: str,
    width_mm: float | None,
    height_mm: float | None = None,
) -> dict[str, Any]:
    """Explicit negative: a lone width never yields door/window area."""
    if height_mm is not None and _positive(height_mm) and _positive(width_mm):
        values: Sequence[float] | None = (float(width_mm), float(height_mm))
        return assess_opening_axis_ownership_shadow(
            physical_opening_id=physical_opening_id,
            dimension_values_mm=values,
            axis_order_resolved=False,
            width_record_id=None,
            height_record_id=None,
            width_m=None,
            height_m=None,
            area_m2=(float(width_mm) * float(height_mm)) / 1_000_000.0,
        )
    return assess_opening_axis_ownership_shadow(
        physical_opening_id=physical_opening_id,
        dimension_values_mm=(float(width_mm),) if _positive(width_mm) else (),
        axis_order_resolved=False,
        width_record_id=None,
        height_record_id=None,
        width_m=None,
        height_m=None,
        area_m2=None,
    )
