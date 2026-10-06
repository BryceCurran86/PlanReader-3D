from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
TOPOLOGY_INDEX = 2


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--support-index", type=int, required=True)
    parser.add_argument("--title", required=True)
    args = parser.parse_args()

    source_sha = hashlib.sha256(PDF.read_bytes()).hexdigest()
    if source_sha != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {source_sha}")

    support = int(args.support_index)
    execution = tuple(sorted({TOPOLOGY_INDEX, support}))
    claim = collect_live_physical_net_wall_claim(
        PDF,
        pages=execution,
        topology_pages=(TOPOLOGY_INDEX,),
        room_area_support_pages=(support,),
    )
    quantities = tuple(claim.room_area_quantity_evidence)
    print(json.dumps({
        "source_sha256": source_sha,
        "support_page_number": support + 1,
        "support_title": args.title,
        "canonical_room_count": len(claim.canonical_rooms),
        "room_area_quantity_count": len(quantities),
        "room_area_quantities": [
            {
                "quantity_id": q.quantity_id,
                "value": q.value,
                "unit": q.unit,
                "authority": str(q.authority),
                "status": str(q.status),
                "reason_codes": list(q.reason_codes or ()),
                "metadata": dict(q.metadata or {}),
            }
            for q in quantities
        ],
        "claim_status": str(getattr(claim.status, "value", claim.status)),
        "claim_reason_codes": list(claim.reason_codes),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
