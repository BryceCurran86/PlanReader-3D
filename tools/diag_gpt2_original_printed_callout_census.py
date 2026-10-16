"""Original-PDF read-only printed-callout + resolved-title census.

Audit source-side references without source-to-target binding. Produces a
source-SHA-checked JSON review artifact. Never elect a room, wall, opening,
schedule row, finish, or quantity. No benchmark truth is read.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import fitz

from pb_page_title_authority import analyse_page, resolve_document
from pb_cross_sheet_printed_callout_shadow import (
    find_printed_callout_candidates_shadow,
    candidates_for_resolved_sheet_shadow,
)


_NATIVE_SHEET_CODE_LOOKALIKE = re.compile(r"^[A-Z]{1,4}[-.]?\\d{1,4}(?:\\.\\d{1,3})?$", re.I)


def _unbound_native_reference_lines(page, *, page_num: int) -> list[dict]:
    """Retain original neighbouring words for source-format forensics only.

    Standalone title codes, fractions, drawing scales and index references
    have no semantic role here. This cannot promote a sheet/element match.
    """
    rows = {}
    for word in page.get_text("words"):
        if len(word) < 8:
            continue
        try:
            block, line, ordinal = (int(word[i]) for i in (5, 6, 7))
            value = str(word[4]).strip()
            bbox = [float(word[i]) for i in range(4)]
        except (IndexError, TypeError, ValueError):
            continue
        rows.setdefault((block, line), []).append((ordinal, value, bbox))
    candidates = []
    for (block, line), words in sorted(rows.items()):
        words.sort(key=lambda row: (row[0], row[2]))
        hits = [
            (ordinal, value, bbox) for ordinal, value, bbox in words
            if _NATIVE_SHEET_CODE_LOOKALIKE.fullmatch(value)
            or ("/" in value and any(char.isdigit() for char in value))
        ]
        if not hits:
            continue
        candidates.append({
            "source_page": page_num,
            "native_block": block,
            "native_line": line,
            "source_word_ordinal_receipts": [row[0] for row in words],
            "source_line_literal_text": " ".join(row[1] for row in words),
            "candidate_word_boxes": [
                {"word_ordinal": ordinal, "raw_text": value, "bbox": bbox}
                for ordinal, value, bbox in hits
            ],
            "text_or_code_not_physical_correspondence": True,
        })
    return candidates


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
        native_lookalikes = []
        candidates = []
        for i in range(pdf.page_count):
            native_lookalikes.extend(_unbound_native_reference_lines(pdf[i], page_num=i + 1))
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
        "native_unbound_reference_text_lines": native_lookalikes,
        "native_unbound_reference_line_count": len(native_lookalikes),
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
        "unbound_native_lines": result["native_unbound_reference_line_count"],
        "first_native_lines": [row["source_line_literal_text"] for row in result["native_unbound_reference_text_lines"][:15]],
        "new_physical_correspondences": 0,
        "new_signed_construction_quantities": 0,
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
