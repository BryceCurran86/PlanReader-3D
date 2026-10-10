"""Read-only Maryborough room-label source-page coverage inventory.

This is candidate discovery only. Native text and bounding boxes are not
authenticated physical room identities, scales, source dimension witnesses,
canonical metric areas, finish occurrences or quantities. Never publish them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

import fitz

_ROOM_LABEL_PATTERNS = {
    "FREEZER": r"\bFREEZER\b",
    "PWD": r"\bPWD\b",
    "AIRLOCK": r"\bAIRLOCK\b",
    "LAUNDRY": r"\bLAUNDRY\b",
    "SALES": r"\bSALES\b",
    "POS COUNTER": r"\bPOS\s+COUNTER\b",
    "FOOD SERVICE": r"\bFOOD\s+SERVICE\b",
    "WASH UP": r"\bWASH\s+UP\b",
    "TRUCK DRIVER LOUNGE": r"\bTRUCK\s+DRIVER(?:S|S')?\s+LOUNGE\b",
    "M-AMB": r"\bM[ -]?AMB(?:ULANT)?\b",
    "F-AMB": r"\bF[ -]?AMB(?:ULANT)?\b",
}
_COMPILED = {label: re.compile(pattern, re.IGNORECASE) for label, pattern in _ROOM_LABEL_PATTERNS.items()}


def inventory(pdf_bytes: bytes, *, expected_sha256: str) -> dict:
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    if sha != expected_sha256.lower():
        raise RuntimeError("source_sha_mismatch")
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if doc.page_count != 31:
            raise RuntimeError("unexpected_source_page_count")
        found = {name: [] for name in _COMPILED}
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    text = " ".join(str(span.get("text", "")) for span in line.get("spans", [])).strip()
                    if not text:
                        continue
                    for name, pattern in _COMPILED.items():
                        if not pattern.search(text):
                            continue
                        found[name].append({
                            "page_1_based": page_index + 1,
                            "native_bbox_pdf_pts": [float(v) for v in line.get("bbox", ())],
                            "native_text": text,
                            "evidence_stage": "unverified_native_text_candidate",
                        })
        return {
            "source_sha256": sha,
            "page_count": doc.page_count,
            "source_scope": "entire_31_page_document_native_text_only",
            "not_qualified_as": [
                "physical_room", "documented_dimension", "scale",
                "metric_area", "material_occurrence", "quantity",
            ],
            "targets": {
                label: {"native_candidate_count": len(rows), "native_candidates": rows}
                for label, rows in sorted(found.items())
            },
        }
    finally:
        doc.close()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--pdf", type=Path, required=True)
    p.add_argument("--source-sha256", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    report = inventory(args.pdf.read_bytes(), expected_sha256=args.source_sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2))
    print("GPT2_B03_NATIVE_ROOM_MAP", json.dumps({
        "source_sha256": report["source_sha256"],
        "page_count": report["page_count"],
        "labels": {
            label: sorted({r["page_1_based"] for r in row["native_candidates"]})
            for label, row in report["targets"].items()
        },
    }, sort_keys=True))


if __name__ == "__main__":
    main()
