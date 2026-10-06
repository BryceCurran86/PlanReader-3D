from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz

PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_INDEX=2

def main():
    data=PDF.read_bytes()
    actual=hashlib.sha256(data).hexdigest()
    if actual != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {actual}")
    with fitz.open(stream=data,filetype="pdf") as doc:
        page=doc[PAGE_INDEX]
        words=page.get_text("words") or []
        rows=[]
        for item in words:
            if len(item)<8:
                continue
            x0,y0,x1,y1,text,block,line,word_no=item[:8]
            clean=str(text).strip()
            digits="".join(ch for ch in clean if ch.isdigit())
            upper=clean.upper()
            if digits=="870" or upper in {"CS","DOOR","D","870CS"}:
                rows.append({
                    "text":clean,
                    "bbox":[float(x0),float(y0),float(x1),float(y1)],
                    "block":int(block),
                    "line":int(line),
                    "word_no":int(word_no),
                })
        # Include full native lines containing an 870 token.
        by_line={}
        for item in words:
            if len(item)<8:
                continue
            x0,y0,x1,y1,text,block,line,word_no=item[:8]
            by_line.setdefault((int(block),int(line)),[]).append({
                "text":str(text),
                "bbox":[float(x0),float(y0),float(x1),float(y1)],
                "word_no":int(word_no),
            })
        lines=[]
        for (block,line),items in sorted(by_line.items()):
            ordered=sorted(items,key=lambda x:x["word_no"])
            if any("".join(ch for ch in x["text"] if ch.isdigit())=="870" for x in ordered):
                lines.append({
                    "block":block,
                    "line":line,
                    "text":" ".join(x["text"] for x in ordered),
                    "words":ordered,
                })
    print(json.dumps({
        "source_sha256":actual,
        "page_id":"3",
        "token_hits":rows,
        "line_hits":lines,
        "870_line_count":len(lines),
    },indent=2,sort_keys=True))

if __name__=="__main__":
    main()
