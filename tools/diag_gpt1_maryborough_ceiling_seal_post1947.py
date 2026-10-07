from __future__ import annotations

import json
from pathlib import Path

from pb_live_ceiling_lining_source_closed_export import (
    seal_live_ceiling_lining_run,
)
from pb_live_physical_net_wall_integration import (
    collect_live_physical_net_wall_claim,
)
from tools.run_source_closed_project_handoff import _source_page_scopes


PDF = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
PROJECT = "au_qld_maryborough_service_station"


def main() -> int:
    topology, support, page_count = _source_page_scopes(PDF)
    all_pages = tuple(range(page_count))
    claim = collect_live_physical_net_wall_claim(
        PDF,
        pages=all_pages,
        topology_pages=(
            topology if topology and topology != all_pages else None
        ),
        room_area_support_pages=(support if support else None),
    )

    quantities = tuple(
        quantity
        for quantity in claim.ceiling_lining_quantity_evidence
        if not quantity.abstained and quantity.value is not None
    )
    run = (
        seal_live_ceiling_lining_run(
            claim,
            workspace_id=1,
            project_id=PROJECT,
        )
        if quantities
        else None
    )

    rooms = {
        room.canonical_room_id: {
            "physical_room_id": room.physical_room_id,
            "room_label": room.room_label,
            "source_room_face_record_id": room.source_room_face_record_id,
            "page_id": room.page_id,
            "viewport_id": room.viewport_id,
        }
        for room in claim.canonical_rooms
    }

    payload = {
        "topology_pages_zero_based": list(topology),
        "support_pages_zero_based": list(support),
        "page_count": page_count,
        "canonical_room_count": len(claim.canonical_rooms),
        "firm_room_area_count": sum(
            1
            for quantity in claim.room_area_quantity_evidence
            if not quantity.abstained and quantity.value is not None
        ),
        "floor_finish_quantity_count": sum(
            1
            for quantity in claim.floor_finish_quantity_evidence
            if not quantity.abstained and quantity.value is not None
        ),
        "ceiling_lining_quantity_count": len(quantities),
        "rooms": rooms,
        "ceiling_quantities": [
            {
                "quantity_id": quantity.quantity_id,
                "semantic_key": quantity.semantic_key,
                "value": quantity.value,
                "unit": quantity.unit,
                "authority": quantity.authority,
                "status": quantity.status,
                "input_entity_ids": list(quantity.input_entity_ids),
                "evidence_ids": list(quantity.evidence_ids),
                "metadata": dict(quantity.metadata or {}),
            }
            for quantity in quantities
        ],
        "sealed_run": None if run is None else run.to_dict(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))

    if quantities:
        assert run is not None
        assert len(run.quantities) == len(quantities)
        assert {row.quantity_id for row in run.quantities} == {
            quantity.quantity_id for quantity in quantities
        }
        assert all(row.lineage_ok for row in run.quantities)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
