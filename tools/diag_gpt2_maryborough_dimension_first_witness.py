"""Fail-closed source-native dimension first-witness audit.

For source discovery only. A dimension token or a vector line is NOT an owned
room dimension. This module never computes room areas, scales, cross-page room
identity, or commercial quantities.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import fitz

from pb_figured_dimension_evidence import (
    extract_dimension_evidence_bundle,
    extract_native_dimension_observations,
)

SOURCE_SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
SCOPED_PAGES_1_BASED = (7, 11, 14, 24, 25, 26, 27, 28)
# Expensive source-vector witness binding is deliberately limited to the
# canonical topology + known support/detail priority sheets.
VECTOR_WITNESS_PAGES_1_BASED = (7, 11, 14)

_ROOM_PATTERN_TEXT = {
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
    "DRY STORE": r"\bDRY\s+STORE\b",
}
ROOM_PATTERNS = {
    label: re.compile(value, flags=re.IGNORECASE)
    for label, value in _ROOM_PATTERN_TEXT.items()
}


def _native_candidate_room_labels(page: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            raw = " ".join(str(span.get("text", "")) for span in line.get("spans", [])).strip()
            if not raw:
                continue
            for label, pattern in ROOM_PATTERNS.items():
                if pattern.search(raw):
                    rows.append({
                        "candidate_label": label,
                        "native_text": raw,
                        "native_bbox_pdf_pts": list(line.get("bbox", ())),
                        "status": "LABEL_CANDIDATE_ONLY",
                    })
    return rows


def inspect_page(page: Any, page_number: int, *, bind_vectors: bool) -> dict[str, Any]:
    """Audit local native text and, optionally, genuine vector witnesses."""
    if bind_vectors:
        bundle = extract_dimension_evidence_bundle(page, page_num=page_number)
        observations = bundle.observations
        bindings = bundle.bindings
        geometry_count = len(bundle.observed_geometry)
    else:
        observations = extract_native_dimension_observations(page, page_num=page_number)
        bindings = ()
        geometry_count = None

    native_dimension_rows = []
    for row in observations:
        native_dimension_rows.append({
            "dimension_id": row.dimension_id,
            "native_text": row.raw_text,
            "value": row.value,
            "unit": row.unit,
            "bbox_pdf_pts": row.bbox,
            "view_id": row.view_id,
            "status": "UNOWNED_FIGURED_DIMENSION_CANDIDATE",
        })
    binding_rows = [
        {
            "dimension_id": b.observation_id,
            "status": str(b.status),
            "dimension_line_id": b.dimension_line_id,
            "witness_line_ids": list(b.witness_line_ids),
            "notes": list(b.notes),
            # Bound geometry still does NOT establish physical room ownership.
            "room_owner_authenticated": False,
        }
        for b in bindings
    ]

    return {
        "page_1_based": page_number,
        "source_room_label_candidates": _native_candidate_room_labels(page),
        "typed_native_dimension_candidates": native_dimension_rows,
        "candidate_count": len(native_dimension_rows),
        "vector_witness_binding_performed": bind_vectors,
        "vector_source_segment_count": geometry_count,
        "dimension_witness_bindings": binding_rows,
        "binding_status_counts": dict(sorted(
            Counter(row["status"] for row in binding_rows).items()
        )),
        "source_owned_room_area_granted": False,
        "cross_view_room_ownership_granted": False,
    }


def source_inventory(source_bytes: bytes, *, expected_sha256: str = SOURCE_SHA) -> dict[str, Any]:
    digest = hashlib.sha256(source_bytes).hexdigest()
    if digest != expected_sha256:
        raise ValueError("SOURCE_SHA_MISMATCH")
    doc = fitz.open(stream=source_bytes, filetype="pdf")
    try:
        if doc.page_count != 31:
            raise ValueError("SOURCE_PAGE_COUNT_MISMATCH")
        rows = [
            inspect_page(
                doc.load_page(page_number - 1),
                page_number,
                bind_vectors=page_number in VECTOR_WITNESS_PAGES_1_BASED,
            )
            for page_number in SCOPED_PAGES_1_BASED
        ]
        return {
            "source_sha256": digest,
            "source_page_count": doc.page_count,
            "scoped_pages_1_based": list(SCOPED_PAGES_1_BASED),
            "vector_witness_pages_1_based": list(VECTOR_WITNESS_PAGES_1_BASED),
            "pages": rows,
            "data_authority": "NATIVE_TEXT_AND_NATIVE_VECTOR_CANDIDATES_ONLY",
            "not_authorised": [
                "physical_room_claim", "cross_view_room_identity",
                "metric_room_area", "physical_scale", "finish_quantity",
                "benchmark_match",
            ],
        }
    finally:
        doc.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = source_inventory(args.pdf.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True, default=str))
    print("GPT2_MARYBOROUGH_DIMENSION_FIRST_WITNESS", json.dumps({
        "source_sha256": result["source_sha256"],
        "pages": [{
            "page_1_based": page["page_1_based"],
            "room_label_candidates": sorted({
                row["candidate_label"] for row in page["source_room_label_candidates"]
            }),
            "typed_dimension_count": page["candidate_count"],
            "binding_counts": page["binding_status_counts"],
            "physical_room_area_granted": False,
        } for page in result["pages"]],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
