"""Mission item 12 — door height owner gate (never invents a second axis).

Typical / assumed / default heights (including 2100 mm) are not evidence.
Only an owned figured height atom or USER_APPROVED height may clear the gate
into review; this module never publishes measurement.
"""
from __future__ import annotations

from typing import Any, Sequence

# Explicit denylist for convention values Cursor must never invent as height.
_FORBIDDEN_INVENTED_HEIGHT_MM = frozenset({2100.0, 2040.0, 1980.0, 2400.0})


def assess_door_height_owner_gate_shadow(
    *,
    physical_opening_id: str,
    owned_height_evidence_ids: Sequence[str] = (),
    owned_height_mm: float | None = None,
    user_approved_height: bool = False,
    label_width_only_mm: float | None = None,
) -> dict[str, Any]:
    oid = str(physical_opening_id or "").strip()
    if not oid:
        raise ValueError("physical opening identity required")
    height_ids = tuple(str(e).strip() for e in owned_height_evidence_ids if str(e).strip())
    height = None
    if owned_height_mm is not None:
        try:
            height = float(owned_height_mm)
        except (TypeError, ValueError):
            raise ValueError("owned_height_mm must be numeric when provided") from None
        if height != height or height <= 0:  # NaN / non-positive
            raise ValueError("owned_height_mm must be a positive finite value")
    # Owner approval or owned figured atom may enter review; bare convention
    # numerics (including common door heights) never clear the gate alone.
    if user_approved_height and height is not None:
        gate = "door_height_user_approved_review_only"
        height_for_report = height
        used_convention = False
    elif height_ids and height is not None:
        gate = "door_height_owned_figured_review_only"
        height_for_report = height
        used_convention = False
    elif height_ids and height is None:
        gate = "door_height_evidence_without_resolved_value"
        height_for_report = None
        used_convention = False
    elif height is not None and not height_ids:
        gate = "door_height_unproven_no_owned_atom"
        height_for_report = None
        used_convention = height in _FORBIDDEN_INVENTED_HEIGHT_MM
    else:
        gate = "door_height_second_axis_unavailable"
        height_for_report = None
        used_convention = False
    return {
        "physical_opening_id": oid,
        "first_remaining_gate": gate,
        "owned_height_evidence_ids": list(height_ids),
        "owned_height_mm": height_for_report,
        "label_width_only_mm": (
            float(label_width_only_mm) if label_width_only_mm is not None else None
        ),
        "user_approved_height": bool(user_approved_height),
        "invented_second_axis_mm": None,
        "used_typical_door_height_convention": used_convention,
        "measurement_published": False,
        "shadow_only": True,
    }
