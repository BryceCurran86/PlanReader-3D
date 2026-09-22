from __future__ import annotations

import argparse
import json
from pathlib import Path

import fitz


def _rect(value):
    if value is None:
        return None
    try:
        return [round(float(value.x0),3), round(float(value.y0),3), round(float(value.x1),3), round(float(value.y1),3)]
    except Exception:
        try:
            return [round(float(x),3) for x in value]
        except Exception:
            return str(value)


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--pages", required=True)
    args=ap.parse_args()
    doc=fitz.open(str(args.pdf))
    payload={"pages":[]}
    try:
        for pno in [int(x) for x in args.pages.split(",") if x.strip()]:
            page=doc[pno-1]
            rows=[]
            drawings=page.get_drawings(extended=True) or []
            for idx,d in enumerate(drawings):
                dtype=str(d.get("type") or "")
                if not dtype.startswith("clip"):
                    continue
                items=[]
                for item in d.get("items",[]) or []:
                    row={"kind":str(item[0]) if item else None}
                    if item and len(item)>1:
                        v=item[1]
                        if hasattr(v,"x0") and hasattr(v,"y0") and hasattr(v,"x1") and hasattr(v,"y1"):
                            row["shape"]=_rect(v)
                        elif hasattr(v,"x") and hasattr(v,"y"):
                            row["shape"]=[round(float(v.x),3),round(float(v.y),3)]
                        else:
                            row["shape"]=str(v)
                    if item and len(item)>2:
                        v=item[2]
                        if hasattr(v,"x") and hasattr(v,"y"):
                            row["end"]=[round(float(v.x),3),round(float(v.y),3)]
                        else:
                            row["end"]=str(v)
                    items.append(row)
                rows.append({
                    "index":idx,
                    "type":dtype,
                    "level":d.get("level"),
                    "seqno":d.get("seqno"),
                    "rect":_rect(d.get("rect")),
                    "scissor":_rect(d.get("scissor")),
                    "closePath":d.get("closePath"),
                    "items":items[:20],
                    "item_count":len(d.get("items",[]) or []),
                })
            payload["pages"].append({"page_number":pno,"clip_entries":rows,"clip_count":len(rows)})
    finally:
        doc.close()
    print(json.dumps(payload,indent=2,sort_keys=True,default=str))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
