#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import fitz


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf")
    parser.add_argument("--page", type=int, required=True)
    args = parser.parse_args()

    doc = fitz.open(args.pdf)
    try:
        page = doc[args.page - 1]
        print("PAGE_RECT=" + json.dumps([page.rect.x0, page.rect.y0, page.rect.x1, page.rect.y1]))

        keywords = re.compile(r"pier|foundation|300|section|column|pillar|post", re.I)
        text_rows = []
        for block in page.get_text("blocks") or ():
            text = " ".join(str(block[4]).split()).strip()
            if text and keywords.search(text):
                text_rows.append({
                    "bbox": [round(float(v), 3) for v in block[:4]],
                    "text": text,
                })
        print("SOURCE_TEXT_BLOCKS=" + json.dumps(text_rows, sort_keys=True))

        drawings = []
        for index, drawing in enumerate(page.get_drawings() or ()):
            rect = drawing.get("rect")
            if rect is None:
                continue
            width = float(rect.width)
            height = float(rect.height)
            if width <= 0 or height <= 0:
                continue
            aspect = max(width, height) / min(width, height)
            if aspect > 1.30:
                continue
            kinds = [str(item[0]) for item in (drawing.get("items") or ())]
            drawings.append({
                "id": f"page:{args.page}:drawing:{index}",
                "bbox": [round(float(rect.x0), 3), round(float(rect.y0), 3),
                         round(float(rect.x1), 3), round(float(rect.y1), 3)],
                "w": round(width, 3),
                "h": round(height, 3),
                "aspect": round(aspect, 4),
                "fill": drawing.get("fill"),
                "color": drawing.get("color"),
                "width_pt": drawing.get("width"),
                "items": kinds,
            })
        drawings.sort(key=lambda row: (row["w"], row["h"], row["bbox"][1], row["bbox"][0]))
        print("SQUAREISH_DRAWINGS=" + json.dumps(drawings, sort_keys=True))
    finally:
        doc.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
