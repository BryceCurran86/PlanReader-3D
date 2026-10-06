from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from pb_source_floor_plan_page_scope import (
    FLOOR_PLAN,
    NOT_FLOOR_PLAN,
    source_floor_plan_topology_scope,
)


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"


def _quantity_row(q):
    return {
        "quantity_id": q.quantity_id,
        "entity_id": getattr(q, "entity_id", None),
        "value": q.value,
        "unit": q.unit,
        "authority": str(q.authority),
        "status": str(q.status),
        "reason_codes": list(q.reason_codes or ()),
        "metadata": dict(q.metadata or {}),
    }


def main() -> None:
    source_bytes = PDF.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    if source_sha != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {source_sha}")

    import fitz
    with fitz.open(str(PDF)) as doc:
        selected = tuple(range(doc.page_count))

    scope = source_floor_plan_topology_scope(PDF, selected)
    if scope is None:
        raise SystemExit("source floor-plan scope unavailable")

    topology = tuple(
        d.page_index for d in scope.decisions if d.classification == FLOOR_PLAN
    )
    if not topology:
        raise SystemExit("no authenticated topology page")

    candidates = tuple(
        d for d in scope.decisions
        if d.classification == NOT_FLOOR_PLAN
        and "PLAN" in str(d.title or "").upper()
    )

    rows = []
    for decision in candidates:
        support = (decision.page_index,)
        execution = tuple(sorted(set(topology) | set(support)))
        claim = collect_live_physical_net_wall_claim(
            PDF,
            pages=execution,
            topology_pages=topology,
            room_area_support_pages=support,
        )
        quantities = tuple(claim.room_area_quantity_evidence)
        rows.append({
            "support_page_index": decision.page_index,
            "support_page_number": decision.page_index + 1,
            "support_title": decision.title,
            "support_view_types": list(decision.view_types),
            "claim_status": str(getattr(claim.status, "value", claim.status)),
            "claim_reason_codes": list(claim.reason_codes),
            "canonical_room_count": len(claim.canonical_rooms),
            "room_area_quantity_count": len(quantities),
            "room_area_quantities": [_quantity_row(q) for q in quantities],
        })

    print(json.dumps({
        "source_sha256": source_sha,
        "topology_page_numbers": [index + 1 for index in topology],
        "candidate_support_pages": [
            {
                "page_number": d.page_index + 1,
                "title": d.title,
                "view_types": list(d.view_types),
            }
            for d in candidates
        ],
        "rows": rows,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
