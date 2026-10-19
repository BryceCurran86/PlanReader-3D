"""Mission item 13 — window/glazed frame area readiness (review only).

Requires host + frame + kind=window + figured pair + axis ownership.
Never invents glass area from aperture geometry alone.
"""
from __future__ import annotations

import math
from typing import Any


def _positive(value: object) -> bool:
    return type(value) in (float, int) and math.isfinite(float(value)) and float(value) > 0


def assess_glazed_opening_frame_area_readiness_shadow(
    *,
    physical_opening_id: str,
    host_record_id: str | None,
    frame_record_id: str | None,
    opening_kind: str | None,
    figured_pair_mm: tuple[float, float] | None,
    axis_order_resolved: bool,
) -> dict[str, Any]:
    oid = str(physical_opening_id or "").strip()
    if not oid:
        raise ValueError("physical opening identity required")
    kind = str(opening_kind or "").strip().lower()
    if not str(host_record_id or "").strip():
        gate = "structural_host_unavailable"
    elif not str(frame_record_id or "").strip():
        gate = "whole_wall_frame_unavailable"
    elif kind != "window":
        gate = "opening_filling_kind_unproven"
    elif (
        figured_pair_mm is None
        or len(figured_pair_mm) != 2
        or not all(_positive(v) for v in figured_pair_mm)
    ):
        gate = "source_figured_dimension_pair_unproven"
    elif not axis_order_resolved:
        gate = "width_height_axis_authority_unproven"
    else:
        gate = "glazed_frame_area_review_only"
    return {
        "physical_opening_id": oid,
        "first_remaining_gate": gate,
        "aperture_geometry_used_as_area": False,
        "measurement_published": False,
        "customer_seal_granted": False,
        "shadow_only": True,
    }
