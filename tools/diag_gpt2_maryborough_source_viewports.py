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
    counts = Counter()
    for index in range(len(doc)):
        page_no = index + 1
        viewports = segment_page_viewports(doc[index], page_number=page_no)
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
    }
    Path("maryborough_gpt2_source_viewport_inventory.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, default=str))
