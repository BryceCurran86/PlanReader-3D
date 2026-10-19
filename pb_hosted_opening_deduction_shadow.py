"""Shadow: hosted-opening wall deductions require authenticated void+host (mission 18).

Geometric gap width alone is never deduction authority (AGENTS.md).
"""
from __future__ import annotations

from typing import Any


def assess_hosted_opening_deduction_shadow(
    *,
    wall_id: str,
    opening_id: str,
    host_binding_record_id: str | None,
    void_record_id: str | None,
    opening_area_m2: float | None,
    opening_area_authority: str | None,
) -> dict[str, Any]:
    wid = str(wall_id or "").strip()
    oid = str(opening_id or "").strip()
    if not wid or not oid:
        raise ValueError("wall and opening identities required")
    host_ok = bool(str(host_binding_record_id or "").strip())
    void_ok = bool(str(void_record_id or "").strip())
    area_ok = (
        type(opening_area_m2) in (float, int)
        and float(opening_area_m2) > 0
        and str(opening_area_authority or "").strip().lower() in {"firm", "corroborated"}
    )
    if not host_ok:
        gate = "deduction_host_binding_unproven"
    elif not void_ok:
        gate = "deduction_opening_void_unproven"
    elif not area_ok:
        gate = "deduction_opening_area_unproven"
    else:
        gate = "hosted_opening_deduction_review_only"
    return {
        "wall_id": wid,
        "opening_id": oid,
        "first_remaining_gate": gate,
        "deduction_authority_granted": False,
        "gap_width_used_as_authority": False,
        "measurement_published": False,
        "shadow_only": True,
    }
