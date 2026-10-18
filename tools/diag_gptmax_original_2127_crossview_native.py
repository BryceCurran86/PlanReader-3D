"""Authenticate original Lot16 native 2127 STACKER plan/elevation label pairs.

A verified cross-sheet label is source evidence, NOT physical SAME, a unique
structural host, full frame, door/window semantic authority, count or quantity.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

import fitz

LOT16_ORIGINAL_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
_SOURCE_LABEL_PAGES = (3, 5)
_EXPECTED_CENTRES = {3: (798.5, 438.0), 5: (734.3, 467.6)}


def paired_native_2127_tokens(page):
    """Require adjacent native source words on one same original text line."""
    words = page.get_text("words")
    pairs = []
    for a, b in zip(words, words[1:]):
        if (str(a[4]).upper() == "2127" and str(b[4]).upper() == "STACKER"
                and (a[5], a[6]) == (b[5], b[6])
                and a[7] + 1 == b[7] and float(a[2]) <= float(b[0])):
            pairs.append((min(float(a[0]), float(b[0])),
                          min(float(a[1]), float(b[1])),
                          max(float(a[2]), float(b[2])),
                          max(float(a[3]), float(b[3]))))
    return tuple(pairs)


def original_2127_crossview_receipt(pdf_bytes):
    """Fail closed on wrong original bytes, pages, native labels or locality."""
    if type(pdf_bytes) is not bytes or sha256(pdf_bytes).hexdigest() != LOT16_ORIGINAL_SHA:
        raise ValueError("SHA-verified original Lot16 PDF required")
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if len(doc) != 13:
            raise ValueError("original Lot16 expected thirteen source pages")
        matched = []
        for page_number in _SOURCE_LABEL_PAGES:
            page = doc[page_number - 1]
            if page.rotation != 0:
                raise ValueError("original Lot16 page rotation changed")
            pairs = paired_native_2127_tokens(page)
            if len(pairs) != 1:
                raise ValueError("unique native 2127 STACKER mark is unproved")
            box = pairs[0]
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            ex, ey = _EXPECTED_CENTRES[page_number]
            if abs(cx-ex) > 3 or abs(cy-ey) > 3:
                raise ValueError("2127 native mark moved outside original source locality")
            matched.append({"page_number":page_number,
                            "native_text":"2127 STACKER",
                            "bbox_pdf_pt":list(box),
                            "source_type":"native_pdf_words",
                            "source_authentic":True})
    finally:
        doc.close()
    return {
        "status":"source_authenticated_crossview_label_candidate",
        "source_sha256":LOT16_ORIGINAL_SHA,
        "native_marks":matched,
        "exact_cross_page_physical_identity_proven":False,
        "unique_structural_host_proven":False,
        "whole_wall_frame_proven":False,
        "door_window_semantic_role_proven":False,
        "quantity_promotion_granted":False,
        "opening_count_completeness_proven":False,
        "source_only_evidence":True,
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.pdf.resolve()==args.output.resolve():
        raise ValueError("original PDF cannot be overwritten")
    report=original_2127_crossview_receipt(args.pdf.read_bytes())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+"\n")
    print(json.dumps({"source_authenticated":True,"authority_promotion":False}))


if __name__=="__main__":
    main()
