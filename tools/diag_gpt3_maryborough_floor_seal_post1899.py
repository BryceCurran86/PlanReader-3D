from __future__ import annotations

import json
from pathlib import Path

from pb_live_floor_area_quantity_publication import publish_live_floor_area_quantities
from pb_live_floor_area_source_closed_export import seal_live_floor_area_run
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from tools.run_source_closed_project_handoff import _source_page_scopes


PDF=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
PROJECT="au_qld_maryborough_service_station"


def main():
    topology,support,page_count=_source_page_scopes(PDF)
    all_pages=tuple(range(page_count))
    claim=collect_live_physical_net_wall_claim(
        PDF,
        pages=all_pages,
        topology_pages=(topology if topology and topology!=all_pages else None),
        room_area_support_pages=(support if support else None),
    )
    floor_quantities=tuple(
        q for q in publish_live_floor_area_quantities(claim)
        if not q.abstained and q.value is not None
    )
    run=(
        seal_live_floor_area_run(
            claim,
            workspace_id=1,
            project_id=PROJECT,
        )
        if floor_quantities else None
    )
    payload={
        "topology_pages_zero_based":list(topology),
        "support_pages_zero_based":list(support),
        "page_count":page_count,
        "canonical_room_count":len(claim.canonical_rooms),
        "canonical_floor_count":len(claim.canonical_floors),
        "firm_room_area_count":sum(
            1 for q in claim.room_area_quantity_evidence
            if not q.abstained and q.value is not None
        ),
        "floor_area_quantity_count":len(floor_quantities),
        "floor_quantities":[
            {
                "quantity_id":q.quantity_id,
                "value":q.value,
                "unit":q.unit,
                "authority":q.authority,
                "semantic_key":q.semantic_key,
                "input_entity_ids":list(q.input_entity_ids),
                "evidence_ids":list(q.evidence_ids),
                "metadata":dict(q.metadata or {}),
            }
            for q in floor_quantities
        ],
        "sealed_run":None if run is None else run.to_dict(),
    }
    print(json.dumps(payload,indent=2,sort_keys=True))
    if floor_quantities and run is not None:
        assert len(run.quantities)==len(floor_quantities)
        assert {q.quantity_id for q in floor_quantities}=={q.quantity_id for q in run.quantities}


if __name__=="__main__":
    main()
