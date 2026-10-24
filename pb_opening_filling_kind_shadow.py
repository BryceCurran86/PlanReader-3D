"""Shadow: door/window filling kind requires positive source evidence (mission 9).

A structural gap / host / frame never invents door vs window. Schedule marks and
labels may nominate; untyped openings abstain.
"""
from __future__ import annotations

from typing import Any


_ALLOWED = frozenset({"door", "window"})


def assess_opening_filling_kind_shadow(
    *,
    physical_opening_id: str,
    opening_kind: str | None,
    source_kind_evidence_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    oid = str(physical_opening_id or "").strip()
    if not oid:
        raise ValueError("physical opening identity required")
    kind = str(opening_kind or "").strip().lower()
    evidence = tuple(eid for eid in source_kind_evidence_ids if str(eid).strip())
    if kind not in _ALLOWED:
        gate = "opening_filling_kind_unproven"
        typed = False
    elif not evidence:
        # Kind token without owned evidence IDs is not source-closed.
        gate = "opening_filling_kind_evidence_unproven"
        typed = False
    else:
        gate = "opening_filling_kind_source_supported"
        typed = True
    return {
        "physical_opening_id": oid,
        "opening_kind": kind or None,
        "source_kind_evidence_ids": list(evidence),
        "filling_kind_source_supported": typed,
        "first_remaining_gate": gate,
        "host_granted": False,
        "frame_granted": False,
        "measurement_published": False,
        "shadow_only": True,
    }
