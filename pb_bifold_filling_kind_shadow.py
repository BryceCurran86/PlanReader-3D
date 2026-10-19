"""Mission item 7 — BIFOLD / specialty filling kind from authentic plan evidence.

Manufacturer/energy/elevation text alone does not create a door filling when
the plan role is unresolved. Gap geometry never supplies kind.
"""
from __future__ import annotations

from typing import Any, Sequence


def assess_bifold_filling_kind_shadow(
    *,
    physical_opening_id: str,
    plan_filling_role_evidence_ids: Sequence[str] = (),
    manufacturer_or_elevation_evidence_ids: Sequence[str] = (),
    gap_geometry_present: bool = False,
) -> dict[str, Any]:
    oid = str(physical_opening_id or "").strip()
    if not oid:
        raise ValueError("physical opening identity required")
    plan = tuple(str(e).strip() for e in plan_filling_role_evidence_ids if str(e).strip())
    other = tuple(
        str(e).strip() for e in manufacturer_or_elevation_evidence_ids if str(e).strip()
    )
    if not plan:
        gate = "bifold_plan_filling_role_unproven"
    elif not other:
        # Plan role without independent type/model support stays review-only.
        gate = "bifold_type_identity_unproven"
    else:
        gate = "bifold_filling_kind_review_only"
    return {
        "physical_opening_id": oid,
        "first_remaining_gate": gate,
        "plan_filling_role_evidence_ids": list(plan),
        "manufacturer_or_elevation_evidence_ids": list(other),
        "gap_geometry_used_as_kind": False,
        "gap_geometry_present": bool(gap_geometry_present),
        "opening_kind_granted": False,
        "measurement_published": False,
        "shadow_only": True,
    }
