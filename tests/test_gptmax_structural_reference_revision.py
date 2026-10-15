"""Prove original date candidates never authorize structural wall transfer."""

import fitz
import pytest

from tools.diag_gptmax_structural_reference_revision import (
    audit_revision_reference,
)


def _pdf(*, reference="Architectural drawings issued to STA on 22/01/26",
         sheet_date="28/07/26", reference_competitor=None,
         add_title_date_label=True):
    s = fitz.open()
    p = s.new_page(width=1191, height=842)
    if reference:
        p.insert_text((780, 165), reference, fontsize=8)
    if reference_competitor:
        p.insert_text((780, 200), reference_competitor, fontsize=8)
    structural = s.tobytes()
    s.close()
    a = fitz.open()
    p = a.new_page(width=1191, height=842)
    if add_title_date_label:
        p.insert_text((980, 780), "DATE:", fontsize=8)
    if sheet_date:
        p.insert_text((1040, 780), sheet_date, fontsize=8)
    p.insert_text((440, 790), "DATE 03/04/20", fontsize=8)  # revision-history decoy
    architectural = a.tobytes()
    a.close()
    return structural, architectural


def _audit(pair):
    return audit_revision_reference(*pair, structural_certificate_page=1,
                                    architectural_plan_page=1)


def test_distinct_original_issued_dates_block_all_cross_source_authority():
    report = _audit(_pdf())
    assert report["structural_referenced_architectural_issue_dates"] == ["2026-01-22"]
    assert report["architectural_sheet_native_date_candidates"] == ["2026-07-28"]
    assert "structural_reference_architectural_issue_dates_differ" in report["reason_codes"]
    assert not any(v for k, v in report.items() if k.endswith("_granted"))
    assert report["source_text_integrity_verified"] is False


def test_same_printed_date_is_not_cross_source_wall_evidence():
    r = _audit(_pdf(sheet_date="22/01/26"))
    assert "equal_printed_dates_do_not_prove_correspondence" in r["reason_codes"]
    assert r["cross_file_wall_identity_granted"] is False


@pytest.mark.parametrize("reference,date,label", [
    (None, "28/07/26", True),
    ("Proposed architectural plans", "28/07/26", True),
    ("Architectural drawings issued to STA on 22/01/26", None, True),
    ("Architectural drawings issued to STA on 22/01/26", "28/07/26", False),
    ("Architectural drawings issued to STA on 31/02/26", "28/07/26", True),
])
def test_missing_or_invalid_references_abstain(reference, date, label):
    r = _audit(_pdf(reference=reference, sheet_date=date,
                    add_title_date_label=label))
    assert "unavailable_or_ambiguous" in " ".join(r["reason_codes"])
    assert not r["cross_file_revision_applicability_granted"]


def test_competing_certified_reference_dates_abstain_without_election():
    r = _audit(_pdf(reference_competitor="Architectural drawings issued to STA on 28/07/26"))
    assert r["structural_referenced_architectural_issue_dates"] == ["2026-01-22", "2026-07-28"]
    assert "original_structural_reference_date_unavailable_or_ambiguous" in r["reason_codes"]


def test_repeated_replay_deterministic_and_source_not_mutated():
    src, arch = _pdf()
    a = _audit((src, arch))
    b = _audit((src, arch))
    assert a == b
    assert len(src) > 0 and len(arch) > 0


def test_explicit_page_input_cannot_be_omitted_or_out_of_bounds():
    a, b = _pdf()
    with pytest.raises(ValueError, match="selected source page absent"):
        audit_revision_reference(a, b, structural_certificate_page=2,
                                 architectural_plan_page=1)
    with pytest.raises(ValueError, match="positive structural"):
        audit_revision_reference(a, b, structural_certificate_page=0,
                                 architectural_plan_page=1)
