"""Mission item 5 — STACKER / shared-image-frame host readiness (fail-closed).

A unique native image placement that covers both flanks and aperture proves
PIXEL registration only. It never supplies structural host, frame, kind,
count, or area. GPT MAX + owner PDF remain required for FIRM host identity.
"""
from __future__ import annotations

from typing import Any, Sequence


def assess_stacker_host_frame_readiness_shadow(
    *,
    physical_opening_id: str,
    unique_image_frame_present: bool = False,
    structural_host_wall_id: str | None = None,
    host_binding_evidence_ids: Sequence[str] = (),
    host_frame_evidence_ids: Sequence[str] = (),
    competing_host_wall_ids: Sequence[str] = (),
) -> dict[str, Any]:
    oid = str(physical_opening_id or "").strip()
    if not oid:
        raise ValueError("physical opening identity required")
    host = str(structural_host_wall_id or "").strip() or None
    bind = tuple(str(e).strip() for e in host_binding_evidence_ids if str(e).strip())
    frame = tuple(str(e).strip() for e in host_frame_evidence_ids if str(e).strip())
    competing = tuple(str(w).strip() for w in competing_host_wall_ids if str(w).strip())
    if competing and len(set(competing)) > 1:
        gate = "stacker_host_ambiguous_competing_walls"
    elif not host:
        gate = "stacker_structural_host_unproven"
    elif not bind:
        gate = "stacker_host_binding_evidence_missing"
    elif not frame:
        gate = "stacker_host_frame_evidence_missing"
    else:
        gate = "stacker_host_frame_review_only"
    return {
        "physical_opening_id": oid,
        "first_remaining_gate": gate,
        "unique_image_frame_present": bool(unique_image_frame_present),
        "image_frame_used_as_structural_host": False,
        "structural_host_wall_id": host,
        "host_binding_evidence_ids": list(bind),
        "host_frame_evidence_ids": list(frame),
        "competing_host_wall_ids": list(competing),
        "host_granted": False,
        "frame_granted": False,
        "measurement_published": False,
        "shadow_only": True,
    }
