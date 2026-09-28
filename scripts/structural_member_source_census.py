#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path
import fitz

from pb_dimension_chain_evidence_extractor import extract_dimension_chains_from_page
from pb_secondary_area_support_evidence import extract_secondary_area_support_evidence_from_page

p=argparse.ArgumentParser()
p.add_argument("--pdf",required=True)
p.add_argument("--page",type=int,required=True)
p.add_argument("--label",required=True)
a=p.parse_args()

doc=fitz.open(a.pdf)
page=doc[a.page-1]
blocks=[]
for i,b in enumerate(page.get_text("blocks") or []):
    text=" ".join(str(b[4]).split())
    if re.search(r"pier|pillar|column|post|CHS|RHS|SHS|masonry|300\s*[xX×]\s*300|50\s*mm",text,re.I):
        blocks.append({"index":i,"text":text,"bbox":[float(x) for x in b[:4]]})

drawings=[]
for i,d in enumerate(page.get_drawings() or []):
    rect=d.get("rect")
    if rect is None: continue
    w,h=float(rect.width),float(rect.height)
    kinds=[str(x[0]) for x in (d.get("items") or ())]
    closed_rect=(kinds==["re"] or (len(kinds)==4 and all(k=="l" for k in kinds)))
    if closed_rect and w>0 and h>0 and max(w,h)/min(w,h)<=1.35:
        drawings.append({
            "index":i,"bbox":[float(rect.x0),float(rect.y0),float(rect.x1),float(rect.y1)],
            "width":w,"height":h,"fill":d.get("fill"),"color":d.get("color"),
            "kinds":kinds
        })

chains=extract_dimension_chains_from_page(page,page_num=a.page,view_id=f"page_{a.page}")
support=extract_secondary_area_support_evidence_from_page(
    page,source_page=a.page,dimension_chains=chains
)
out={
    "label":a.label,"page":a.page,"page_rect":[float(page.rect.width),float(page.rect.height)],
    "matched_text_blocks":blocks,
    "closed_near_square_drawings":drawings,
    "dimension_chains":[{
        "chain_id":str(c.chain_id),"orientation":str(c.orientation),
        "values_m":[float(o.value_m) for o in c.observations if o.value_m>0],
        "bboxes":[list(map(float,o.bbox)) for o in c.observations if o.bbox is not None]
    } for c in chains],
    "existing_secondary_support":None if support is None else support.__dict__,
}
print(json.dumps(out,default=str))
