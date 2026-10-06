from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from pb_live_ceiling_area_quantity_publication import publish_live_ceiling_area_quantities
from pb_live_ceiling_lining_integration import collect_live_ceiling_lining_claims
from pb_live_floor_area_quantity_publication import publish_live_floor_area_quantities
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from tools.run_source_closed_project_handoff import _source_page_scopes


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"


def status(value) -> str:
    return str(getattr(value, "value", value))


def main() -> None:
    source_sha = hashlib.sha256(PDF.read_bytes()).hexdigest()
    if source_sha != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {source_sha}")

    topology, support, page_count = _source_page_scopes(PDF)
    execution = tuple(sorted(set(topology) | set(support))) or topology
    claim = collect_live_physical_net_wall_claim(
        PDF,
        pages=execution,
        topology_pages=topology,
        room_area_support_pages=(support or None),
    )
    floors = tuple(claim.canonical_floors)
    room_quantities = tuple(claim.room_area_quantity_evidence)
    floor_quantities = publish_live_floor_area_quantities(claim)

    ceiling = collect_live_ceiling_lining_claims(
        PDF,
        pages=(topology if topology else tuple(range(page_count))),
        authoritative_room_area_quantities=room_quantities,
    )
    ceiling_quantities = publish_live_ceiling_area_quantities(ceiling)

    room_status = Counter(str(q.status) for q in room_quantities)
    room_authority = Counter(str(q.authority) for q in room_quantities)
    room_reasons = Counter(
        reason
        for q in room_quantities
        for reason in tuple(q.reason_codes or ())
    )
    floor_metric_authority = Counter(
        str(f.metric_area_authority or "<none>") for f in floors
    )

    payload = {
        "source_sha256": source_sha,
        "topology_pages": [x + 1 for x in topology],
        "room_area_support_pages": [x + 1 for x in support],
        "execution_pages": [x + 1 for x in execution],
        "claim_status": status(claim.status),
        "claim_reason_codes": list(claim.reason_codes),
        "canonical_room_status": status(claim.canonical_room_status),
        "canonical_room_reason_codes": list(claim.canonical_room_reason_codes),
        "canonical_room_count": len(claim.canonical_rooms),
        "room_area_quantity_count": len(room_quantities),
        "room_area_quantity_status": dict(room_status),
        "room_area_quantity_authority": dict(room_authority),
        "room_area_quantity_reasons": dict(room_reasons.most_common()),
        "canonical_floor_status": status(claim.canonical_floor_status),
        "canonical_floor_reason_codes": list(claim.canonical_floor_reason_codes),
        "canonical_floor_count": len(floors),
        "floor_metric_area_count": sum(f.metric_area_m2 is not None for f in floors),
        "floor_metric_quantity_id_count": sum(bool(f.metric_area_quantity_id) for f in floors),
        "floor_metric_authority": dict(floor_metric_authority),
        "published_floor_quantity_count": len(floor_quantities),
        "published_floor_quantities": [
            {
                "quantity_id": q.quantity_id,
                "value": q.value,
                "authority": q.authority,
                "input_entity_ids": list(q.input_entity_ids),
                "metadata": dict(q.metadata or {}),
            }
            for q in floor_quantities
        ],
        "ceiling_status": status(ceiling.status),
        "ceiling_reason_codes": list(ceiling.reason_codes),
        "canonical_ceiling_count": len(ceiling.canonical_ceilings),
        "shadow_ceiling_quantity_count": len(ceiling.quantity_evidence),
        "canonical_ceiling_metric_complete_count": sum(
            bool(x.metric_area_complete) for x in ceiling.canonical_ceilings
        ),
        "published_ceiling_quantity_count": len(ceiling_quantities),
        "published_ceiling_quantities": [
            {
                "quantity_id": q.quantity_id,
                "value": q.value,
                "authority": q.authority,
                "input_entity_ids": list(q.input_entity_ids),
                "metadata": dict(q.metadata or {}),
            }
            for q in ceiling_quantities
        ],
        "sample_floors": [
            {
                "canonical_floor_id": f.canonical_floor_id,
                "room_entity_id": f.room_entity_id,
                "page_id": f.page_id,
                "viewport_id": f.viewport_id,
                "metric_area_m2": f.metric_area_m2,
                "metric_area_quantity_id": f.metric_area_quantity_id,
                "metric_area_authority": f.metric_area_authority,
                "geometry_complete": f.geometry_complete,
                "physical_identity_resolved": f.physical_floor_surface_identity_resolved,
            }
            for f in floors[:20]
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
