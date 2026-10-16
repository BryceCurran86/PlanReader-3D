"""Read-only original F.07 view-membership audit for native opening marks.

Original labels and figured words cannot grant a structural host, physical
cross-sheet identity, dimension, count or customer quantity.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable, Sequence

from diag_gptmax_cross_view_native_marks import native_phrase_occurrences

STATUS = "UNBOUND_NATIVE_F07_VIEWPORT_MEMBERSHIP_CENSUS"


def _fits(box: Sequence[float], parent: Sequence[float] | None) -> bool:
    if parent is None or len(parent) != 4 or len(box) != 4:
        return False
    return all(float(box[i]) >= float(parent[i]) for i in (0, 1)) and all(
        float(box[i]) <= float(parent[i]) for i in (2, 3)
    )


def _phrase_rows(words, phrase: str) -> list[dict]:
    return [dict(row, phrase=phrase) for row in native_phrase_occurrences(words, phrase)]


def _viewport_row(view: Any, valid: bool) -> dict:
    bbox = getattr(view, "bounding_box", None)
    return {
        "view_id": str(view.view_id),
        "view_type": str(view.view_type),
        "label": str(view.label),
        "status": str(view.status),
        "boundary_source": str(view.boundary_source),
        "bbox_pdf_pt": list(bbox) if bbox is not None else None,
        "original_f07_producer_token_valid": bool(valid),
    }


def _stamp_scope(rows: list[dict], views: list[dict]) -> list[dict]:
    for row in rows:
        contained = [
            v for v in views
            if _fits(row["envelope_pdf_pt"], v["bbox_pdf_pt"])
        ]
        eligible = [
            v for v in contained if v["status"] == "resolved"
            and v["boundary_source"] == "vector_frame"
            and v["original_f07_producer_token_valid"]
        ]
        has_competing_scope = sum(
            v["status"] in {"resolved", "derived"} for v in contained
        ) != 1
        accepted = len(eligible) == 1 and not has_competing_scope
        row["fully_containing_view_ids"] = sorted(v["view_id"] for v in contained)
        row["resolved_f07_vector_frame_view_id"] = (
            eligible[0]["view_id"] if accepted else None
        )
        row["viewport_membership_reason"] = (
            "unique_original_f07_frame_contains_complete_native_bbox"
            if accepted else "unproven_or_ambiguous_f07_native_bbox_owner"
        )
        row["physical_opening_identity_proven"] = False
        row["dimension_anchor_bound_to_opening"] = False
    return rows


def census_pages(document: Any, *, page_indices: Sequence[int], phrase: str,
                 datum_tokens: Sequence[str], segment: Callable,
                 is_f07_record: Callable[[Any], bool],
                 resolved_titles: Sequence[Any] = ()) -> dict:
    if not page_indices or len(set(page_indices)) != len(page_indices):
        raise ValueError("page indices must be distinct, nonempty")
    if not str(phrase).strip():
        raise ValueError("phrase must be nonempty")
    pages = []
    for index in sorted(page_indices):
        if index < 0 or index >= len(document):
            raise ValueError("source PDF page unavailable")
        page = document[index]
        views = segment(page, page_number=index + 1)
        descriptors = [_viewport_row(v, is_f07_record(v)) for v in views]
        if len({v["view_id"] for v in descriptors}) != len(descriptors):
            raise ValueError("non-unique original F07 view identity")
        words = page.get_text("words")
        marks = _stamp_scope(_phrase_rows(words, phrase), descriptors)
        datums = {
            word.upper(): _stamp_scope(_phrase_rows(words, word), descriptors)
            for word in sorted({
                str(x).strip().upper() for x in datum_tokens if str(x).strip()
            })
        }
        title = resolved_titles[index] if resolved_titles else None
        pages.append({
            "pdf_page_index_zero_based": index,
            "producer_page_number_one_based": index + 1,
            "page_title_from_existing_authority": getattr(title, "title", "") or "",
            "source_title_block_sheet_code": getattr(title, "sheet_number", "") or "",
            "title_evidence_source": getattr(title, "source", "") or "",
            "viewports": descriptors,
            "mark_occurrences": marks,
            "datum_token_occurrences": datums,
        })
    return {
        "status": STATUS,
        "source_evidence_only": True,
        "f07_viewport_records_read_only": True,
        "no_promoted_record": True,
        "requested_page_indices": sorted(page_indices),
        "pages": pages,
        "cross_sheet_physical_identity_proven": False,
        "specific_opening_dimension_binding_proven": False,
        "opening_host_proven": False,
        "opening_kind_proven": False,
        "opening_count_proven": False,
        "firm_quantity_granted": False,
    }


def original_source_report(path: Path, *, expected_sha256: str,
                           page_indices: Sequence[int], phrase: str,
                           datum_tokens: Sequence[str]) -> dict:
    import fitz
    import pb_page_title_authority as title_authority
    from pb_viewport_segmentation import (
        is_segment_page_viewports_product,
        segment_page_viewports,
    )

    data = Path(path).read_bytes()
    digest = sha256(data).hexdigest()
    if digest != expected_sha256.lower():
        raise ValueError("original PDF source SHA256 mismatch")
    with fitz.open(stream=data, filetype="pdf") as doc:
        title_records = title_authority.resolve_document([
            title_authority.analyse_page(page, index + 1, allow_ocr=False)
            for index, page in enumerate(doc)
        ])
        result = census_pages(
            doc, page_indices=page_indices, phrase=phrase,
            datum_tokens=datum_tokens, segment=segment_page_viewports,
            is_f07_record=is_segment_page_viewports_product,
            resolved_titles=title_records,
        )
        result["source_sha256"] = digest
        result["source_total_pdf_pages"] = len(doc)
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--page-indices", nargs="+", type=int, required=True)
    parser.add_argument("--phrase", required=True)
    parser.add_argument("--datum-tokens", nargs="*", default=())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = original_source_report(
        args.pdf, expected_sha256=args.sha256, page_indices=args.page_indices,
        phrase=args.phrase, datum_tokens=args.datum_tokens,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8",
    )
    for page in report["pages"]:
        print(
            "PDF index", page["pdf_page_index_zero_based"],
            "F07 view count", len(page["viewports"]),
            "mark occurrences", len(page["mark_occurrences"]),
        )
        for mark in page["mark_occurrences"]:
            print("mark scoped to", mark["resolved_f07_vector_frame_view_id"],
                  mark["viewport_membership_reason"])


if __name__ == "__main__":
    main()
