"""Shadow: opening-count publication requires a proven complete universe (mission 14–15).

Incomplete, conflicting, or duplicate instance sets abstain. Never default count=1.
Physically distinct IDs are never merged because labels match.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence


def assess_opening_universe_completeness_shadow(
    *,
    instance_ids: Sequence[str],
    universe_complete: bool,
    conflicting_instance_ids: Sequence[str] = (),
) -> dict[str, Any]:
    cleaned = [str(i).strip() for i in instance_ids if str(i).strip()]
    counts = Counter(cleaned)
    duplicates = sorted(i for i, n in counts.items() if n > 1)
    conflicts = sorted({str(i).strip() for i in conflicting_instance_ids if str(i).strip()})
    if duplicates:
        gate = "opening_universe_duplicate_instance_ids"
        complete = False
    elif conflicts:
        gate = "opening_universe_conflicting_instance_ids"
        complete = False
    elif not universe_complete:
        gate = "opening_universe_incomplete"
        complete = False
    else:
        gate = "opening_universe_complete_review_only"
        complete = True
    return {
        "status": "UNPUBLISHED_OPENING_UNIVERSE_SHADOW",
        "first_remaining_gate": gate,
        "universe_complete": complete,
        "unique_instance_count": len(counts),
        "duplicate_instance_ids": duplicates,
        "conflicting_instance_ids": conflicts,
        "opening_count_granted": False,
        "measurement_published": False,
        "shadow_only": True,
    }


def refuse_merge_distinct_openings_by_label(
    *,
    openings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Retains every distinct physical ID even when printed labels collide."""
    by_label: dict[str, list[str]] = {}
    for row in openings:
        oid = str(row.get("physical_opening_id") or "").strip()
        label = str(row.get("printed_label") or "").strip()
        if not oid:
            raise ValueError("physical opening identity required")
        by_label.setdefault(label or f"__unlabelled__:{oid}", []).append(oid)
    collisions = {
        label: ids for label, ids in by_label.items()
        if label and not label.startswith("__unlabelled__:") and len(set(ids)) > 1
    }
    return {
        "status": "UNPUBLISHED_OPENING_LABEL_COLLISION_SHADOW",
        "label_collisions": {
            label: sorted(set(ids)) for label, ids in sorted(collisions.items())
        },
        "merged_physical_ids": [],
        "opening_count_granted": False,
        "shadow_only": True,
        "limitation": "Matching labels never prove SAME physical opening.",
    }
