from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pb_live_opening_area_quantity_publication import publish_live_opening_area_quantities
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_visibility_authority import SourceVisibilityProducer

PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"

def main():
    source_bytes=PDF.read_bytes()
    sha=hashlib.sha256(source_bytes).hexdigest()
    if sha != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {sha}")

    source=SourceVisibilityProducer(
        producer_method="diag_gpt3_lot16_area_publication_gap",
        producer_version="1",
    )
    initial=source.ingest_native_pdf_bytes(
        document_id="diag-gpt3-lot16-area-publication-gap",
        source_bytes=source_bytes,
        source_locator=str(PDF),
        page_ids=("3",),
    )
    wall=compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=initial.revision.revision_id,
        page_ids=("3",),
    )
    voids=compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall,
    )
    quantities=publish_live_opening_area_quantities(voids)
    published_ids={
        str(q.input_entity_ids[0])
        for q in quantities
        if q.input_entity_ids
    }

    rows=[]
    for opening in sorted(voids.canonical_openings,key=lambda x:x.physical_opening_id):
        if opening.area_m2 is None or opening.physical_opening_id in published_ids:
            continue
        evidence=set(str(x) for x in opening.evidence_ids)
        if opening.area_basis=="figured_opening_label":
            measurement_id=opening.figured_area_record_id
        elif opening.area_basis=="resolved_opening_geometry":
            measurement_id=opening.opening_void_record_id
        elif opening.area_basis=="authenticated_elevation_frame":
            measurement_id=opening.figured_area_record_id
        elif opening.area_basis=="authenticated_frame_schedule":
            measurement_id=opening.schedule_binding_record_id
        else:
            measurement_id=None
        rows.append({
            "physical_opening_id":opening.physical_opening_id,
            "pattern":opening.structural_pattern,
            "area_m2":opening.area_m2,
            "area_basis":opening.area_basis,
            "opening_kind":opening.opening_kind,
            "host_wall_id":opening.host_wall_id,
            "host_binding_record_id":opening.host_binding_record_id,
            "host_frame_record_id":opening.host_frame_record_id,
            "viewport_id":opening.viewport_id,
            "measurement_record_id":measurement_id,
            "measurement_record_retained":(
                measurement_id is not None and str(measurement_id) in evidence
            ),
            "schedule_row_dimension_basis":opening.schedule_row_dimension_basis,
            "type_mark":opening.type_mark,
        })
    print(json.dumps({
        "canonical_area_count":sum(1 for x in voids.canonical_openings if x.area_m2 is not None),
        "published_area_count":len(quantities),
        "measured_but_unpublished_count":len(rows),
        "rows":rows,
    },indent=2,sort_keys=True))

if __name__=="__main__":
    main()
