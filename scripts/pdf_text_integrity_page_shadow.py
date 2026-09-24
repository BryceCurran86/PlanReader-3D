"""Real-source shadow: per-reason PdfTextIntegrity classification of one page.

Diagnostic only. Reads a PDF and prints, for every native word on one page, how
many words are trusted and which reason codes block the rest, plus the embedded
font programs behind glyph-verification blocks. No benchmark quantity, expected
BOQ value, live extractor or commercial output is read or changed.

usage: pdf_text_integrity_page_shadow.py <pdf> <1-based page number>
"""
from __future__ import annotations

import collections
import json
from pathlib import Path
import re
import sys

import fitz

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pb_pdf_text_integrity_authority import (  # noqa: E402
    TEXT_GLYPH_MAPPING_UNVERIFIED,
    classify_native_word_integrity,
)


def _font_programs(doc: fitz.Document, page: fitz.Page) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for font in page.get_fonts(full=True):
        xref, subtype, base = int(font[0]), str(font[2]), str(font[3])
        info: dict[str, object] = {"subtype": subtype, "descendant": None, "font_file": None}
        match = re.search(r"DescendantFonts\s*\[\s*(\d+)", doc.xref_object(xref))
        target = int(match.group(1)) if match else xref
        if match:
            info["descendant"] = doc.xref_get_key(target, "Subtype")[1]
        descriptor = doc.xref_get_key(target, "FontDescriptor")
        if descriptor[0] == "xref":
            fd = int(descriptor[1].split()[0])
            for key in ("FontFile", "FontFile2", "FontFile3"):
                if doc.xref_get_key(fd, key)[0] != "null":
                    info["font_file"] = key
        out[base] = info
    return out


def run(pdf_path: Path, page_number: int) -> dict[str, object]:
    doc = fitz.open(str(pdf_path))
    page = doc[page_number - 1]
    reasons: collections.Counter[str] = collections.Counter()
    glyph_only_by_font: collections.Counter[str] = collections.Counter()
    trusted = 0
    words = page.get_text("words")
    for word in words:
        decision = classify_native_word_integrity(
            page, {"text": word[4], "bbox": tuple(word[:4])}
        )
        trusted += bool(decision.trusted)
        reasons.update(decision.reason_codes)
        if set(decision.reason_codes) == {TEXT_GLYPH_MAPPING_UNVERIFIED}:
            glyph_only_by_font[decision.font_name] += 1
    return {
        "page": page_number,
        "words": len(words),
        "trusted": trusted,
        "reason_counts": dict(reasons),
        "blocked_only_by_glyph_mapping_unverified_by_font": dict(glyph_only_by_font),
        "font_programs": _font_programs(doc, page),
    }


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    print(json.dumps(run(Path(sys.argv[1]), int(sys.argv[2])), indent=2, sort_keys=True))
