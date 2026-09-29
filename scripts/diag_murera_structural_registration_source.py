#!/usr/bin/env python3
"""TEST-ONLY Murera source evidence diagnostic.

Reads source PDF evidence only. Never imports benchmark expected values,
mappings, scorer logic, tolerances, or quantities.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

import fitz

from pb_viewport_segmentation import segment_page_viewports

KEY_RE = re.compile(
    r"\b(?:foundation|floor|plan|section|elevation|grid|axis|pier|pillar|"
    r"column|stanchion|chs|masonry|stone|verandah|veranda|structural)\b",
    re.IGNORECASE,
)


def _clean(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    path = Path(args.pdf)
    payload = path.read_bytes()
    source_sha = hashlib.sha256(payload).hexdigest()
    doc = fitz.open(stream=payload, filetype="pdf")
    rows = []
    try:
        for page_num in range(219, 233):
            page = doc.load_page(page_num - 1)
            text = page.get_text("text")
            lines = [_clean(line) for line in text.splitlines() if _clean(line)]
            keyed_lines = [line for line in lines if KEY_RE.search(line)]

            words = []
            for word in page.get_text("words") or ():
                token = _clean(word[4])
                if token and KEY_RE.search(token):
                    words.append(
                        {
                            "text": token,
                            "bbox": [float(word[0]), float(word[1]), float(word[2]), float(word[3])],
                            "block": int(word[5]),
                            "line": int(word[6]),
                            "word": int(word[7]),
                        }
                    )

            drawings = []
            for index, drawing in enumerate(page.get_drawings() or ()):
                rect = drawing.get("rect")
                if rect is None:
                    continue
                item_kinds = [str(item[0]) for item in (drawing.get("items") or ()) if item]
                drawings.append(
                    {
                        "drawing_index": index,
                        "bbox": [float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)],
                        "width": float(rect.width),
                        "height": float(rect.height),
                        "close_path": bool(drawing.get("closePath")),
                        "item_kinds": item_kinds,
                        "fill": drawing.get("fill"),
                        "color": drawing.get("color"),
                        "line_width": drawing.get("width"),
                    }
                )

            viewports = []
            try:
                for viewport in segment_page_viewports(page, page_number=page_num):
                    viewports.append(
                        {
                            "view_id": str(viewport.view_id),
                            "view_type": str(viewport.view_type),
                            "status": str(viewport.status),
                            "boundary_source": str(viewport.boundary_source),
                            "bounding_box": (
                                None
                                if viewport.bounding_box is None
                                else [float(value) for value in viewport.bounding_box]
                            ),
                        }
                    )
            except Exception as exc:
                viewports = [{"error": f"{type(exc).__name__}:{exc}"}]

            rows.append(
                {
                    "page": page_num,
                    "page_size": [float(page.rect.width), float(page.rect.height)],
                    "keyed_lines": keyed_lines,
                    "keyed_words": words,
                    "viewports": viewports,
                    "drawing_count": len(drawings),
                    "drawings": drawings,
                }
            )
    finally:
        doc.close()

    result = {"source_sha256": source_sha, "pages": rows}
    out = Path(args.out)
    out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps({
        "source_sha256": source_sha,
        "pages": [
            {
                "page": row["page"],
                "keyed_lines": row["keyed_lines"][:30],
                "viewports": row["viewports"],
                "drawing_count": row["drawing_count"],
            }
            for row in rows
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
