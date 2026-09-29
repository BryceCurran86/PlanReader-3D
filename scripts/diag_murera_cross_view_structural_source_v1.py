#!/usr/bin/env python3
"""TEST-ONLY Murera cross-view structural source census.

Reads only the exact source PDF. It never imports benchmark expectations,
scoring, tolerances, mappings, or expected quantities.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re

import fitz

from pb_viewport_segmentation import segment_page_viewports

TOKEN_RE = re.compile(
    r"\b(?:foundation|layout|floor\s+plan|section|elevation|grid|axis|"
    r"pier|pillar|column|stanchion|chs|masonry|stone|veranda(?:h)?|"
    r"[A-Z]\s*[-/]?\s*\d+)\b",
    re.IGNORECASE,
)


def _bbox(value):
    return [round(float(x), 3) for x in value]


def _candidate_square_glyphs(page, page_number):
    rows = []
    scale_ref = max(1.0, min(float(page.rect.width), float(page.rect.height)))
    max_side = scale_ref * 0.03
    for index, drawing in enumerate(page.get_drawings() or ()):
        rect = drawing.get("rect")
        if rect is None:
            continue
        width = float(rect.width)
        height = float(rect.height)
        if width <= 0.0 or height <= 0.0 or max(width, height) > max_side:
            continue
        aspect = max(width, height) / min(width, height)
        if aspect > 1.35:
            continue
        items = tuple(drawing.get("items") or ())
        kinds = tuple(str(item[0]) for item in items if item)
        rectangular = kinds == ("re",) or (
            len(kinds) == 4 and all(kind == "l" for kind in kinds)
        )
        if not rectangular:
            continue
        rows.append(
            {
                "primitive_id": f"page:{page_number}:drawing:{index}",
                "bbox": _bbox((rect.x0, rect.y0, rect.x1, rect.y1)),
                "center": [
                    round((float(rect.x0) + float(rect.x1)) / 2.0, 3),
                    round((float(rect.y0) + float(rect.y1)) / 2.0, 3),
                ],
                "width": round(width, 3),
                "height": round(height, 3),
                "fill": drawing.get("fill"),
                "item_kinds": kinds,
            }
        )
    return rows


def _axis_line_candidates(page, page_number):
    rows = []
    min_span = max(float(page.rect.width), float(page.rect.height)) * 0.12
    for drawing_index, drawing in enumerate(page.get_drawings() or ()):
        for primitive_index, item in enumerate(drawing.get("items") or ()):
            if not item or str(item[0]) != "l" or len(item) < 3:
                continue
            p1, p2 = item[1], item[2]
            x1, y1 = float(p1.x), float(p1.y)
            x2, y2 = float(p2.x), float(p2.y)
            length = math.hypot(x2 - x1, y2 - y1)
            if length < min_span:
                continue
            dx, dy = abs(x2 - x1), abs(y2 - y1)
            if min(dx, dy) > max(1.0, length * 0.015):
                continue
            rows.append(
                {
                    "primitive_id": (
                        f"page:{page_number}:drawing:{drawing_index}:"
                        f"primitive:{primitive_index}"
                    ),
                    "geometry": [
                        round(x1, 3),
                        round(y1, 3),
                        round(x2, 3),
                        round(y2, 3),
                    ],
                    "orientation": "horizontal" if dx >= dy else "vertical",
                    "length": round(length, 3),
                }
            )
    return rows


def _text_evidence(page):
    rows = []
    for block in page.get_text("blocks") or ():
        text = " ".join(str(block[4] or "").split()).strip()
        if text and TOKEN_RE.search(text):
            rows.append({"text": text, "bbox": _bbox(block[:4])})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--page-start", type=int, default=219)
    parser.add_argument("--page-end", type=int, default=226)
    args = parser.parse_args()

    path = Path(args.pdf)
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    doc = fitz.open(stream=payload, filetype="pdf")
    pages = []
    try:
        for page_number in range(args.page_start, args.page_end + 1):
            page = doc.load_page(page_number - 1)
            viewports = segment_page_viewports(page, page_number=page_number)
            pages.append(
                {
                    "page": page_number,
                    "page_size": [
                        round(float(page.rect.width), 3),
                        round(float(page.rect.height), 3),
                    ],
                    "text_evidence": _text_evidence(page),
                    "viewports": [
                        {
                            "view_id": row.view_id,
                            "view_type": row.view_type,
                            "label": row.label,
                            "status": row.status,
                            "boundary_source": row.boundary_source,
                            "bounding_box": (
                                None
                                if row.bounding_box is None
                                else _bbox(row.bounding_box)
                            ),
                            "scale_denominator": row.scale_denominator,
                            "scale_conflict": row.scale_conflict,
                        }
                        for row in viewports
                    ],
                    "square_glyph_candidates": _candidate_square_glyphs(
                        page, page_number
                    ),
                    "axis_line_candidates": _axis_line_candidates(
                        page, page_number
                    ),
                }
            )
    finally:
        doc.close()

    result = {"source_sha256": digest, "pages": pages}
    Path(args.out).write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "source_sha256": digest,
                "pages": [
                    {
                        "page": row["page"],
                        "viewports": [
                            (v["view_id"], v["view_type"], v["status"])
                            for v in row["viewports"]
                        ],
                        "text_hits": len(row["text_evidence"]),
                        "square_glyphs": len(row["square_glyph_candidates"]),
                        "axis_lines": len(row["axis_line_candidates"]),
                    }
                    for row in pages
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
