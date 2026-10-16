"""Read-only overlay of the structural wall-ink shadow on an original PDF page.

Draws accepted network ink (red), unproven paired ink (blue), the sheet frame / dashed / outlined-glyph negatives
(orange / grey / purple) over a faded render of the page and writes a JSON summary. It never writes to the PDF
or the repository checkout and publishes no authority.

Usage: python -m tools.diag_structural_wall_ink_overlay --pdf FILE --page 3 --png OUT.png --json OUT.json
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

import fitz

from pb_structural_wall_ink_shadow import (
    NOT_WALL_INK,
    REASON_DASHED_OR_PATTERNED,
    REASON_OUTLINED_GLYPH_RUN,
    REASON_SHEET_FRAME_RING,
    UNPROVEN,
    WALL_NETWORK_INK_CANDIDATE,
    classify_structural_wall_ink,
)
from pb_vector_geometry_v130 import extract_native_page

COLORS = {
    WALL_NETWORK_INK_CANDIDATE: (220, 0, 0),
    REASON_SHEET_FRAME_RING: (255, 150, 0),
    REASON_OUTLINED_GLYPH_RUN: (150, 0, 200),
    REASON_DASHED_OR_PATTERNED: (140, 140, 140),
}


def run(pdf: Path, page_number: int, png: Path | None, summary_path: Path | None, dpi: int = 110) -> dict:
    document = fitz.open(str(pdf))
    page = document[page_number - 1]
    native = extract_native_page(page)
    segments = native["segments"]
    report = classify_structural_wall_ink(segments, page_width=page.rect.width, page_height=page.rect.height)
    by_class = Counter(d.classification for d in report.decisions)
    reasons = Counter(r for d in report.decisions for r in d.reason_codes)
    summary = {
        "page": page_number,
        "segments": len(segments),
        "classification_counts": dict(by_class),
        "reason_counts": dict(reasons),
        "network_count": report.network_count,
        "darkest_ink_color": report.darkest_ink_color,
        "ink_class_table": [
            {"ink_class": list(r.ink_class), "segments": r.segment_count, "length_pt": r.total_length_pt,
             "network_candidates": r.candidate_segment_count} for r in report.class_table[:12]
        ],
        "shadow_only": report.shadow_only,
        "live_effect": report.live_effect,
        "wall_authority_granted": report.wall_authority_granted,
    }
    if summary_path is not None:
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    if png is not None:
        import numpy as np
        from PIL import Image, ImageDraw

        zoom = dpi / 72
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        faded = 255 - (255 - np.asarray(image).astype("float32")) * 0.15
        image = Image.fromarray(faded.astype("uint8"))
        draw = ImageDraw.Draw(image)
        index = {d.source_primitive_id: d for d in report.decisions}
        # Native segment geometry is in the unrotated page frame; the render is in the displayed (rotated) frame.
        to_view = page.rotation_matrix
        for segment in segments:
            decision = index.get(str(segment.get("id")))
            if decision is None:
                continue
            if decision.classification == WALL_NETWORK_INK_CANDIDATE:
                color = COLORS[WALL_NETWORK_INK_CANDIDATE]
            elif decision.classification == NOT_WALL_INK:
                color = COLORS.get(decision.reason_codes[0], (0, 0, 0))
            elif REASON_NO_PARTNER_PAIRED in decision.reason_codes:
                color = (0, 120, 255)
            else:
                continue
            p1 = fitz.Point(segment["x1"], segment["y1"]) * to_view
            p2 = fitz.Point(segment["x2"], segment["y2"]) * to_view
            draw.line([(p1.x * zoom, p1.y * zoom), (p2.x * zoom, p2.y * zoom)], fill=color, width=2)
        image.save(str(png))
    return summary


REASON_NO_PARTNER_PAIRED = "paired_island_below_network_extent"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page", type=int, required=True, help="1-based page number")
    parser.add_argument("--png", type=Path)
    parser.add_argument("--json", type=Path, dest="summary")
    parser.add_argument("--dpi", type=int, default=110)
    args = parser.parse_args()
    for target in (args.png, args.summary):
        if target is not None:
            target.parent.mkdir(parents=True, exist_ok=True)
    print(json.dumps(run(args.pdf, args.page, args.png, args.summary, args.dpi), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
