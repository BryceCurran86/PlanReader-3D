"""Read-only producer receipt ledger for named-room metric first failures.

This is a diagnostic adapter, not a scale, room-area, or QuantityEvidence
producer. Never infer a metric quantity from a missing first-failure receipt.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


def summarize_named_room_metric_first_gates(claim: Any) -> dict[str, Any]:
    """Report exact named source room ownership and existing measurement gates.

    Duplicate physical IDs, even with the same label, are not uniquely
    attributable. Their first-failure codes remain counted but cannot be
    assigned to a named room in the diagnostic output.
    """
    named = tuple(
        (str(getattr(room, "physical_room_id", "") or "").strip(),
         " ".join(str(getattr(room, "room_label", "") or "").upper().split()))
        for room in getattr(claim, "canonical_rooms", ()) or ()
        if str(getattr(room, "room_label", "") or "").strip()
    )
    counts = Counter(room_id for room_id, _ in named)
    owners = {room_id: label for room_id, label in named
              if room_id and counts[room_id] == 1}
    conflicts = sorted({room_id for room_id, _ in named
                        if not room_id or counts[room_id] != 1})

    kinds = (
        ("same_view", "same_view_room_area_first_failure_codes"),
        ("cross_view", "cross_view_room_area_first_failure_codes"),
        ("physical_scale", "physical_scale_first_failure_codes"),
    )
    ledger: dict[str, list[dict[str, Any]]] = {}
    total: dict[str, int] = {}
    for key, attr in kinds:
        codes = tuple(getattr(claim, attr, ()) or ())
        total[key] = len(codes)
        entries = []
        for source_room_id, reason in codes:
            room_id = str(source_room_id or "").strip()
            if room_id not in owners:
                continue
            detail = (
                {"first_gates": [str(code) for code in (reason or ())]}
                if key == "physical_scale"
                else {"first_gate": str(reason)}
            )
            entries.append({
                "physical_room_id": room_id,
                "label": owners[room_id],
                **detail,
            })
        ledger[key] = sorted(entries, key=lambda row: (
            row["label"], row["physical_room_id"],
            repr(row.get("first_gate", row.get("first_gates"))),
        ))
    return {
        "source_named_room_count": len(named),
        "uniquely_attributable_named_room_count": len(owners),
        "ambiguous_named_physical_room_ids": conflicts,
        "all_source_first_failure_receipt_counts": total,
        "named_room_metric_first_failure_codes": ledger,
        "metric_quantity_published": False,
    }
