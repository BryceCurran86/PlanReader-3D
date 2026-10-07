from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import fitz

from pb_drawing_evidence_binding import DrawingViewType
from pb_figured_dimension_evidence import extract_dimension_evidence_bundle
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim

PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_INDEX=2
PAGE_NO=3

def room_bbox(points):
    xs=[float(p[0]) for p in points]
    ys=[float(p[1]) for p in points]
    return (min(xs),min(ys),max(xs),max(ys))

def endpoint_span(obs):
    endpoints=getattr(obs,"endpoints",None)
    if endpoints is None or len(endpoints)!=2:
        return None
    try:
        (x0,y0),(x1,y1)=endpoints
        return (float(x0),float(y0),float(x1),float(y1))
    except Exception:
        return None

def dim_row(obs):
    span=endpoint_span(obs)
    return {
        "dimension_id":str(getattr(obs,"dimension_id","")),
        "raw_text":str(getattr(obs,"raw_text","")),
        "value":getattr(obs,"value",None),
        "unit":str(getattr(obs,"unit","")),
        "orientation":str(getattr(obs,"orientation","")),
        "authority":str(getattr(obs,"authority","")),
        "confidence":float(getattr(obs,"confidence",0.0) or 0.0),
        "conflict_state":str(getattr(obs,"conflict_state","")),
        "extraction_method":str(getattr(obs,"extraction_method","")),
        "witness_targets":list(getattr(obs,"witness_targets",()) or ()),
        "endpoints":None if span is None else list(span),
        "bbox":None if getattr(obs,"bbox",None) is None else list(getattr(obs,"bbox")),
    }

def geometric_delta(room_box, obs):
    span=endpoint_span(obs)
    if span is None:
        return None
    x0,y0,x1,y1=span
    orient=str(getattr(obs,"orientation",""))
    rx0,ry0,rx1,ry1=room_box
    if orient=="horizontal":
        d1=abs(min(x0,x1)-rx0)+abs(max(x0,x1)-rx1)
        return {
            "axis":"horizontal",
            "edge_endpoint_delta_sum_pt":d1,
            "span_pt":abs(x1-x0),
            "room_span_pt":rx1-rx0,
            "span_delta_pt":abs(abs(x1-x0)-(rx1-rx0)),
            "cross_axis_nearest_edge_pt":min(abs((y0+y1)/2-ry0),abs((y0+y1)/2-ry1)),
        }
    if orient=="vertical":
        d1=abs(min(y0,y1)-ry0)+abs(max(y0,y1)-ry1)
        return {
            "axis":"vertical",
            "edge_endpoint_delta_sum_pt":d1,
            "span_pt":abs(y1-y0),
            "room_span_pt":ry1-ry0,
            "span_delta_pt":abs(abs(y1-y0)-(ry1-ry0)),
            "cross_axis_nearest_edge_pt":min(abs((x0+x1)/2-rx0),abs((x0+x1)/2-rx1)),
        }
    return None

def main():
    actual=hashlib.sha256(PDF.read_bytes()).hexdigest()
    if actual!=EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {actual}")

    claim=collect_live_physical_net_wall_claim(
        PDF,
        pages=(PAGE_INDEX,),
        topology_pages=(PAGE_INDEX,),
        room_area_support_pages=None,
    )
    rooms=tuple(claim.canonical_rooms)
    labeled=tuple(
        r for r in rooms
        if str(r.room_label or "").strip()
        and str(r.room_label_binding_record_id or "").strip()
        and tuple(r.room_label_evidence_ids)
    )

    doc=fitz.open(PDF)
    try:
        page=doc[PAGE_INDEX]
        bundle=extract_dimension_evidence_bundle(
            page,
            page_num=PAGE_NO,
            view_id="",
            view_type=DrawingViewType.FLOOR_PLAN.value,
        )
    finally:
        doc.close()

    observations=tuple(bundle.observations)
    bound=tuple(o for o in observations if endpoint_span(o) is not None)
    horizontal=tuple(o for o in bound if str(getattr(o,"orientation",""))=="horizontal")
    vertical=tuple(o for o in bound if str(getattr(o,"orientation",""))=="vertical")

    room_rows=[]
    for room in labeled:
        bbox=room_bbox(room.polygon_pdf_pts)
        hrows=[]
        vrows=[]
        for obs in horizontal:
            delta=geometric_delta(bbox,obs)
            if delta is not None:
                hrows.append({**dim_row(obs),**delta})
        for obs in vertical:
            delta=geometric_delta(bbox,obs)
            if delta is not None:
                vrows.append({**dim_row(obs),**delta})
        hrows.sort(key=lambda x:(x["edge_endpoint_delta_sum_pt"],x["cross_axis_nearest_edge_pt"],x["dimension_id"]))
        vrows.sort(key=lambda x:(x["edge_endpoint_delta_sum_pt"],x["cross_axis_nearest_edge_pt"],x["dimension_id"]))
        room_rows.append({
            "physical_room_id":room.physical_room_id,
            "canonical_room_id":room.canonical_room_id,
            "room_label":room.room_label,
            "room_label_binding_record_id":room.room_label_binding_record_id,
            "room_label_evidence_ids":list(room.room_label_evidence_ids),
            "source_room_face_record_id":room.source_room_face_record_id,
            "viewport_id":room.viewport_id,
            "bbox":list(bbox),
            "best_horizontal_by_exact_geometry":hrows[:8],
            "best_vertical_by_exact_geometry":vrows[:8],
        })

    payload={
        "source_sha256":actual,
        "claim_status":getattr(claim.status,"value",str(claim.status)),
        "canonical_room_count":len(rooms),
        "labeled_room_count":len(labeled),
        "label_counts":dict(Counter(str(r.room_label) for r in labeled)),
        "dimension_observation_count":len(observations),
        "bound_dimension_count":len(bound),
        "horizontal_bound_count":len(horizontal),
        "vertical_bound_count":len(vertical),
        "dimension_authorities":dict(Counter(str(getattr(o,"authority","")) for o in observations)),
        "dimension_conflicts":dict(Counter(str(getattr(o,"conflict_state","")) for o in observations)),
        "dimension_methods":dict(Counter(str(getattr(o,"extraction_method","")) for o in observations)),
        "room_rows":room_rows,
    }
    print(json.dumps(payload,indent=2,sort_keys=True,default=str))

if __name__=="__main__":
    main()
