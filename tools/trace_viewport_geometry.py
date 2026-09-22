from __future__ import annotations

import argparse
import json
from pathlib import Path

import fitz

from pb_viewport_segmentation import (
    _frame_candidates_for_title,
    calibrate_viewport_layout,
    extract_vector_frames,
    extract_view_title_anchors,
    segment_page_viewports,
)


def _bbox(value):
    return [round(float(x), 3) for x in value] if value is not None else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--page-number", type=int, required=True)
    args = parser.parse_args()

    doc = fitz.open(str(args.pdf))
    try:
        page = doc[args.page_number - 1]
        calibration = calibrate_viewport_layout(page)
        anchors = extract_view_title_anchors(page)
        frames = extract_vector_frames(page, calibration)
        viewports = segment_page_viewports(page, page_number=args.page_number)
        payload = {
            "page_number": args.page_number,
            "page_rect": _bbox((page.rect.x0, page.rect.y0, page.rect.x1, page.rect.y1)),
            "calibration": {
                "median_word_height_pt": calibration.median_word_height_pt,
                "title_frame_gap_pt": calibration.title_frame_gap_pt,
                "minimum_frame_span_pt": calibration.minimum_frame_span_pt,
                "title_separation_pt": calibration.title_separation_pt,
            },
            "frames": [_bbox(frame) for frame in frames],
            "anchors": [
                {
                    "text": anchor.text,
                    "view_type": anchor.view_type,
                    "bbox": _bbox(anchor.bbox),
                    "center": [round(float(v), 3) for v in anchor.center],
                    "candidate_frames": [
                        _bbox(frame)
                        for frame in _frame_candidates_for_title(
                            anchor, frames, calibration, anchors
                        )
                    ],
                }
                for anchor in anchors
            ],
            "viewports": [
                {
                    "label": viewport.label,
                    "view_type": viewport.view_type,
                    "status": viewport.status,
                    "boundary_source": viewport.boundary_source,
                    "bbox": _bbox(viewport.bounding_box),
                    "title_bbox": _bbox(viewport.title_bbox),
                    "notes": list(viewport.notes),
                }
                for viewport in viewports
            ],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    finally:
        doc.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
