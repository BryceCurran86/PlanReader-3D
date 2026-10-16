"""Original-source forensic of PLAN insets printed on mixed-elevation sheets.

Diagnoses the first authority stage. Sheet title is resolved separately by
pb_page_title_authority; native local titles and existing F07 segmented
viewports are enumerated without filling unsupported view bounds.

No text, page number, proximity, dimension value, bitmap or drawing scale is
allowed to mint a physical room, dimension endpoint, quantity, floor finish,
elevation correspondence, or new viewport.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

import fitz

from pb_page_title_authority import analyse_page, resolve_document
from pb_viewport_segmentation import (
    extract_view_title_anchors, segment_page_viewports,
    is_authoritative_derived_viewport, validate_non_overlapping_viewports,
)

_NUMBER = re.compile(r"^[1-9][0-9]{1,4}$")
_TITLE_WORDS = frozenset({"PLAN", "ELEVATION", "ELEVATIONS"})


def _finite_rect(raw) -> tuple[float, float, float, float] | None:
    if raw is None or isinstance(raw, (str, bytes)):
        return None
    try:
        b = tuple(float(x) for x in raw)
    except (ValueError, TypeError, OverflowError):
        return None
    if len(b) != 4 or not all(math.isfinite(x) for x in b):
        return None
    return b if b[2] > b[0] and b[3] > b[1] else None


def _original_native_lines(page, page_no: int):
    grouped = {}
    for word in page.get_text("words"):
        if len(word) < 8:
            continue
        box = _finite_rect(word[:4])
        if box is None:
            continue
        try:
            bi, li, ordinal = (int(word[i]) for i in (5, 6, 7))
        except (TypeError, ValueError, OverflowError):
            continue
        if min(bi, li, ordinal) < 0:
            continue
        grouped.setdefault((bi, li), []).append({
            "original_source_native_page": page_no,
            "native_block": bi, "native_line": li,
            "native_word_ordinal": ordinal,
            "raw_text": str(word[4]),
            "bbox_pdf_pts": list(box),
        })
    output = []
    for (bi, li), words in sorted(grouped.items()):
        words.sort(key=lambda x: (x["native_word_ordinal"], x["bbox_pdf_pts"]))
        literal = " ".join(w["raw_text"] for w in words)
        output.append({
            "original_source_page": page_no,
            "source_line_key": [bi, li],
            "native_raw_line_text": literal,
            "native_word_receipts": words,
            "line_has_plan_or_elevation_vocabulary":
                any(w["raw_text"].strip(".,:-").upper() in _TITLE_WORDS for w in words),
            "line_contains_figured_text_candidate":
                any(_NUMBER.fullmatch(w["raw_text"]) for w in words),
            "semantic_dimension_target_authenticated": False,
            "source_line_proves_room_or_viewport": False,
        })
    return output


def _as_token(value):
    item = getattr(value, "value", value)
    return item if type(item) is str else ""


def _all_local_view_evidence(page, page_num: int):
    original_anchors = extract_view_title_anchors(page)
    viewports = segment_page_viewports(page, page_number=page_num)
    return {
        "original_native_view_title_anchors": [
            {"original_title_text": str(a.text),
             "native_title_bbox_pdf_pts": list(a.bbox),
             "native_text_direction": list(a.direction),
             "candidate_native_view_type": _as_token(a.view_type),
             "title_alone_proves_viewport": False}
            for a in original_anchors
        ],
        "existing_f07_viewports": [
            {"view_id": str(v.view_id), "title": str(v.label),
             "view_type": _as_token(v.view_type),
             "status": _as_token(v.status),
             "native_viewport_bbox_pdf_pts":
                 list(v.bounding_box) if v.bounding_box is not None else None,
             "boundary_source": _as_token(v.boundary_source),
             "authoritative_derived": is_authoritative_derived_viewport(v),
             "original_local_view_role_granted_by_this_report": False}
            for v in viewports
        ],
        "production_viewport_bbox_overlaps": validate_non_overlapping_viewports(viewports),
        "new_viewport_authentications": 0,
    }


def audit(source_bytes: bytes, *, expected_sha256: str,
          source_pages=(24, 25, 26, 27)):
    sha = hashlib.sha256(source_bytes).hexdigest()
    if sha != expected_sha256:
        raise ValueError("original-source-sha-mismatch")
    if len(set(source_pages)) != len(source_pages):
        raise ValueError("duplicate-source-page-address")
    with fitz.open(stream=source_bytes, filetype="pdf") as pdf:
        title_analyses = [
            analyse_page(pdf[i], i + 1, allow_ocr=False)
            for i in range(pdf.page_count)
        ]
        titles = resolve_document(title_analyses)
        result = []
        for page_no in source_pages:
            if type(page_no) is not int or page_no < 1 or page_no > len(pdf):
                raise ValueError("source-page-out-of-range")
            page = pdf[page_no - 1]
            sheet = titles[page_no - 1]
            lines = _original_native_lines(page, page_no)
            roles = _all_local_view_evidence(page, page_no)
            sheet_code_candidates = [
                word for line in lines for word in line["native_word_receipts"]
                if re.fullmatch(r"[A-Z]{1,3}[-.]?\d{2,4}(?:\.\d{1,3})?", word["raw_text"].strip(), re.I)
            ]
            field_label_lines = [
                line for line in lines
                if any(token in line["native_raw_line_text"].upper()
                       for token in ("DRAWING NO", "SHEET NO", "SHEET NUMBER", "DWG NO", "DRAWING TITLE"))
            ]
            source_candidates = [
                line for line in lines
                if line["line_has_plan_or_elevation_vocabulary"]
                or line["line_contains_figured_text_candidate"]
            ]
            result.append({
                "original_pdf_page": page_no,
                "native_title_block_sheet_number": sheet.sheet_number,
                "native_title_block_sheet_title": sheet.title,
                "sheet_id_resolution_source": sheet.sheet_number_source,
                "sheet_title_resolution_source": sheet.source,
                "native_original_line_count": len(lines),
                "source_native_sheet_code_word_candidates": sheet_code_candidates,
                "native_title_field_label_line_candidates": field_label_lines,
                "title_reader_page_analysis_sheet_values": list(title_analyses[page_no - 1].sheet_numbers),
                "title_reader_page_analysis_has_title_block": title_analyses[page_no - 1].title_block is not None,
                "original_native_title_block_bbox_pdf_pts": list(title_analyses[page_no - 1].title_block) if title_analyses[page_no - 1].title_block else None,
                "original_native_title_reader_field_labels": [
                    {"source_text": c.text, "kind": c.kind, "source_bbox_rel": list(c.box),
                     "label_strength": c.label_strength, "source_reason": c.reason}
                    for c in title_analyses[page_no - 1].candidates if c.kind == "label"
                ],
                "native_candidate_lines": source_candidates,
                "native_unfiltered_word_count":
                    sum(len(line["native_word_receipts"]) for line in lines),
                **roles,
                "actual_source_endpoint_bracket_binding_proven": False,
                "plan_inset_to_main_floor_physical_room_proven": False,
                "material_finish_application_proven": False,
                "new_metric_room_area_quantity": False,
            })
    return {
        "source_sha256": sha,
        "source_original_pdf_page_count": len(titles),
        "candidate_source_page_universe": list(source_pages),
        "original_mixed_elevation_sheets": result,
        "diagnostic_only": True,
        "new_physical_room_correspondence": 0,
        "new_floor_finish_quantities": 0,
        "new_room_area_quantities": 0,
        "new_customer_rows": 0,
        "uses_frozen_gold": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    opts = parser.parse_args()
    res = audit(opts.pdf.read_bytes(), expected_sha256=opts.sha256)
    opts.output.parent.mkdir(parents=True, exist_ok=True)
    opts.output.write_text(json.dumps(res, sort_keys=True, indent=2) + "\n")
    for sheet in res["original_mixed_elevation_sheets"]:
        native = sheet["native_candidate_lines"]
        titled = [
            line for line in native if line["line_has_plan_or_elevation_vocabulary"]
        ]
        expected_tokens = {"3570", "2200"} if sheet["original_pdf_page"] == 26 else set()
        relevant = [
            line["native_raw_line_text"] for line in native
            if expected_tokens.intersection(w["raw_text"] for w in line["native_word_receipts"])
        ]
        print(json.dumps({
            "original_page": sheet["original_pdf_page"],
            "original_sheet": sheet["native_title_block_sheet_number"],
            "native_candidate_count": len(native),
            "native_sheet_code_words": [w["raw_text"] for w in sheet["source_native_sheet_code_word_candidates"][:30]],
            "native_title_field_label_lines": [v["native_raw_line_text"] for v in sheet["native_title_field_label_line_candidates"][:10]],
            "reader_bound_sheet_values": sheet["title_reader_page_analysis_sheet_values"],
            "reader_has_title_block": sheet["title_reader_page_analysis_has_title_block"],
            "reader_original_title_block_bbox": sheet["original_native_title_block_bbox_pdf_pts"],
            "original_source_A50_codes_and_bboxes": [
                {"text": w["raw_text"], "bbox": w["bbox_pdf_pts"]}
                for w in sheet["source_native_sheet_code_word_candidates"]
                if w["raw_text"] in {"A500", "A501", "A502", "A503"}
            ],
            "source_title_field_binding_candidates": [v["source_reason"] for v in sheet["original_native_title_reader_field_labels"][:12]],
            "printed_local_title_lines": [
                line["native_raw_line_text"] for line in titled[:25]
            ],
            "native_pwd_dimension_lines_unbound": relevant[:25],
            "new_room_area_quantities": 0,
        }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
