"""Source-only Q5446 vector-glyph title OCR proof (NOT a page-role grant).

The original PDF prints the sheet title as vector outlines, so its native
word layer sees only DocuSign. OCR is strictly restricted to the title block,
and its output cannot substitute for producer-positive sheet-role authority.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import argparse
import json
import re
import subprocess

import fitz

SHA = "5f29aa0122d72e2cc8886b3f19239ff32865c8d705eee99f785c389ca27fb7f0"
REQUIRED_TITLES = ("GROUND FLOOR PLAN", "FIRST FLOOR PLAN")
SHEET_TITLE = fitz.Rect(595, 725, 885, 813)
CAP = 20_000


def title_from_ocr_text(text: str, expected: str) -> str | None:
    # Accept neither ambiguous unrelated text nor an OCR title without its
    # source sheet's explicitly printed View field.
    upper = " ".join(re.findall(r"[A-Z]+", text.upper()))
    count = len(re.findall(r"\b" + re.escape(expected) + r"\b", upper))
    other = [t for t in REQUIRED_TITLES if t != expected
             and re.search(r"\b" + re.escape(t) + r"\b", upper)]
    if count != 1 or other or "VIEW" not in upper:
        return None
    return expected


def _ocr_cropped_native_title(page) -> str:
    crop = page.get_pixmap(matrix=fitz.Matrix(3, 3), clip=SHEET_TITLE, alpha=False)
    try:
        call = subprocess.run(
            ["tesseract", "stdin", "stdout", "--psm", "6"],
            input=crop.tobytes("png"), capture_output=True, timeout=15, check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(
            "bounded title OCR unavailable; source page role must abstain"
        ) from exc
    if call.returncode:
        raise RuntimeError("bounded title OCR failed; source page role must abstain")
    return call.stdout.decode("utf-8", errors="replace")


def source_title_candidates(original_pdf: bytes, *, ocr=_ocr_cropped_native_title):
    if type(original_pdf) is not bytes or sha256(original_pdf).hexdigest() != SHA:
        raise ValueError("SHA-verified original Q5446 standard plans PDF required")
    doc = fitz.open(stream=original_pdf, filetype="pdf")
    try:
        if len(doc) != 10:
            raise ValueError("original Q5446 page universe changed")
        rows = []
        for idx, expected in enumerate(REQUIRED_TITLES):
            page = doc[idx]
            native_count = len(page.get_drawings())
            if native_count >= CAP:
                raise ValueError("original page-native drawing exceeds fixed 20,000 bound")
            raster_text = ocr(page)
            title = title_from_ocr_text(raster_text, expected)
            if title is None:
                raise ValueError("original vector title not uniquely recognized")
            rows.append({
                "page_number": idx + 1, "original_title_candidate": title,
                "native_drawings_on_page": native_count,
                "title_source": "SHA-authenticated original cropped pixels; OCR candidate",
                "producer_positive_floor_plan_role": False,
            })
        return {
            "schema": "q5446.source_vector_title_shadow.v1",
            "source_sha256": SHA, "source_page_count": len(doc),
            "title_candidate_rows": rows,
            "topology_eligible_pages": None,
            "source_authored_page_role_issued": False,
            "full_20k_cap_preserved": True,
            "frozen_score_promotion": False,
        }
    finally:
        doc.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if args.pdf.resolve() == args.out.resolve():
        raise ValueError("cannot overwrite original PDF")
    result = source_title_candidates(args.pdf.read_bytes())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "source_title_candidates": len(result["title_candidate_rows"]),
        "source_role_promotions": 0,
    }))


if __name__ == "__main__":
    main()
