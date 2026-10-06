from __future__ import annotations
import hashlib, json
from collections import Counter
from pathlib import Path
from tools.run_source_closed_project_handoff import _source_page_scopes
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim

PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"

def main():
    payload=PDF.read_bytes()
    assert hashlib.sha256(payload).hexdigest()==EXPECTED_SHA
    topology,support,page_count=_source_page_scopes(PDF)
    claim=collect_live_physical_net_wall_claim(
        PDF,
        pages=tuple(range(page_count)),
        topology_pages=topology,
        room_area_support_pages=(support if support else None),
    )
    rooms=[]
    reason_counts=Counter()
    for r in claim.canonical_rooms:
        for reason in r.room_label_reason_codes:
            reason_counts[str(reason)]+=1
        rooms.append({
            "canonical_room_id":r.canonical_room_id,
            "physical_room_id":r.physical_room_id,
            "page_id":r.page_id,
            "viewport_id":r.viewport_id,
            "geometry_complete":r.geometry_complete,
            "room_label":r.room_label,
            "has_label_binding":bool(r.room_label_binding_record_id),
            "label_evidence_count":len(r.room_label_evidence_ids),
            "label_reason_codes":list(r.room_label_reason_codes),
        })
    print(json.dumps({
        "canonical_room_count":len(rooms),
        "labeled_room_count":sum(bool(r["room_label"]) for r in rooms),
        "bound_label_count":sum(r["has_label_binding"] for r in rooms),
        "label_evidence_room_count":sum(r["label_evidence_count"]>0 for r in rooms),
        "same_view_eligible_room_count":sum(
            r["geometry_complete"] and bool(r["room_label"]) and
            r["has_label_binding"] and r["label_evidence_count"]>0
            for r in rooms
        ),
        "label_reason_counts":dict(reason_counts.most_common()),
        "labeled_rooms":[r for r in rooms if r["room_label"]],
    },indent=2,sort_keys=True))

if __name__=="__main__":
    main()
