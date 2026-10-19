"""Mission item 10 — schedule/label/leader/witness binding shadow.

Binds printed marks and dimension witnesses to a physical opening only when
ownership evidence IDs are explicit. Proximity / first-bbox is refused.
"""
from __future__ import annotations

from typing import Any, Sequence


def _clean(value: object) -> str:
    return str(value or "").strip()


def bind_opening_label_leader_witness_shadow(
    *,
    physical_opening_id: str,
    printed_mark: str | None,
    schedule_row_id: str | None,
    leader_evidence_id: str | None,
    dimension_witness_ids: Sequence[str] = (),
    proximity_only: bool = False,
) -> dict[str, Any]:
    oid = _clean(physical_opening_id)
    if not oid:
        raise ValueError("physical opening identity required")
    if proximity_only:
        return {
            "physical_opening_id": oid,
            "first_remaining_gate": "proximity_only_label_binding_forbidden",
            "mark_bound": False,
            "schedule_bound": False,
            "leader_bound": False,
            "witness_bound": False,
            "measurement_published": False,
            "shadow_only": True,
        }
    mark = _clean(printed_mark)
    schedule = _clean(schedule_row_id)
    leader = _clean(leader_evidence_id)
    witnesses = tuple(_clean(w) for w in dimension_witness_ids if _clean(w))
    mark_bound = bool(mark) and bool(schedule or leader)
    schedule_bound = bool(schedule)
    leader_bound = bool(leader)
    witness_bound = len(witnesses) > 0
    if not mark and not schedule and not leader and not witnesses:
        gate = "opening_label_leader_witness_unavailable"
    elif mark and not (schedule or leader):
        gate = "printed_mark_without_owned_schedule_or_leader"
    elif witnesses and not (schedule or leader or mark):
        gate = "dimension_witness_without_opening_ownership"
    else:
        gate = "opening_label_leader_witness_review_only"
    return {
        "physical_opening_id": oid,
        "printed_mark": mark or None,
        "schedule_row_id": schedule or None,
        "leader_evidence_id": leader or None,
        "dimension_witness_ids": list(witnesses),
        "mark_bound": mark_bound,
        "schedule_bound": schedule_bound,
        "leader_bound": leader_bound,
        "witness_bound": witness_bound,
        "first_remaining_gate": gate,
        "measurement_published": False,
        "opening_kind_granted": False,
        "shadow_only": True,
    }
