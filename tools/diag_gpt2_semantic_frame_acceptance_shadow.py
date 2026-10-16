"""GPT2 read-only F.07 semantic schedule-frame acceptance source trace.

Inspects what the *existing* segmentation already accepted, without recomputing
an alternative frame, moving a title, changing an authority or trusting text.
External CAD schedule captions can be valid: title containment is only a
negative/competing receipt, never an unconditional validity veto.

The candidate must NOT be consumed as a corrected viewport. It cannot mint
a physical ceiling, room, source material or quantity.
"""
from __future__ import annotations

from collections import Counter
import math
from typing import Any


def _bbox(value: object):
    try:
        if isinstance(value, (bytes, str)):
            return None
        numbers = tuple(float(x) for x in value)
    except (TypeError, ValueError, OverflowError):
        return None
    if len(numbers) != 4 or not all(math.isfinite(n) for n in numbers):
        return None
    if numbers[2] <= numbers[0] or numbers[3] <= numbers[1]:
        return None
    return numbers


def _contains(outer: object, inner: object) -> bool:
    a = _bbox(outer)
    b = _bbox(inner)
    return bool(
        a is not None and b is not None
        and a[0] <= b[0] and a[1] <= b[1]
        and a[2] >= b[2] and a[3] >= b[3]
    )


def _word_inventory(page, frame):
    """Retain competing *raw* words, not TRUSTED_PDF_TEXT or table semantics."""
    rows = []
    for word in page.get_text("words"):
        if len(word) < 8:
            continue
        bbox = _bbox(word[:4])
        if bbox is None or not _contains(frame, bbox):
            continue
        rows.append({
            "native_word_address": list(word[5:8]),
            "native_word_bbox_pdf_pts": list(bbox),
            "raw_literal_not_trusted": str(word[4]),
            "source_text_trusted": False,
            "semantic_table_row_owner_proven": False,
        })
    return rows


def _first_gate(*, title_inside: bool, repeated_rect_cells: bool,
                line_grid_positive: bool) -> str:
    """Diagnostic gate taxonomy, never a true/false promotion."""
    if title_inside:
        return "enclosed_title_still_needs_accepted_frame_source_role"
    if repeated_rect_cells:
        return "external_caption_needs_native_table_content_and_title_owner"
    if line_grid_positive:
        return "external_line_grid_may_be_building_or_table_no_content_owner"
    return "external_semantic_title_without_positive_table_content"


