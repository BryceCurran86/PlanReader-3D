#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re

import fitz


KEYWORDS = re.compile(r"pier|foundation|300|section|column|pillar|post", re.I)


def _rect_tuple(rect):
    return [round(float(rect.x0), 3), round(float(rect.y0), 3),
            round(float(rect.x1), 3), round(float(rect.y1), 3)]


def _primitive_rows(page, page_no: int):
    rows = []
    for drawing_index, drawing in enumerate(page.get_drawings() or ()):
        for item_index, item in enumerate(drawing.get("items") or ()):
            kind = str(item[0])
            if kind == "re":
                rect = item[1]
                w = float(rect.width)
                h = float(rect.height)
                if w <= 0 or h <= 0:
                    continue
                aspect = max(w, h) / min(w, h)
                if aspect <= 1.35:
                    rows.append({
                        "id": f"page:{page_no}:drawing:{drawing_index}:item:{item_index}",
                        "kind": kind,
                        "bbox": _rect_tuple(rect),
                        "w": round(w, 3),
                        "h": round(h, 3),
                        "aspect": round(aspect, 4),
                        "fill": drawing.get("fill"),
                        "color": drawing.get("color"),
                        "stroke_width": drawing.get("width"),
                    })
    return sorted(rows, key=lambda r: (r["w"], r["h"], r["bbox"][1], r["bbox"][0]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf")
    parser.add_argument("--page", type=int, required=True)
    parser.add_argument("--scan-start", type=int)
    parser.add_argument("--scan-end", type=int)
    args = parser.parse_args()

    doc = fitz.open(args.pdf)
    try:
        scan_start = args.scan_start or args.page
        scan_end = args.scan_end or args.page
        scan = []
        for page_no in range(scan_start, scan_end + 1):
            page = doc[page_no - 1]
            text = page.get_text("text") or ""
            matches = sorted({m.group(0).lower() for m in KEYWORDS.finditer(text)})
            relevant_lines = [
                " ".join(line.split())
                for line in text.splitlines()
                if KEYWORDS.search(line)
            ]
            scan.append({
                "page": page_no,
                "matches": matches,
                "relevant_lines": relevant_lines[:80],
                "drawing_count": len(page.get_drawings() or ()),
            })
        print("KEYWORD_PAGE_SCAN=" + json.dumps(scan, sort_keys=True))

        page = doc[args.page - 1]
        print("PAGE_RECT=" + json.dumps(_rect_tuple(page.rect)))

        text_rows = []
        for block in page.get_text("blocks") or ():
            text = " ".join(str(block[4]).split()).strip()
            if text and KEYWORDS.search(text):
                text_rows.append({
                    "bbox": [round(float(v), 3) for v in block[:4]],
                    "text": text,
                })
        print("SOURCE_TEXT_BLOCKS=" + json.dumps(text_rows, sort_keys=True))
        print("SQUAREISH_PRIMITIVE_RECTS=" + json.dumps(
            _primitive_rows(page, args.page), sort_keys=True
        ))
    finally:
        doc.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
