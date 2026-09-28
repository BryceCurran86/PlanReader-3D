#!/usr/bin/env python3
import json, re, sys
import fitz

pdf=sys.argv[1]
page_no=int(sys.argv[2])
doc=fitz.open(pdf)
page=doc[page_no-1]
words=page.get_text("words") or []
targets=[]
for i,w in enumerate(words):
    text=str(w[4]).strip()
    if re.search(r"^(?:300|4500|4,500|300x300|300X300)$|pier|masonry|column|stanchion",text,re.I):
        x0,y0,x1,y1=map(float,w[:4])
        neigh=[]
        for j,v in enumerate(words):
            if abs(j-i)>12: continue
            neigh.append({"i":j,"text":str(v[4]),"bbox":[float(x) for x in v[:4]]})
        targets.append({"i":i,"text":text,"bbox":[x0,y0,x1,y1],"neighbors":neigh})

drawings=page.get_drawings() or []
near=[]
for ti,t in enumerate(targets):
    tx0,ty0,tx1,ty1=t["bbox"]
    cx=(tx0+tx1)/2; cy=(ty0+ty1)/2
    local=[]
    for di,d in enumerate(drawings):
        r=d.get("rect")
        if r is None: continue
        rcx=(float(r.x0)+float(r.x1))/2
        rcy=(float(r.y0)+float(r.y1))/2
        if abs(rcx-cx)<=90 and abs(rcy-cy)<=90:
            local.append({
                "drawing":di,
                "rect":[float(r.x0),float(r.y0),float(r.x1),float(r.y1)],
                "fill":d.get("fill"),"color":d.get("color"),
                "items":[str(x[0]) for x in (d.get("items") or ())][:20]
            })
    near.append({"target_index":ti,"local_drawings":local[:120]})

print(json.dumps({
    "page":page_no,
    "text":" ".join(page.get_text("text").split()),
    "targets":targets,
    "nearby_drawings":near
},default=str))
