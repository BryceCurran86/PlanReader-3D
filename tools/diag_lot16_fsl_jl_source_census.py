from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

import fitz

from pb_figured_dimension_evidence import extract_dimension_evidence_bundle
from pb_drawing_evidence_binding import DrawingViewType

PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"

TOKENS=("FSL","JL","JAMB","HEAD","2100","HEIGHT","DOOR","DOORS")

def norm(text):
    return "".join(ch.upper() if ch.isalnum() else " " for ch in str(text)).split()

def main():
    data=PDF.read_bytes()
    actual=hashlib.sha256(data).hexdigest()
    if actual != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {actual}")

    pages=[]
    with fitz.open(stream=data,filetype="pdf") as doc:
        for index in range(int(doc.page_count)):
            page=doc[index]
            words=page.get_text("words") or []
            by_line=defaultdict(list)
            for item in words:
                if len(item)<8:
                    continue
                x0,y0,x1,y1,text,block,line,word_no=item[:8]
                by_line[(int(block),int(line))].append({
                    "text":str(text),
                    "bbox":[float(x0),float(y0),float(x1),float(y1)],
                    "word_no":int(word_no),
                })
            line_hits=[]
            for (block,line),items in sorted(by_line.items()):
                ordered=sorted(items,key=lambda x:x["word_no"])
                text=" ".join(x["text"] for x in ordered)
                upper=" ".join(norm(text))
                matched=[token for token in TOKENS if token in upper.split()]
                # Keep exact numeric 2100 and any FSL/JL/jamb/head line.
                if not matched:
                    continue
                if not (
                    "FSL" in matched or "JL" in matched or "JAMB" in matched
                    or "HEAD" in matched or "2100" in matched
                ):
                    continue
                line_hits.append({
                    "block":block,
                    "line":line,
                    "text":text,
                    "matched_tokens":matched,
                    "words":ordered,
                })

            dimension_hits=[]
            if line_hits:
                try:
                    bundle=extract_dimension_evidence_bundle(
                        page,
                        page_num=index+1,
                        view_id=f"page:{index+1}:lot16-fsl-jl-diag",
                        view_type=DrawingViewType.ELEVATION.value,
                    )
                except Exception as exc:
                    dimension_hits=[{"error":type(exc).__name__,"message":str(exc)}]
                else:
                    for obs in bundle.observations:
                        raw=str(getattr(obs,"raw_text","") or "")
                        if "2100" not in raw.replace(",","").replace(".",""):
                            continue
                        dimension_hits.append({
                            "dimension_id":str(getattr(obs,"dimension_id","")),
                            "raw_text":raw,
                            "value":getattr(obs,"value",None),
                            "unit":getattr(obs,"unit",None),
                            "bbox":list(getattr(obs,"bbox",()) or ()),
                        })
            if line_hits or dimension_hits:
                pages.append({
                    "page_id":str(index+1),
                    "line_hits":line_hits,
                    "dimension_2100_hits":dimension_hits,
                })

    print(json.dumps({
        "source_sha256":actual,
        "page_count_with_hits":len(pages),
        "pages":pages,
    },indent=2,sort_keys=True))

if __name__=="__main__":
    main()
