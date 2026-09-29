#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import fitz

from pb_dimension_chain_evidence_extractor import extract_dimension_chains_from_page
from pb_secondary_area_support_evidence import extract_secondary_area_support_evidence_from_page

STRUCTURAL_DEFINITION_RE = re.compile(
    r"\b(?:CHS|RHS|SHS|circular\s+hollow|square\s+hollow|steel|timber|concrete|masonry)"
    r"\b.{0,80}\b(?:pillars?|columns?|posts?|piers?|poles?|stanchions?)\b|"
    r"\b(?:pillars?|columns?|posts?|piers?|poles?|stanchions?)\b.{0,80}"
    r"\b(?:CHS|RHS|SHS|circular\s+hollow|square\s+hollow|steel|timber|concrete|masonry)\b",
    re.IGNORECASE,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf")
    args = parser.parse_args()

    path = Path(args.pdf)
    payload = path.read_bytes()
    source_sha256 = hashlib.sha256(payload).hexdigest()
    doc = fitz.open(stream=payload, filetype="pdf")
    definitions = []
    page_54_support = None
    try:
        for page_num in range(1, len(doc) + 1):
            page = doc.load_page(page_num - 1)
            for block_index, block in enumerate(page.get_text("blocks") or ()):
                text = " ".join(str(block[4]).split()).strip()
                if not text or not STRUCTURAL_DEFINITION_RE.search(text):
                    continue
                definitions.append({
                    "page": page_num,
                    "block_index": block_index,
                    "bbox": [float(v) for v in block[:4]],
                    "text": text,
                })

            if page_num == 54:
                chains = extract_dimension_chains_from_page(
                    page,
                    page_num=54,
                    view_id="page_54",
                )
                support = extract_secondary_area_support_evidence_from_page(
                    page,
                    source_page=54,
                    dimension_chains=chains,
                )
                if support is not None:
                    page_54_support = {
                        "zone_type": support.zone_type,
                        "support_kind": support.support_kind,
                        "support_count": support.support_count,
                        "source_pages": list(support.source_pages),
                        "chain_ids": list(support.chain_ids),
                        "support_symbol_ids": list(support.support_symbol_ids),
                        "evidence_mode": support.evidence_mode,
                        "zone_text": support.zone_text,
                        "support_text": support.support_text,
                    }
    finally:
        doc.close()

    result = {
        "source_sha256": source_sha256,
        "definitions": definitions,
        "page_54_support": page_54_support,
        "trust_boundary": {
            "definitions_create_quantity": False,
            "page_54_support_count_source": "physical_support_symbols_only",
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
