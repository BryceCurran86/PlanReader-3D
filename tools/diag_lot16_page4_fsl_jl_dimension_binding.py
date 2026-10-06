from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz

from pb_drawing_evidence_binding import DrawingViewType
from pb_figured_dimension_evidence import BindingStatus, extract_dimension_evidence_bundle

PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_INDEX=3

def main():
    data=PDF.read_bytes()
    actual=hashlib.sha256(data).hexdigest()
    if actual != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {actual}")
    with fitz.open(stream=data,filetype="pdf") as doc:
        page=doc[PAGE_INDEX]
        words=page.get_text("words") or []
        datum_words=[]
        for item in words:
            if len(item)<8:
                continue
            x0,y0,x1,y1,text,block,line,word_no=item[:8]
            token=str(text).strip().upper().strip(":")
            if token in {"FSL","JL","2100","68560","70660"}:
                datum_words.append({
                    "text":str(text),
                    "token":token,
                    "bbox":[float(x0),float(y0),float(x1),float(y1)],
                    "center":[(float(x0)+float(x1))/2.0,(float(y0)+float(y1))/2.0],
                    "block":int(block),
                    "line":int(line),
                    "word_no":int(word_no),
                })
        bundle=extract_dimension_evidence_bundle(
            page,
            page_num=PAGE_INDEX+1,
            view_id="page:4:lot16-fsl-jl-binding",
            view_type=DrawingViewType.ELEVATION.value,
        )
        binding_by_id={
            str(b.observation_id):b
            for b in bundle.bindings
            if b.status==BindingStatus.WITNESS_BOUND.value
        }
        dims=[]
        for obs in bundle.observations:
            raw=str(getattr(obs,"raw_text","") or "")
            if raw.replace(",","").replace(".","").strip()!="2100":
                continue
            binding=binding_by_id.get(str(obs.dimension_id))
            dims.append({
                "dimension_id":str(obs.dimension_id),
                "raw_text":raw,
                "value":getattr(obs,"value",None),
                "unit":getattr(obs,"unit",None),
                "bbox":list(getattr(obs,"bbox",()) or ()),
                "binding_status":None if binding is None else binding.status,
                "binding_endpoints":None if binding is None or binding.endpoints is None else [
                    [float(binding.endpoints[0][0]),float(binding.endpoints[0][1])],
                    [float(binding.endpoints[1][0]),float(binding.endpoints[1][1])],
                ],
                "dimension_line_id":None if binding is None else str(getattr(binding,"dimension_line_id","") or ""),
                "witness_line_ids":[] if binding is None else list(getattr(binding,"witness_line_ids",()) or ()),
            })
        print(json.dumps({
            "source_sha256":actual,
            "page_id":"4",
            "datum_words":datum_words,
            "dimension_2100":dims,
        },indent=2,sort_keys=True))

if __name__=="__main__":
    main()
