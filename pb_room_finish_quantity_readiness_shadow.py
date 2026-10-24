"""Mission item 19 — floor/ceiling/tiling readiness without inventing finish.

Requires authenticated room face + finish definition + occurrence binding.
Plain floor area alone never matches a finish BOQ item.
"""
from __future__ import annotations

from typing import Any


def assess_room_finish_quantity_readiness_shadow(
    *,
    room_id: str,
    room_face_record_id: str | None,
    finish_definition_id: str | None,
    finish_occurrence_id: str | None,
    area_m2: float | None,
    area_authority: str | None,
) -> dict[str, Any]:
    rid = str(room_id or "").strip()
    if not rid:
        raise ValueError("room identity required")
    face = str(room_face_record_id or "").strip()
    finish_def = str(finish_definition_id or "").strip()
    occurrence = str(finish_occurrence_id or "").strip()
    area_ok = (
        type(area_m2) in (float, int)
        and float(area_m2) > 0
        and str(area_authority or "").strip().lower() in {"firm", "corroborated"}
    )
    if not face:
        gate = "source_room_face_unavailable"
    elif not finish_def:
        gate = "finish_definition_unavailable"
    elif not occurrence:
        gate = "finish_occurrence_unbound"
    elif not area_ok:
        gate = "finish_area_authority_unproven"
    else:
        gate = "room_finish_quantity_review_only"
    return {
        "room_id": rid,
        "first_remaining_gate": gate,
        "plain_floor_treated_as_finish": False,
        "measurement_published": False,
        "customer_seal_granted": False,
        "shadow_only": True,
    }
