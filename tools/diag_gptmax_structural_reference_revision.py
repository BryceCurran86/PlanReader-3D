"""Read-only, native-text cross-document design-reference audit.

Native PDF text is diagnostic input, NOT authenticated PlanReader source evidence.
No result from this tool licenses cross-document wall identity, scale, dimension,
quantity, or historical benchmark promotion.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re

import fitz

_DATE = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}$")
_REFERENCE = re.compile(
    r"\barchitectural\s+drawings\s+issued\s+to\s+[^\n]{1,100}?\s+on\s+"
    r"(\d{1,2}/\d{1,2}/\d{2,4})\b",
    re.IGNORECASE,
)


def _clean_date(value: str) -> str | None:
    if not _DATE.fullmatch(value):
        return None
    for pattern in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _reference_dates(page: fitz.Page) -> tuple[str, ...]:
    # Preserve every reference date: never elect one competing source record.
    raw = page.get_text("text", sort=False)
    return tuple(sorted(set(
        normalized
        for match in _REFERENCE.finditer(raw)
        if (normalized := _clean_date(match.group(1))) is not None
    )))


def _sheet_date_candidates(page: fitz.Page) -> tuple[str, ...]:
    """Native title-block date candidates, not authoritative revision identity."""
    width, height = page.rect.width, page.rect.height
    words = page.get_text("words", sort=False)
    # Restrict detection to an explicit source title-block DATE: printed field.
    # Do not fall back to any loose page date or revision-history entry.
    date_labels = [w for w in words if w[4].strip().upper() == "DATE:"
                   and w[0] >= width * .5 and w[1] >= height * .7]
    if len(date_labels) != 1:
        return ()
    label = date_labels[0]
    dates = set()
    for word in words:
        if word[0] <= label[2] or word[0] >= width:
            continue
        if max(word[1], label[1]) >= min(word[3], label[3]):
            continue
        candidate = _clean_date(word[4].strip())
        if candidate is not None:
            dates.add(candidate)
    return tuple(sorted(dates))


def audit_revision_reference(
    structural_bytes: bytes, architectural_bytes: bytes,
    *, structural_certificate_page: int, architectural_plan_page: int,
) -> dict:
    """Page addresses are 1-based explicit caller selections, never guessed."""
    if not isinstance(structural_bytes, bytes) or not structural_bytes:
        raise TypeError("original structural PDF bytes required")
    if not isinstance(architectural_bytes, bytes) or not architectural_bytes:
        raise TypeError("original architectural PDF bytes required")
    if type(structural_certificate_page) is not int or structural_certificate_page < 1:
        raise ValueError("explicit positive structural certificate page required")
    if type(architectural_plan_page) is not int or architectural_plan_page < 1:
        raise ValueError("explicit positive architectural plan page required")
    with fitz.open(stream=structural_bytes, filetype="pdf") as structural, fitz.open(
        stream=architectural_bytes, filetype="pdf"
    ) as architectural:
        if structural_certificate_page > len(structural) or architectural_plan_page > len(architectural):
            raise ValueError("selected source page absent")
        refs = _reference_dates(structural[structural_certificate_page - 1])
        sheets = _sheet_date_candidates(architectural[architectural_plan_page - 1])
    reasons = ["native_text_diagnostic_not_source_authority",
               "cross_document_source_wall_correspondence_unproven"]
    if len(refs) != 1:
        reasons.append("original_structural_reference_date_unavailable_or_ambiguous")
    if len(sheets) != 1:
        reasons.append("original_architectural_title_date_unavailable_or_ambiguous")
    if len(refs) == len(sheets) == 1:
        if refs[0] != sheets[0]:
            reasons.append("structural_reference_architectural_issue_dates_differ")
        else:
            # Matching printed dates still cannot authenticate a source revision
            # or establish shared physical geometry across different PDFs.
            reasons.append("equal_printed_dates_do_not_prove_correspondence")
    return {
        "status": "UNPUBLISHED_NATIVE_TEXT_DIAGNOSTIC",
        "source_sha256": {
            "structural": sha256(structural_bytes).hexdigest(),
            "architectural": sha256(architectural_bytes).hexdigest(),
        },
        "source_pages": {
            "structural_certificate": structural_certificate_page,
            "architectural_plan": architectural_plan_page,
        },
        "structural_referenced_architectural_issue_dates": list(refs),
        "architectural_sheet_native_date_candidates": list(sheets),
        "reason_codes": reasons,
        "source_text_integrity_verified": False,
        "cross_file_revision_applicability_granted": False,
        "cross_file_wall_identity_granted": False,
        "cross_file_scale_or_dimension_granted": False,
        "quantity_or_customer_publication_granted": False,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--structural-pdf", type=Path, required=True)
    p.add_argument("--architectural-pdf", type=Path, required=True)
    p.add_argument("--structural-certificate-page", type=int, required=True)
    p.add_argument("--architectural-plan-page", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    report = audit_revision_reference(
        args.structural_pdf.read_bytes(), args.architectural_pdf.read_bytes(),
        structural_certificate_page=args.structural_certificate_page,
        architectural_plan_page=args.architectural_plan_page,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print({"reason_codes": report["reason_codes"],
           "cross_file_wall_identity_granted": False})


if __name__ == "__main__":
    main()
