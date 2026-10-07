from __future__ import annotations

import hashlib
import json
from pathlib import Path
import fitz

from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from pb_live_floor_area_quantity_publication import publish_live_floor_area_quantities
from pb_live_ceiling_lining_integration import collect_live_ceiling_lining_claims
from pb_live_ceiling_area_quantity_publication import publish_live_ceiling_area_quantities
from pb_hosted_opening_instance_adapter import authoritative_floor_plan_viewports

PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
TOPOLOGY=(2,)

def main():
    actual=hashlib.sha256(PDF.read_bytes()).hexdigest()
    if actual!=EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {actual}")

    claim=collect_live_physical_net_wall_claim(
        PDF,
        pages=TOPOLOGY,
        topology_pages=TOPOLOGY,
        room_area_support_pages=None,
    )
    floor_all=publish_live_floor_area_quantities(claim)
    floor_q=tuple(q for q in floor_all if not q.abstained and q.value is not None)
    authoritative_room=tuple(
        q for q in claim.room_area_quantity_evidence
        if not q.abstained and q.value is not None
    )
    ceiling=collect_live_ceiling_lining_claims(
        PDF,
        pages=TOPOLOGY,
        authoritative_room_area_quantities=authoritative_room,
    )
    ceiling_q=tuple(
        q for q in publish_live_ceiling_area_quantities(ceiling)
        if not q.abstained and q.value is not None
    )

    doc=fitz.open(PDF)
    try:
        viewport_rows=[]
        for index in TOPOLOGY:
            for vp in authoritative_floor_plan_viewports(doc[index],page_number=index+1):
                viewport_rows.append({
                    "page_no":index+1,
                    "viewport_id":vp.view_id,
                    "view_type":vp.view_type,
                    "status":vp.status,
                    "bbox":list(vp.bounding_box) if vp.bounding_box else None,
                })
    finally:
        doc.close()

    payload={
        "source_sha256":actual,
        "claim_status":getattr(claim.status,"value",str(claim.status)),
        "claim_reason_codes":list(claim.reason_codes),
        "canonical_room_count":len(claim.canonical_rooms),
        "canonical_room_status":getattr(claim.canonical_room_status,"value",str(claim.canonical_room_status)),
        "canonical_room_reason_codes":list(claim.canonical_room_reason_codes),
        "canonical_floor_count":len(claim.canonical_floors),
        "canonical_floor_status":getattr(claim.canonical_floor_status,"value",str(claim.canonical_floor_status)),
        "canonical_floor_reason_codes":list(claim.canonical_floor_reason_codes),
        "metric_floor_count":sum(
            1 for f in claim.canonical_floors
            if getattr(f,"metric_area_m2",None) not in (None,0)
        ),
        "room_area_quantity_count":len(authoritative_room),
        "room_area_quantities":[q.to_dict() for q in authoritative_room],
        "floor_quantity_count":len(floor_q),
        "floor_quantities":[q.to_dict() for q in floor_q],
        "all_floor_publication_count":len(floor_all),
        "all_floor_publications":[q.to_dict() for q in floor_all],
        "authoritative_floor_plan_viewports":viewport_rows,
        "ceiling_status":getattr(ceiling.status,"value",str(ceiling.status)),
        "ceiling_reason_codes":list(ceiling.reason_codes),
        "canonical_ceiling_count":len(ceiling.canonical_ceilings),
        "ceiling_shadow_quantity_count":len(ceiling.quantity_evidence),
        "ceiling_final_quantity_count":len(ceiling_q),
        "canonical_ceilings":[c.to_dict() for c in ceiling.canonical_ceilings],
        "ceiling_quantities":[q.to_dict() for q in ceiling_q],
    }
    print(json.dumps(payload,indent=2,sort_keys=True,default=str))

if __name__=="__main__":
    main()
