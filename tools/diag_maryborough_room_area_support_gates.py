from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import fitz

import pb_cross_view_room_area_authority as cv
from pb_live_canonical_room_composition import compose_live_canonical_rooms
from pb_live_canonical_wall_composition import compose_live_canonical_walls
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_floor_plan_page_scope import source_floor_plan_topology_scope
from pb_source_visibility_authority import SourceVisibilityProducer

SOURCE=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
TARGETS=("AIRLOCK","LAUNDRY","OFFICE","PWD")

def norm(value):
    return " ".join(str(value or "").strip().upper().split())

def exact_native_lines(page):
    grouped=defaultdict(list)
    for word in page.get_text("words") or ():
        if len(word)<8:
            continue
        grouped[(int(word[5]),int(word[6]))].append(word)
    out=[]
    for key,words in grouped.items():
        ordered=sorted(words,key=lambda row:int(row[7]))
        text=" ".join(str(row[4]).strip() for row in ordered if str(row[4]).strip())
        if text:
            out.append(norm(text))
    return tuple(out)

def pair_payload(h,v):
    return {
        "h_id":str(h.dimension_id),"h_mm":float(h.value_mm),
        "h_endpoints_pt":[list(h.endpoints_pt[0]),list(h.endpoints_pt[1])],
        "h_witness_geometries":[list(row) for row in h.witness_geometries],
        "v_id":str(v.dimension_id),"v_mm":float(v.value_mm),
        "v_endpoints_pt":[list(v.endpoints_pt[0]),list(v.endpoints_pt[1])],
        "v_witness_geometries":[list(row) for row in v.witness_geometries],
        "area_m2_if_owned":round(float(h.value_mm)*float(v.value_mm)/1_000_000.0,9),
    }

