"""Read-only F.07 native vector-frame first-failing-stage census.

Uses the existing F.07 implementation, never creates an alternative frame,
a producer token, a physical opening, a height record or a quantity.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

import pb_viewport_segmentation as f07

SOURCE_ONLY_STATUS = "UNBOUND_F07_ORIGINAL_VECTOR_FRAME_CANDIDATE_AUDIT"


def _bbox(value: Any) -> list[float]:
    return [float(v) for v in value]


def native_frame_gate_audit(page: Any, *, segmentation=f07) -> dict:
    """Audit original F07 decisions without modifying an original PDF/page."""
    calibration = segmentation.calibrate_viewport_layout(page)
    anchors = segmentation.extract_view_title_anchors(page)
    frames = segmentation.extract_vector_frames(page, calibration)
    fragments = segmentation._text_fragments(page)
    drawings = tuple(page.get_drawings() or ())
    opcodes: Counter[str] = Counter()
    path_samples = []
    for path_index, drawing in enumerate(drawings):
        items = drawing.get("items", []) or []
        present = set()
        for item in items:
            if not item:
                continue
            code = str(item[0])
            opcodes[code] += 1
            present.add(code)
        if present.intersection({"re", "qu", "l"}):
            path_samples.append({
                "original_get_drawings_path_index": path_index,
                "drawing_opcode_kinds": sorted(present),
                "item_count": len(items),
                "native_path_rect": (
                    _bbox(drawing["rect"])
                    if drawing.get("rect") is not None else None
                ),
                "closed_flag": bool(drawing.get("closePath", False)),
            })
    audits = []
    for anchor in anchors:
        candidates = segmentation._frame_candidates_for_title(
            page, anchor, frames, calibration, anchors=anchors,
        )
        rejected = [
            segmentation._rejected_ownership_frame(
                page, frame, calibration, fragments, view_type=anchor.view_type,
            )
            for frame in candidates
        ]
        survivors = [frame for frame, bad in zip(candidates, rejected) if not bad]
        collapsed_nested = segmentation._collapse_nested_band_frames(survivors)
        collapsed_equivalent = segmentation._collapse_equivalent_nested_frames(
            collapsed_nested, calibration,
        )
        counts = (len(frames), len(candidates), len(survivors),
                  len(collapsed_nested), len(collapsed_equivalent))
        first_failure = (
            "no_eligible_native_vector_frame" if not frames else
            "no_native_frame_associated_with_original_title" if not candidates else
            "all_original_title_candidate_frames_rejected" if not survivors else
            "competing_or_unproven_frame_title_ownership"
        )
        audits.append({
            "source_title_text": str(anchor.text),
            "source_title_view_type": str(anchor.view_type),
            "source_title_bbox": _bbox(anchor.bbox),
            "source_native_frame_count": len(frames),
            "associated_source_frame_count": len(candidates),
            "nonrejected_associated_source_frame_count": len(survivors),
            "nested_collapse_frame_count": len(collapsed_nested),
            "equivalent_collapse_frame_count": len(collapsed_equivalent),
            "associated_frame_candidates": [
                {
                    "original_native_frame_bbox": _bbox(frame),
                    "rejected_by_existing_f07": bool(bad),
                } for frame, bad in zip(candidates, rejected)
            ],
            "candidate_stage_counts": list(counts),
            "first_failure_if_not_resolved": first_failure,
            "native_vector_frame_authentication_granted": False,
        })
    return {
        "status": SOURCE_ONLY_STATUS,
        "source_only": True,
        "original_native_drawing_path_count": len(drawings),
        "original_drawing_opcode_counts": dict(sorted(opcodes.items())),
        "original_native_candidate_path_summaries": path_samples,
        "all_original_f07_eligible_frame_bboxes": [_bbox(b) for b in frames],
        "original_titles": audits,
        "source_physical_view_correspondence_proven": False,
        "opening_height_granted": False,
        "opening_width_granted": False,
        "opening_host_granted": False,
        "opening_area_granted": False,
        "opening_count_granted": False,
    }


__all__ = ["SOURCE_ONLY_STATUS", "native_frame_gate_audit"]


def main() -> None:
    """Original-source-only standalone CLI. Source mismatch fails before publication."""
    import argparse
    from hashlib import sha256
    import json
    from pathlib import Path

    import fitz

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--page-index", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = args.pdf.read_bytes()
    digest = sha256(payload).hexdigest()
    if digest != args.sha256.lower():
        raise ValueError("source SHA mismatch: no original frame census")
    with fitz.open(stream=payload, filetype="pdf") as original:
        if args.page_index < 0 or args.page_index >= len(original):
            raise ValueError("original native page unavailable")
        result = native_frame_gate_audit(original[args.page_index])
        result["source_sha256"] = digest
        result["source_page_index_zero_based"] = args.page_index
        result["original_pdf_page_count"] = len(original)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    for title in result["original_titles"]:
        print("Original title", title["source_title_text"],
              "stage counts", title["candidate_stage_counts"],
              "first fail", title["first_failure_if_not_resolved"])


if __name__ == "__main__":
    main()
