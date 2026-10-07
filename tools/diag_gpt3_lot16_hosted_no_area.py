from __future__ import annotations

from dataclasses import asdict, is_dataclass
import hashlib
import json
from pathlib import Path

from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_opening_label_dimension_authority import OpeningLabelDimensionProducer
from pb_opening_label_semantic_authority import OpeningLabelSemanticProducer
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID="3"


def _state(value):
    return str(getattr(value,"value",value))


def _jsonable(value):
    if value is None or isinstance(value,(str,int,float,bool)):
        return value
    if is_dataclass(value):
        return {k:_jsonable(v) for k,v in asdict(value).items()}
    if isinstance(value,dict):
        return {str(k):_jsonable(v) for k,v in value.items()}
    if isinstance(value,(tuple,list,set,frozenset)):
        return [_jsonable(v) for v in value]
    return str(value)


def _result_payload(result):
    if result is None:
        return None
    return {
        "status":_state(getattr(result,"status",None)),
        "reason_codes":[str(x) for x in getattr(result,"reason_codes",())],
        "evidence":_jsonable(getattr(result,"evidence",None)),
        "record":_jsonable(getattr(result,"record",None)),
    }


def main():
    source_bytes=PDF.read_bytes()
    sha=hashlib.sha256(source_bytes).hexdigest()
    if sha != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {sha}")

    source=SourceVisibilityProducer(
        producer_method="diag_gpt3_lot16_hosted_no_area",
        producer_version="1",
    )
    initial=source.ingest_native_pdf_bytes(
        document_id="diag-gpt3-lot16-hosted-no-area",
        source_bytes=source_bytes,
        source_locator=str(PDF),
        page_ids=(PAGE_ID,),
    )
    wall=compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=initial.revision.revision_id,
        page_ids=(PAGE_ID,),
    )
    voids=compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall,
    )
    current=source.published_snapshot_for_revision(initial.revision.revision_id)
    if current is None:
        raise SystemExit("current snapshot unavailable")

    trace_by_id={x.opening_identity_id:x for x in voids.traces}
    targets=[
        x for x in voids.canonical_openings
        if x.host_wall_id is not None and x.area_m2 is None
    ]

    label_dimension=OpeningLabelDimensionProducer.from_source_visibility_producer(source)
    label_semantic=OpeningLabelSemanticProducer.from_source_visibility_producer(source)

    rows=[]
    for opening in sorted(targets,key=lambda x:x.physical_opening_id):
        selector=ObservationSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            observation_id=opening.representative_observation_id,
        )
        dimension_result=label_dimension.publish_scope(selector)
        semantic_result=label_semantic.publish_scope(selector)
        trace=trace_by_id.get(opening.physical_opening_id)
        rows.append({
            "physical_opening_id":opening.physical_opening_id,
            "pattern":opening.structural_pattern,
            "host_wall_id":opening.host_wall_id,
            "host_binding_record_id":opening.host_binding_record_id,
            "host_frame_record_id":opening.host_frame_record_id,
            "opening_kind":opening.opening_kind,
            "type_mark":opening.type_mark,
            "area_m2":opening.area_m2,
            "area_basis":opening.area_basis,
            "figured_area_record_id":opening.figured_area_record_id,
            "width_m":opening.width_m,
            "height_m":opening.height_m,
            "geometry_complete":opening.geometry_complete,
            "schedule_binding_record_id":opening.schedule_binding_record_id,
            "schedule_page_id":opening.schedule_page_id,
            "schedule_declared_width_mm":opening.schedule_declared_width_mm,
            "schedule_declared_height_mm":opening.schedule_declared_height_mm,
            "schedule_row_dimension_basis":opening.schedule_row_dimension_basis,
            "source_observation_ids":list(opening.source_observation_ids),
            "source_geometries":[list(g) for g in opening.source_geometries],
            "trace":None if trace is None else {
                "width_status":_state(trace.width_status),
                "width_reason_codes":list(trace.width_reason_codes),
                "schedule_binding_status":_state(trace.schedule_binding_status),
                "schedule_binding_reason_codes":list(trace.schedule_binding_reason_codes),
                "height_status":_state(trace.height_status),
                "height_reason_codes":list(trace.height_reason_codes),
                "vertical_status":_state(trace.vertical_status),
                "vertical_reason_codes":list(trace.vertical_reason_codes),
                "scale_status":_state(trace.scale_status),
                "scale_reason_codes":list(trace.scale_reason_codes),
                "void_status":_state(trace.void_status),
                "void_reason_codes":list(trace.void_reason_codes),
            },
            "label_dimension":_result_payload(dimension_result),
            "label_semantic":_result_payload(semantic_result),
        })

    payload={
        "source_sha256":sha,
        "canonical_opening_count":len(voids.canonical_openings),
        "host_proven_count":sum(1 for x in voids.canonical_openings if x.host_wall_id is not None),
        "area_resolved_count":sum(1 for x in voids.canonical_openings if x.area_m2 is not None),
        "host_proven_no_area_count":len(rows),
        "rows":rows,
    }
    print(json.dumps(payload,indent=2,sort_keys=True))


if __name__=="__main__":
    main()
