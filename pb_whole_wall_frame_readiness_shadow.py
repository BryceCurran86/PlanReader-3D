"""Mission item 3 — whole-wall frame consumption readiness (shadow).

Requires authenticated host binding + complete frame record. Aligned-fragment
unproven reasons keep the opening in review; never proximity-complete a wall.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def assess_whole_wall_frame_readiness_shadow(
    *,
    physical_opening_id: str,
    host_record_id: str | None,
    frame_record_id: str | None,
    frame_reason_codes: Sequence[str] = (),
) -> dict[str, Any]:
    oid = str(physical_opening_id or "").strip()
    if not oid:
        raise ValueError("physical opening identity required")
    reasons = tuple(str(r) for r in frame_reason_codes)
    if not str(host_record_id or "").strip():
        gate = "structural_host_unavailable"
    elif any("aligned_fragment_distinctness_unproven" in r for r in reasons):
        gate = "whole_wall_frame_aligned_fragment_distinctness_unproven"
    elif any("unproven_wall_pair" in r for r in reasons):
        gate = "whole_wall_frame_unproven_wall_pair"
    elif not str(frame_record_id or "").strip():
        gate = "whole_wall_frame_unavailable"
    else:
        gate = "whole_wall_frame_consumption_review_only"
    return {
        "physical_opening_id": oid,
        "first_remaining_gate": gate,
        "frame_reason_codes": list(reasons),
        "proximity_completion_used": False,
        "measurement_published": False,
        "shadow_only": True,
    }
