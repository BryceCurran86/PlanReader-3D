"""Original-PDF read-only printed-callout + resolved-title census.

Audit source-side references without source-to-target binding. Produces a
source-SHA-checked JSON review artifact. Never elect a room, wall, opening,
schedule row, finish, or quantity. No benchmark truth is read.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import fitz

from pb_page_title_authority import analyse_page, resolve_document
from pb_cross_sheet_printed_callout_shadow import (
    find_printed_callout_candidates_shadow,
    candidates_for_resolved_sheet_shadow,
)


def census(source_bytes: bytes, *, expected_sha256: str) -> dict:
    observed_sha = hashlib.sha256(source_bytes).hexdigest()
    if observed_sha != expected_sha256:
        raise ValueError("immutable original source PDF digest mismatch")
    with fitz.open(stream=source_bytes, filetype="pdf") as pdf:
        analyses = [analyse_page(pdf[i], i + 1, allow_ocr=False) for i in range(pdf.page_count)]
        titles = resolve_document(analyses)
        # All sheet identities are from the EXISTING labelled title reader;
        # never from page.get_text(words) callouts or page number assumptions.
        sheet_rows = []
        for entry in titles:
            sheet_rows.append({
                "source_page": entry.page_no,
                "title": entry.title,
                "title_evidence_source": entry.source,
                "sheet_number": entry.sheet_number,
                "sheet_number_evidence_source": entry.sheet_number_source,
                "sheet_number_resolved_by_this_diagnostic": False,
            })
        candidates = []
        for i in range(pdf.page_count):
            for item in find_printed_callout_candidates_shadow(pdf[i], page_num=i + 1):
                # Even a single title sheet match is just an unbound lexical
                # code correspondence: never grant physical element identity.
                matched_titles = [
                    row for row in sheet_rows
                    if candidates_for_resolved_sheet_shadow(
                        [item], sheet_number=row["sheet_number"]
                    )
                ]
                candidates.append({
                    "source_page": item.source_page,
                    "printed_callout_mark": item.mark,
                    "printed_referenced_sheet_code": item.referenced_sheet_code,
                    "native_pdf_callout_bbox": list(item.callout_bbox),
                    "candidate_title_sheet_pages_not_physical_correspondence":
                        [row["source_page"] for row in matched_titles],
                    "uniquely_resolved_target_sheet_candidate":
                        len(matched_titles) == 1,
                    "physical_target_identity_granted": False,
                    "source_owned_dimension_endpoint_granted": False,
                })
    return {
        "source_sha256": observed_sha,
        "original_pdf_page_count": len(sheet_rows),
        "title_block_sheet_evidence": sheet_rows,
        "printed_cross_sheet_callout_candidate_ledger": candidates,
        "unbound_literal_reference_count": len(candidates),
        "diagnostic_only": True,
        "new_producer_authored_source_or_viewports": False,
        "new_physical_correspondences": 0,
        "new_signed_construction_quantities": 0,
        "new_customer_rows": 0,
        "uses_frozen_v2_reference": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = census(args.pdf.read_bytes(), expected_sha256=args.sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "source_sha256": result["source_sha256"],
        "pages": result["original_pdf_page_count"],
        "printed_candidates": result["unbound_literal_reference_count"],
        "new_physical_correspondences": 0,
        "new_signed_construction_quantities": 0,
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
