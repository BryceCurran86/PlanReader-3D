from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pb_live_opening_area_quantity_publication import publish_live_opening_area_quantities
from pb_live_opening_count_quantity_publication import (
    publish_live_authenticated_opening_count_quantities,
)
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_visibility_authority import SourceVisibilityProducer


PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID="3"


def state(value):
    return str(getattr(value,"value",value))


def main():
    source_bytes=PDF.read_bytes()
    actual=hashlib.sha256(source_bytes).hexdigest()
    if actual != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {actual}")

    source=SourceVisibilityProducer(
        producer_method="diag_gpt3_lot16_host_integration_v1",
        producer_version="1",
    )
    published=source.ingest_native_pdf_bytes(
        document_id="diag-gpt3-lot16-host-integration-v1",
        source_bytes=source_bytes,
        source_locator=str(PDF),
        page_ids=(PAGE_ID,),
    )
    wall_opening=compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=(PAGE_ID,),
    )
    voids=compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )
    areas=publish_live_opening_area_quantities(voids)
    counts=publish_live_authenticated_opening_count_quantities(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )

    semantic=wall_opening.semantic_enumeration_result
    record=semantic.record
    universe=wall_opening.opening_universe_result

    payload={
        "source_sha256":actual,
        "wall_opening_status":state(wall_opening.status),
        "wall_opening_reason_codes":list(wall_opening.reason_codes),
        "semantic_status":state(semantic.status),
        "semantic_reason_codes":list(semantic.reason_codes),
        "physical_opening_universe_complete":(
            None if record is None else bool(record.physical_opening_universe_complete)
        ),
        "semantic_physical_opening_count":(
            0 if record is None else len(record.physical_opening_record_ids)
        ),
        "opening_universe_status":state(universe.status),
        "opening_universe_reason_codes":list(universe.reason_codes),
        "opening_binding_count":len(wall_opening.opening_bindings),
        "host_bound_count":sum(1 for x in wall_opening.opening_bindings if x.host_wall_id),
        "two_face_lineage_host_count":sum(
            1
            for x in wall_opening.opening_bindings
            if "two_face_source_lineage_host_resolved" in x.reason_codes
        ),
        "host_binding_reason_counts":{},
        "host_frame_count":len(wall_opening.host_frames),
        "canonical_opening_count":len(voids.canonical_openings),
        "kind_resolved_count":sum(1 for x in voids.canonical_openings if x.opening_kind),
        "area_resolved_count":sum(1 for x in voids.canonical_openings if x.area_m2 is not None),
        "opening_area_quantity_count":len(areas),
        "opening_count_quantity_count":len(counts),
        "opening_area_values":[float(x.value) for x in areas],
        "opening_count_values":[float(x.value) for x in counts],
    }
    for trace in wall_opening.opening_bindings:
        for reason in trace.reason_codes:
            payload["host_binding_reason_counts"][reason]=(
                payload["host_binding_reason_counts"].get(reason,0)+1
            )
    print(json.dumps(payload,indent=2,sort_keys=True))


if __name__=="__main__":
    main()
