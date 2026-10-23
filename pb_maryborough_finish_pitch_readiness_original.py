"""Maryborough room-scope finish + pitched-ceiling readiness (fail-closed)."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pb_pitched_ceiling_readiness_shadow import assess_pitched_ceiling_readiness_shadow
from pb_room_finish_quantity_readiness_shadow import (
    assess_room_finish_quantity_readiness_shadow,
)


def attach_maryborough_finish_pitch_readiness(
    scope_first_failures: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    rows = []
    for scope in scope_first_failures:
        scope_id = str(scope.get("decision_scope_id") or "").strip()
        if not scope_id:
            raise ValueError("decision_scope_id required")
        # Original room gate does not yet publish finish/pitch atoms — fail closed.
        finish = assess_room_finish_quantity_readiness_shadow(
            room_id=scope_id,
            room_face_record_id=None,
            finish_definition_id=None,
            finish_occurrence_id=None,
            area_m2=None,
            area_authority=None,
        )
        pitch = assess_pitched_ceiling_readiness_shadow(
            room_or_plane_id=scope_id,
            plan_area_m2=None,
            plan_area_authority=None,
            pitch_ratio_or_degrees=None,
            pitch_authority=None,
        )
        rows.append({
            "decision_scope_id": scope_id,
            "room_first_unproved_authority": scope.get("first_unproved_authority"),
            "finish_gate": finish["first_remaining_gate"],
            "pitched_ceiling_gate": pitch["first_remaining_gate"],
            "plain_floor_treated_as_finish": False,
            "measurement_published": False,
        })
    return {
        "status": "UNPUBLISHED_MARYBOROUGH_FINISH_PITCH_READINESS",
        "scope_count": len(rows),
        "scopes": rows,
        "measurement_published": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }
