from __future__ import annotations
import hashlib, json, math, re
from collections import Counter
from pathlib import Path

import fitz

from tools.run_source_closed_project_handoff import _source_page_scopes
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from pb_source_room_label_authority import _normalized_room_line

PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"

def point_in_polygon(point, polygon):
    x,y=point
    pts=tuple((float(p[0]),float(p[1])) for p in polygon)
    inside=False
    for index,(x1,y1) in enumerate(pts):
        x2,y2=pts[(index+1)%len(pts)]
        if (y1>y)==(y2>y):
            continue
        crossing=x1+(y-y1)*(x2-x1)/(y2-y1)
        if crossing>x:
            inside=not inside
    return inside

def bbox_of(polygon):
    xs=[float(p[0]) for p in polygon]
    ys=[float(p[1]) for p in polygon]
    return (min(xs),min(ys),max(xs),max(ys))

def point_bbox_distance(point,bbox):
    x,y=point
    x0,y0,x1,y1=bbox
    dx=max(x0-x,0.0,x-x1)
    dy=max(y0-y,0.0,y-y1)
    return math.hypot(dx,dy)

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
    room_objects=tuple(claim.canonical_rooms)
    rooms=[]
    reason_counts=Counter()
    for r in room_objects:
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
            "polygon_bbox_pdf_pt":list(bbox_of(r.polygon_pdf_pts)),
            "area_page_pts2":float(r.area_page_pts2),
        })

    doc=fitz.open(stream=payload,filetype="pdf")
    line_rows=[]
    for page_index in topology:
        page=doc[page_index]
        page_id=str(page_index+1)
        scoped=[r for r in room_objects if str(r.page_id)==page_id]
        for block in (page.get_text("dict").get("blocks") or ()):
            for line in (block.get("lines") or ()):
                spans=line.get("spans") or ()
                text=" ".join(
                    str(span.get("text") or "").strip()
                    for span in spans
                    if str(span.get("text") or "").strip()
                ).strip()
                compact=" ".join(text.split())
                if not compact:
                    continue
                if len(compact.split())>4 or not re.fullmatch(r"[A-Za-z&\- /\.]+",compact):
                    continue
                bbox=tuple(float(x) for x in line.get("bbox",(0,0,0,0)))
                center=((bbox[0]+bbox[2])/2.0,(bbox[1]+bbox[3])/2.0)
                containing=[
                    r for r in scoped
                    if point_in_polygon(center,r.polygon_pdf_pts)
                ]
                distances=sorted(
                    (
                        point_bbox_distance(center,bbox_of(r.polygon_pdf_pts)),
                        r.physical_room_id,
                    )
                    for r in scoped
                )
                line_rows.append({
                    "page_id":page_id,
                    "text":compact,
                    "bbox_pdf_pt":list(bbox),
                    "center_pdf_pt":list(center),
                    "normalized_room_label":_normalized_room_line(compact),
                    "containing_room_count":len(containing),
                    "containing_room_ids":[r.physical_room_id for r in containing],
                    "nearest_room_bbox_distance_pt":(
                        None if not distances else distances[0][0]
                    ),
                    "nearest_room_id":(
                        None if not distances else distances[0][1]
                    ),
                })
    doc.close()

    room_like_lines=[
        row for row in line_rows
        if row["normalized_room_label"] is not None
        or row["text"].upper()==row["text"]
    ]
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
        "topology_pages_zero_based":list(topology),
        "short_alpha_line_count":len(line_rows),
        "room_like_line_count":len(room_like_lines),
        "room_like_lines":room_like_lines,
    },indent=2,sort_keys=True))

if __name__=="__main__":
    main()
