from __future__ import annotations
import hashlib, json
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
        room_area_support_pages=support,
    )
    rows=[]
    for q in claim.room_area_quantity_evidence:
        rows.append({
            "quantity_id":q.quantity_id,
            "value":q.value,
            "unit":q.unit,
            "authority":q.authority,
            "status":q.status,
            "abstained":q.abstained,
            "input_entity_ids":list(q.input_entity_ids),
            "evidence_ids":list(q.evidence_ids),
            "metadata":dict(q.metadata or {}),
        })
    floors=[]
    for f in claim.canonical_floors:
        if getattr(f,"metric_area_m2",None) is None:
            continue
        floors.append({
            "canonical_floor_id":f.canonical_floor_id,
            "physical_floor_surface_id":getattr(f,"physical_floor_surface_id",None),
            "room_entity_id":f.room_entity_id,
            "page_id":f.page_id,
            "viewport_id":f.viewport_id,
            "metric_area_m2":f.metric_area_m2,
            "metric_area_authority":f.metric_area_authority,
            "metric_area_quantity_id":f.metric_area_quantity_id,
            "finish":getattr(f,"finish",None),
        })
    print(json.dumps({
        "topology_pages":topology,
        "support_pages":support,
        "canonical_room_count":len(claim.canonical_rooms),
        "canonical_floor_count":len(claim.canonical_floors),
        "room_area_quantity_count":len(rows),
        "metric_floor_count":len(floors),
        "room_area_quantities":rows,
        "metric_floors":floors,
    },indent=2,sort_keys=True,default=str))

if __name__=="__main__":
    main()