def trace_accepted_semantic_frame_sources(
    page: Any, *, page_number: int,
):
    """Inspect production F.07 accepted semantic frames and their dependent bands.

    Proves only which diagnostic predicates/source rectangles were present.
    All real source authority remains in the existing F.07 producer, unchanged.
    """
    if type(page_number) is not int or page_number <= 0:
        raise ValueError("positive_one_based_source_page_required")
    from pb_viewport_segmentation import (
        _SEMANTIC_TABLE_VIEW_TYPES,
        _frame_candidates_for_title,
        _frame_looks_like_line_grid_table,
        _frame_looks_like_table,
        calibrate_viewport_layout,
        extract_vector_frames,
        extract_view_title_anchors,
        segment_page_viewports,
    )

    calibration = calibrate_viewport_layout(page)
    anchors = extract_view_title_anchors(page)
    frames = extract_vector_frames(page, calibration)
    original_views = segment_page_viewports(page, page_number=page_number)
    semantic_rows = []
    all_dependencies = []
    for viewport in original_views:
        provenance = getattr(viewport, "provenance", None) or {}
        separator = provenance.get("separator_view_id")
        if separator:
            all_dependencies.append({
                "dependent_view_id": str(viewport.view_id),
                "reported_view_type": str(viewport.view_type),
                "reported_status": str(viewport.status),
                "reported_viewport_bbox_pdf_pts":
                    list(viewport.bounding_box) if viewport.bounding_box else None,
                "reported_separator_view_id": str(separator),
                "rotated_band_mode": str(provenance.get("partition_mode") or ""),
                "source_positive_semantic_separator_owner_proven_here": False,
            })
        if viewport.view_type not in _SEMANTIC_TABLE_VIEW_TYPES:
            continue
        try:
            anchor_index = int(str(viewport.view_id).rsplit("_", 1)[1]) - 1
        except (TypeError, ValueError, IndexError):
            continue
        if anchor_index < 0 or anchor_index >= len(anchors):
            continue
        anchor = anchors[anchor_index]
        frame = _bbox(viewport.bounding_box)
        row = {
            "reported_semantic_view_id": str(viewport.view_id),
            "reported_semantic_type": str(viewport.view_type),
            "reported_status": str(viewport.status),
            "original_semantic_title_not_trusted": str(anchor.text),
            "original_native_semantic_title_bbox_pdf_pts": list(anchor.bbox),
            "original_native_title_direction": list(anchor.direction),
            "reported_frame_native_bbox_pdf_pts": list(frame) if frame else None,
            "reported_title_inside_frame": _contains(frame, anchor.bbox),
            "semantic_frame_owner_authenticated_by_this_trace": False,
            "source_semantic_table_text_trusted_by_this_trace": False,
            "source_ceiling_quantity_granted": False,
        }
        if frame is not None:
            candidates = _frame_candidates_for_title(
                page, anchor, frames, calibration, anchors=anchors,
            )
            row["candidate_original_frame_rectangles_pdf_pts"] = [
                list(f) for f in candidates
            ]
            row["reported_frame_is_native_frame_candidate"] = any(
                all(abs(x-y) < 1e-6 for x, y in zip(f, frame))
                for f in candidates
            )
            strict_rect = _frame_looks_like_table(
                frame, page, calibration, allow_line_grid_only=False,
            )
            line_grid = _frame_looks_like_line_grid_table(
                frame, page, calibration,
            )
            row["strict_repeated_native_rectangle_cells_candidate"] = bool(strict_rect)
            row["native_line_grid_appearance_candidate"] = bool(line_grid)
            row["first_unclosed_external_table_owner_gate"] = _first_gate(
                title_inside=row["reported_title_inside_frame"],
                repeated_rect_cells=bool(strict_rect),
                line_grid_positive=bool(line_grid),
            )
            row["original_raw_words_inside_reported_frame"] = _word_inventory(
                page, frame,
            )
        semantic_rows.append(row)
    return {
        "source_pdf_page_one_based": page_number,
        "reported_semantic_frame_source_gate_rows": semantic_rows,
        "reported_rotated_separator_dependents": all_dependencies,
        "reported_view_count": len(original_views),
        "original_source_title_anchor_count": len(anchors),
        "original_native_frame_rectangle_count": len(frames),
        "producer_viewports_mutated": False,
        "newly_authorized_viewports": 0,
        "newly_authorized_schedule_table_frames": 0,
        "newly_authorized_room_or_ceiling_material_occurrences": 0,
        "newly_authorized_customer_quantities": 0,
    }



def main() -> int:
    """Produce one immutable-source evidence receipt; never mutate the PDF."""
    import argparse
    from hashlib import sha256
    import json
    from pathlib import Path
    import fitz

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--page", type=int, required=True)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    source = args.pdf.read_bytes()
    digest = sha256(source).hexdigest()
    if digest != args.source_sha256:
        raise ValueError("immutable_source_sha256_mismatch")
    with fitz.open(stream=source, filetype="pdf") as document:
        if args.page < 1 or args.page > len(document):
            raise ValueError("source_page_out_of_range")
        report = trace_accepted_semantic_frame_sources(
            document[args.page - 1], page_number=args.page,
        )
    report["original_pdf_sha256"] = digest
    report["original_bytes_immutable"] = sha256(args.pdf.read_bytes()).hexdigest() == digest
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    for row in report["reported_semantic_frame_source_gate_rows"]:
        print(json.dumps({
            "view": row["reported_semantic_view_id"],
            "caption": row["original_semantic_title_not_trusted"],
            "status": row["reported_status"],
            "claimed_box": row["reported_frame_native_bbox_pdf_pts"],
            "title_inside": row["reported_title_inside_frame"],
            "strict_native_cell_candidate":
                row.get("strict_repeated_native_rectangle_cells_candidate"),
            "native_line_grid_candidate":
                row.get("native_line_grid_appearance_candidate"),
            "first_unclosed_gate": row.get("first_unclosed_external_table_owner_gate"),
        }, sort_keys=True))
    for row in report["reported_rotated_separator_dependents"]:
        print(json.dumps(row, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
