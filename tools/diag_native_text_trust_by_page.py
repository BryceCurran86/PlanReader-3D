"""Read-only census: how many native words does the text-integrity authority trust, per page?

Counts and reason codes only; no word text, file name or coordinate is written. For every page it
classifies each native word twice with the existing producer-owned classifier: default, and with the
merged opt-in proof (original-PDF source-byte -> ToUnicode -> symbol-GID chain plus the raw
no-active-clip proof). The opt-in needs the optional fontTools dependency and abstains without it, so
the report states whether fontTools was importable.

This grants no authority: nothing here is a receipt, a quantity or a score.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path
from typing import Iterable, Optional

import fitz

from pb_pdf_text_integrity_authority import classify_native_word_integrity

OPT_IN = {"source_symbol_font_chain_shadow": True, "source_raw_no_active_text_clip_shadow": True}


def _fonttools_available() -> bool:
    try:
        import fontTools.ttLib  # noqa: F401
    except ImportError:
        return False
    return True


def _word(raw: tuple) -> dict:
    return {"text": raw[4], "bbox": tuple(raw[:4]), "block_no": raw[5], "line_no": raw[6], "word_no": raw[7]}


def census_page(page: fitz.Page) -> dict:
    words = page.get_text("words")
    out = {"words": len(words)}
    for label, kwargs in (("default", {}), ("opt_in", OPT_IN)):
        trusted = 0
        reasons: collections.Counter = collections.Counter()
        for raw in words:
            decision = classify_native_word_integrity(page, _word(raw), **kwargs)
            if decision.trusted:
                trusted += 1
            else:
                reasons.update(decision.reason_codes)
        out[label] = {"trusted": trusted, "reasons": dict(sorted(reasons.items()))}
    return out


def census_pdf(path: Path, pages: Optional[Iterable[int]] = None) -> dict:
    with fitz.open(path) as document:
        wanted = sorted(set(pages)) if pages is not None else list(range(1, document.page_count + 1))
        if any(type(p) is not int or p < 1 or p > document.page_count for p in wanted):
            raise ValueError("page numbers must be 1-based pages of the PDF")
        report = {str(p): census_page(document[p - 1]) for p in wanted}
        rotation = {str(p): int(document[p - 1].rotation) for p in wanted}
    for number, row in report.items():
        row["rotation"] = rotation[number]
    return {
        "schema": "native_text_trust_by_page/1",
        "fonttools_importable": _fonttools_available(),
        "pymupdf": fitz.VersionBind,
        "page_count": len(report),
        "totals": {
            "words": sum(r["words"] for r in report.values()),
            "trusted_default": sum(r["default"]["trusted"] for r in report.values()),
            "trusted_opt_in": sum(r["opt_in"]["trusted"] for r in report.values()),
        },
        "pages": report,
        "authority_granted": False,
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--pages", type=int, nargs="*", default=None, help="1-based pages (default: all)")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = census_pdf(args.pdf, args.pages)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["totals"], sort_keys=True), "fonttools:", result["fonttools_importable"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
