from __future__ import annotations

import argparse, collections, json
from pathlib import Path
import fitz
from pb_vector_geometry_v130 import _clip_scissor_by_seqno

def page_stats(page, page_number):
    table=_clip_scissor_by_seqno(page)
    drawings=page.get_drawings() or []
    counts=collections.Counter()
    samples=[]
    for d in drawings:
        seq=d.get("seqno") if isinstance(d,dict) else None
        try:
            key=int(seq) if seq is not None else None
        except Exception:
            key=None
        assoc=table.by_seqno.get(key) if key is not None else None
        state=(
            "missing" if assoc is None else
            "unclipped" if not assoc.clip_present else
            "exact" if assoc.exact_shape_known else
            "unresolved"
        )
        counts[state]+=1
        if state=="unresolved" and len(samples)<20:
            samples.append({
                "seqno": key,
                "drawing_type": str(d.get("type") or ""),
                "level": d.get("level"),
                "item_kinds": [str(i[0]) for i in (d.get("items") or []) if i],
                "assoc_scissor": assoc.scissor,
                "assoc_exact_rect": assoc.exact_rect,
            })
    return {
        "page_number": page_number,
        "table_available": table.available,
        "drawing_count": len(drawings),
        "association_counts": dict(counts),
        "unresolved_samples": samples,
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("pdf",type=Path)
    ap.add_argument("--pages",required=True)
    a=ap.parse_args()
    doc=fitz.open(str(a.pdf))
    try:
        pages=[int(v) for v in a.pages.split(",") if v.strip()]
        print(json.dumps({"pages":[page_stats(doc[p-1],p) for p in pages]},indent=2,sort_keys=True,default=str))
    finally:
        doc.close()

if __name__=="__main__":
    main()
