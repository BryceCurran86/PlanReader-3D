"""Shadow: wall length/height/face area only via existing firm seams (mission 16–17).

Does not call commercial publishers. Refuses face area when height or length is
unauthenticated. Reuses authority vocabulary only — never invents 2.8 m defaults.
"""
from __future__ import annotations

import math
from typing import Any


def _positive(value: object) -> bool:
    return type(value) in (float, int) and math.isfinite(float(value)) and float(value) > 0


def assess_wall_length_height_face_shadow(
    *,
    wall_id: str,
    length_m: float | None,
    length_authority: str | None,
    height_m: float | None,
    height_authority: str | None,
) -> dict[str, Any]:
    wid = str(wall_id or "").strip()
    if not wid:
        raise ValueError("wall identity required")
    length_ok = _positive(length_m) and str(length_authority or "").strip().lower() in {
        "firm", "corroborated"
    }
    height_ok = _positive(height_m) and str(height_authority or "").strip().lower() in {
        "firm", "corroborated"
    }
    if not length_ok:
        gate = "wall_length_authority_unproven"
        face = None
    elif not height_ok:
        gate = "wall_height_authority_unproven"
        face = None
    else:
        gate = "wall_face_area_review_only"
        face = float(length_m) * float(height_m)
    return {
        "wall_id": wid,
        "first_remaining_gate": gate,
        "length_authenticated": length_ok,
        "height_authenticated": height_ok,
        "face_area_m2_review_only": face,
        "default_height_invented": False,
        "measurement_published": False,
        "customer_seal_granted": False,
        "shadow_only": True,
    }
