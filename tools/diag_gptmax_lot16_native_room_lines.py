from __future__ import annotations
import hashlib, json, re
from pathlib import Path
import fitz
from pb_source_room_label_authority import _normalized_room_line

PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"

def main():
    raw=PDF.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    doc=fitz.open(stream=raw,filetype="pdf")
    page=doc[2]
    rows=[]
    candidates=[]
    short_alpha=[]
    data=page.get_text("dict")
    for block in data.get("blocks",()):
        for line in block.get("lines",()):
            spans=line.get("spans",())
            text=" ".join(str(s.get("text") or "").strip() for s in spans if str(s.get("text") or "").strip()).strip()
            if not text:
                continue
            bbox=tuple(float(x) for x in line.get("bbox",(0,0,0,0)))
            norm=_normalized_room_line(text)
            row={"text":text,"bbox":bbox,"normalized_room_label":norm}
            rows.append(row)
            if norm:
                candidates.append(row)
            compact=" ".join(text.split())
            if 1 <= len(compact.split()) <= 4 and re.fullmatch(r"[A-Za-z&\- /]+",compact):
                short_alpha.append(row)
    doc.close()
    print(json.dumps({
        "page":3,
        "normalized_room_candidate_count":len(candidates),
        "normalized_room_candidates":candidates,
        "short_alpha_line_count":len(short_alpha),
        "short_alpha_lines":short_alpha,
    },indent=2,sort_keys=True))

if __name__=="__main__":
    main()
