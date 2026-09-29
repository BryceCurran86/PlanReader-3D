#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path
import fitz

from pb_dimension_chain_evidence_extractor import extract_dimension_chains_from_page
import pb_secondary_area_support_evidence as support

PATTERN=re.compile(r"\b(?:CHS|SHS|RHS|pillar|pillars|pier|piers|column|columns|post|posts)\b", re.I)

def chain_payload(chain):
    return {
        "chain_id":str(chain.chain_id),
        "orientation":str(chain.orientation),
        "values_m":[float(o.value_m) for o in chain.observations],
        "bboxes":[list(o.bbox) if o.bbox is not None else None for o in chain.observations],
    }

def page_census(pdf_path, page_number):
    doc=fitz.open(str(pdf_path))
    try:
        page=doc[page_number-1]
        blocks=[
            {"text":" ".join(str(b[4]).split()),"bbox":[float(v) for v in b[:4]]}
            for b in (page.get_text("blocks") or ())
            if PATTERN.search(str(b[4]))
        ]
        chains=extract_dimension_chains_from_page(
            page,page_num=page_number,view_id=f"page_{page_number}"
        )
        evidence=support.extract_secondary_area_support_evidence_from_page(
            page,source_page=page_number,dimension_chains=chains
        )
        glyphs=support._physical_support_glyphs(page,source_page=page_number)
        return {
            "page":page_number,
            "support_text_blocks":blocks,
            "dimension_chains":[chain_payload(c) for c in chains],
            "physical_support_glyphs":[
                {
                    "glyph_id":g.glyph_id,
                    "bbox":list(g.bbox),
                    "center":[g.center_x,g.center_y],
                    "width":g.width,"height":g.height,
                } for g in glyphs
            ],
            "current_secondary_support_evidence":(
                None if evidence is None else {
                    "zone_type":evidence.zone_type,
                    "support_kind":evidence.support_kind,
                    "support_count":evidence.support_count,
                    "bay_count":evidence.bay_count,
                    "bay_spans_m":list(evidence.bay_spans_m),
                    "source_pages":list(evidence.source_pages),
                    "chain_ids":list(evidence.chain_ids),
                    "zone_text":evidence.zone_text,
                    "support_text":evidence.support_text,
                    "support_symbol_ids":list(evidence.support_symbol_ids),
                    "evidence_mode":evidence.evidence_mode,
                    "confidence":evidence.confidence,
                }
            ),
        }
    finally:
        doc.close()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--kstvet",required=True)
    ap.add_argument("--murera",required=True)
    args=ap.parse_args()
    out={
        "kstvet":page_census(Path(args.kstvet),54),
        "murera":page_census(Path(args.murera),225),
    }
    print(json.dumps(out,indent=2,sort_keys=True))

if __name__=="__main__":
    main()
