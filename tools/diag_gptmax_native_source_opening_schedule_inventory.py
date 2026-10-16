"""Read-only native PDF opening-tag and schedule source inventory.

For source-first investigation ONLY. Native text and nearby numeric labels
are untrusted candidates; they cannot establish an opening instance, host,
schedule-row authority, height, metric area or customer quantity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import fitz


def native_source_text_inventory(pdf_bytes: bytes) -> dict:
    if not isinstance(pdf_bytes, bytes) or not pdf_bytes:
        raise ValueError("original immutable PDF bytes required")
    source_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        pages = []
        for index, page in enumerate(pdf):
            rows = []
            for raw in page.get_text("words", sort=False):
                x0, y0, x1, y1, token, block, line, word = raw[:8]
                if not (isinstance(token, str) and token):
                    continue
                rows.append({
                    "bbox_pdf_pts": [round(float(q), 6) for q in (x0, y0, x1, y1)],
                    "text": token,
                    "block": int(block),
                    "line": int(line),
                    "word": int(word),
                })
            if any(v["bbox_pdf_pts"][2] <= v["bbox_pdf_pts"][0]
                   or v["bbox_pdf_pts"][3] <= v["bbox_pdf_pts"][1]
                   for v in rows):
                raise ValueError("native text zero-area source address")
            pages.append({
                "page_id": str(index + 1),
                "page_rotation": int(page.rotation),
                "page_rect_pdf_pts": [float(page.rect.x0), float(page.rect.y0),
                                      float(page.rect.x1), float(page.rect.y1)],
                "word_count": len(rows),
                "source_native_words": rows,
            })
        return {
            "source_sha256": source_sha256,
            "source_page_count": len(pages),
            "pages": pages,
            "original_native_text_is_not_an_authenticated_opening_tag": True,
            "opening_instance_bound": False,
            "opening_height_granted": False,
            "physical_host_granted": False,
            "customer_quantity_granted": False,
            "benchmark_accuracy_granted": False,
        }
    finally:
        pdf.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = native_source_text_inventory(args.pdf.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2)+"\n",
                           encoding="utf-8")
    print(json.dumps({"source_sha256":report["source_sha256"],
                      "pages":report["source_page_count"],
                      "source_native_words":sum(p["word_count"] for p in report["pages"]),
                      "physical_quantity_granted":False},sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
