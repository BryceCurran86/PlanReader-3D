"""Diagnostic-only source viewport inventory; cannot grant production authority."""
from __future__ import annotations
import hashlib
import json
from collections import Counter
from pathlib import Path
import fitz
from pb_drawing_evidence_binding import DrawingViewType
from pb_viewport_segmentation import (
    is_authoritative_derived_viewport, segment_page_viewports,
    validate_non_overlapping_viewports,
    calibrate_viewport_layout, extract_vector_frames,
    extract_view_title_anchors, _frame_candidates_for_title,
    _frame_looks_like_table,
)

SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
if __name__ == "__main__":
    if not SOURCE.is_file():
        raise SystemExit(f"SOURCE PDF UNAVAILABLE: {SOURCE}")
    payload = SOURCE.read_bytes()
    doc = fitz.open(stream=payload, filetype="pdf")
    target_types = {
        DrawingViewType.REFLECTED_CEILING_PLAN.value,
        DrawingViewType.FLOOR_FINISH_PLAN.value,
        DrawingViewType.SCHEDULE.value,
        DrawingViewType.LEGEND.value,
        DrawingViewType.SPECIFICATION.value,
    }
    results = []
    frame_diagnostics = []
    counts = Counter()
    for index in range(len(doc)):
        page_no = index + 1
        viewports = segment_page_viewports(doc[index], page_number=page_no)
        if page_no in (1, 9, 11, 30):
            page = doc[index]
            calibration = calibrate_viewport_layout(page)
            frames = extract_vector_frames(page, calibration)
            anchors = extract_view_title_anchors(page)
            for anchor in anchors:
                if anchor.view_type not in target_types:
                    continue
                candidates = _frame_candidates_for_title(
                    page, anchor, frames, calibration, anchors=anchors
                )
                frame_diagnostics.append({
                    'source_page': page_no, 'title': anchor.text,
                    'type': anchor.view_type, 'native_title_bbox': anchor.bbox,
                    'native_direction': anchor.direction,
                    'candidate_frames': candidates,
                    'candidate_table_proof': [
                        _frame_looks_like_table(frame, page, calibration)
                        for frame in candidates
                    ],
                    'native_frame_count': len(frames),
                    'calibrated_min_span_pt': calibration.minimum_frame_span_pt,
                })
        nonoverlap = validate_non_overlapping_viewports(viewports)
        for viewport in viewports:
            if viewport.view_type not in target_types:
                continue
            authoritative = (
                viewport.status == "resolved" and viewport.bounding_box is not None
            ) or is_authoritative_derived_viewport(viewport)
            counts[(viewport.view_type, viewport.status)] += 1
            results.append({
                "source_page": page_no,
                "view_id": viewport.view_id,
                "title": viewport.label,
                "view_type": viewport.view_type,
                "status": viewport.status,
                "authoritative": bool(authoritative and nonoverlap),
                "native_bbox": viewport.bounding_box,
                "notes": viewport.notes,
                "provenance": viewport.provenance,
                "page_viewport_nonoverlap": nonoverlap,
            })
    doc.close()
    report = {
        "source_sha256": hashlib.sha256(payload).hexdigest(),
        "page_count": page_no,
        "counts": [{"type": k[0], "status": k[1], "count": v} for k, v in sorted(counts.items())],
        "viewports": results,
        "target_page_frame_diagnostics": frame_diagnostics,
    }
    Path("maryborough_gpt2_source_viewport_inventory.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, default=str))