def main():
    doc=fitz.open(SOURCE)
    try:
        scope=source_floor_plan_topology_scope(SOURCE,tuple(range(doc.page_count)))
        if scope is None:
            raise RuntimeError("source page scope unavailable")
        decisions={d.page_index:d for d in scope.decisions}
        candidates=defaultdict(set)
        for page_index in scope.evidence_page_indices:
            page_lines=set(exact_native_lines(doc[page_index]))
            for target in TARGETS:
                if target in page_lines:
                    candidates[target].add(page_index)
        support_indices=sorted({i for values in candidates.values() for i in values})
    finally:
        doc.close()

    page_ids=("7",)+tuple(str(i+1) for i in support_indices)
    source=SourceVisibilityProducer(
        producer_method="gpt2-room-area-support-gates",
        producer_version="1",
    )
    published=source.ingest_native_pdf_bytes(
        document_id="gpt2-room-area-support-gates",
        source_bytes=SOURCE.read_bytes(),
        source_locator="memory://maryborough.pdf",
        page_ids=page_ids,
    )
    wo=compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("7",),
        evidence_page_ids=(),
    )
    cw=compose_live_canonical_walls(
        source_visibility_producer=source,
        wall_opening_composition=wo,
    )
    rooms=compose_live_canonical_rooms(
        source_visibility_producer=source,
        wall_opening_composition=wo,
        canonical_wall_ids_by_candidate=cw.candidate_to_canonical_wall_id,
        unresolved_wall_candidate_ids=cw.unresolved_wall_candidate_ids,
    )
    eligible=[
        room for room in rooms.rooms
        if room.geometry_complete
        and str(room.physical_room_id or "").strip()
        and str(room.source_room_face_record_id or "").strip()
        and norm(room.room_label) in TARGETS
        and str(room.room_label_binding_record_id or "").strip()
        and bool(room.room_label_evidence_ids)
    ]
    grouped=defaultdict(list)
    for room in eligible:
        grouped[norm(room.room_label)].append(room)
    unique={k:v[0] for k,v in grouped.items() if len(v)==1}

    audit={target:[] for target in TARGETS}
    for page_index in support_indices:
        page_id=str(page_index+1)
        decision=decisions[page_index]
        lines=cv._trusted_lines_for_page(
            source,
            revision_id=published.revision.revision_id,
            page_id=page_id,
            candidate_labels=tuple(unique),
        )
        for target in TARGETS:
            room=unique.get(target)
            relevant=tuple(line for line in lines if norm(line.text)==target)
            if room is None or not relevant:
                continue
            dims=cv._trusted_native_dimensions_for_page(
                source,
                revision_id=published.revision.revision_id,
                page_id=page_id,
                candidate_lines=relevant,
            )
            hs=tuple(d for d in dims if d.orientation==cv.DimensionOrientation.HORIZONTAL.value)
            vs=tuple(d for d in dims if d.orientation==cv.DimensionOrientation.VERTICAL.value)
            spatial=[]
            scaled=[]
            witness=[]
            for line in relevant:
                for h in hs:
                    for v in vs:
                        if not cv._line_inside_dimension_pair(line,h,v):
                            continue
                        spatial.append(pair_payload(h,v))
                        if not cv._figured_pair_scale_consistent(page_id=page_id,horizontal=h,vertical=v):
                            continue
                        scaled.append(pair_payload(h,v))
                        if not cv._witness_systems_intersect(h,v):
                            continue
                        witness.append(pair_payload(h,v))
            owned_h=[
                (line,d) for line in relevant for d in hs
                if cv._dimension_is_immediate_label_annotation(line,d)
            ]
            owned_v=[
                (line,d) for line in relevant for d in vs
                if cv._dimension_is_immediate_label_annotation(line,d)
            ]
            annotations=[]
            seen=set()
            for _hl,h in owned_h:
                for _vl,v in owned_v:
                    if not cv._figured_pair_scale_consistent(page_id=page_id,horizontal=h,vertical=v):
                        continue
                    key=(h.dimension_id,v.dimension_id)
                    if key in seen:
                        continue
                    seen.add(key)
                    annotations.append(pair_payload(h,v))
            audit[target].append({
                "page_number_one_based":page_index+1,
                "title":decision.title,
                "classification":decision.classification,
                "view_types":list(decision.view_types),
                "trusted_label_count":len(relevant),
                "trusted_dimension_count":len(dims),
                "horizontal_dimension_count":len(hs),
                "vertical_dimension_count":len(vs),
                "spatial_pair_count":len(spatial),
                "scale_consistent_pair_count":len(scaled),
                "scale_consistent_pairs":scaled,
                "witness_pair_count":len(witness),
                "witness_pairs":witness,
                "annotation_horizontal_count":len(owned_h),
                "annotation_vertical_count":len(owned_v),
                "annotation_pair_count":len(annotations),
                "annotation_pairs":annotations,
            })

    result=cv.CrossViewRoomAreaProducer.from_source(source=source,rooms=rooms).publish()
    published_rows={
        norm(record.room_label):{
            "area_m2":record.area_evidence.normalized_value,
            "page_id":record.source_dimension_page_id,
            "h":record.horizontal_dimension_id,
            "v":record.vertical_dimension_id,
            "support_mode":record.area_evidence.metadata.get("source_label_support_mode"),
        }
        for record in result.records
        if norm(record.room_label) in TARGETS
    }
    print(json.dumps({
        "decoded_page_ids":list(page_ids),
        "navigation_pages":{
            target:[
                {
                    "page_number_one_based":i+1,
                    "title":decisions[i].title,
                    "classification":decisions[i].classification,
                    "view_types":list(decisions[i].view_types),
                }
                for i in sorted(candidates[target])
            ]
            for target in TARGETS
        },
        "unique_topology_targets":sorted(unique),
        "audit":audit,
        "published_records":published_rows,
        "result_status":getattr(result.status,"value",str(result.status)),
        "reason_codes":list(result.reason_codes),
    },indent=2,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
