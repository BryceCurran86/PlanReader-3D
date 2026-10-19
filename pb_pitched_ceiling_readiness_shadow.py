"""Mission item 20 — pitched/raked ceiling fail-closed without proven pitch.

Plan area alone never becomes a pitched surface quantity.
"""
from __future__ import annotations

import math
from typing import Any


def _positive(value: object) -> bool:
    return type(value) in (float, int) and math.isfinite(float(value)) and float(value) > 0


def assess_pitched_ceiling_readiness_shadow(
    *,
    room_or_plane_id: str,
    plan_area_m2: float | None,
    plan_area_authority: str | None,
    pitch_ratio_or_degrees: float | None,
    pitch_authority: str | None,
) -> dict[str, Any]:
    rid = str(room_or_plane_id or "").strip()
    if not rid:
        raise ValueError("room or plane identity required")
    plan_ok = _positive(plan_area_m2) and str(plan_area_authority or "").strip().lower() in {
        "firm", "corroborated"
    }
    pitch_ok = _positive(pitch_ratio_or_degrees) and str(pitch_authority or "").strip().lower() in {
        "firm", "corroborated"
    }
    if not plan_ok:
        gate = "ceiling_plan_area_authority_unproven"
        surface = None
    elif not pitch_ok:
        gate = "ceiling_pitch_authority_unproven"
        surface = None
    else:
        gate = "pitched_ceiling_surface_review_only"
        # Review-only geometric factor; not a published quantity.
        pitch = float(pitch_ratio_or_degrees)
        # Interpret small values as rise/run ratio, larger as degrees.
        if pitch <= 1.0:
            factor = math.sqrt(1.0 + pitch * pitch)
        else:
            factor = 1.0 / math.cos(math.radians(pitch))
        surface = float(plan_area_m2) * factor
    return {
        "room_or_plane_id": rid,
        "first_remaining_gate": gate,
        "plan_area_used_as_pitched_surface": False,
        "surface_area_m2_review_only": surface,
        "measurement_published": False,
        "customer_seal_granted": False,
        "shadow_only": True,
    }
