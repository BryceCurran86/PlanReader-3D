#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
import fitz

p=argparse.ArgumentParser()
p.add_argument("--pdf",required=True)
p.add_argument("--start",type=int,required=True)
p.add_argument("--end",type=int,required=True)
a=p.parse_args()

doc=fitz.open(a.pdf)
rows=[]
pattern=re.compile(r"\b(pier|pillar|column|post|CHS|RHS|SHS|masonry)\b|300\s*[xX×]\s*300",re.I)
for page_no in range(a.start,a.end+1):
    page=doc[page_no-1]
    blocks=[]
    for i,b in enumerate(page.get_text("blocks") or []):
        text=" ".join(str(b[4]).split())
        if pattern.search(text):
            blocks.append({"index":i,"text":text,"bbox":[float(x) for x in b[:4]]})
    near_squares=[]
    for i,d in enumerate(page.get_drawings() or []):
        rect=d.get("rect")
        if rect is None: continue
        w,h=float(rect.width),float(rect.height)
        if w<=0 or h<=0 or max(w,h)/min(w,h)>1.25: continue
        kinds=[str(x[0]) for x in (d.get("items") or ())]
        if not (kinds==["re"] or (len(kinds)==4 and all(k=="l" for k in kinds))): continue
        if max(w,h) > min(float(page.rect.width),float(page.rect.height))*0.04: continue
        near_squares.append({
          "index":i,"bbox":[float(rect.x0),float(rect.y0),float(rect.x1),float(rect.y1)],
          "width":w,"height":h,"fill":d.get("fill")
        })
    if blocks or near_squares:
        rows.append({
          "page":page_no,
          "text_head":" ".join(page.get_text("text").split())[:220],
          "matched_blocks":blocks,
          "near_square_count":len(near_squares),
          "near_squares":near_squares[:80],
        })
print(json.dumps({"pages":rows},default=str))
