"""The coverage diagnostic reports the authority's own verdicts and changes nothing."""
from __future__ import annotations

import json

import fitz

from tools.diag_text_integrity_coverage import coverage, main


def _pdf(path):
    document = fitz.open()
    page = document.new_page(width=842, height=595)
    page.insert_text((50, 100), "LIVING ROOM 3600", fontname="helv", fontsize=12)
    page.insert_text((50, 140), "BED 2 2400", fontname="helv", fontsize=12)
    document.save(str(path))
    document.close()


def test_plain_base14_text_is_fully_trusted_and_fonts_are_listed(tmp_path):
    pdf = tmp_path / "plain.pdf"
    _pdf(pdf)
    before = pdf.read_bytes()
    rows = coverage(pdf, [1])
    assert pdf.read_bytes() == before                                   # read-only
    row = rows[0]
    assert row["page"] == 1 and row["words"] == 6
    assert row["trusted_words"] == 6 and row["trusted_fraction"] == 1.0
    assert row["status_counts"] == {"CORROBORATED": 6}
    assert row["reason_counts_per_word"] == {"producer_owned_pdf_text_integrity_resolved": 6}
    assert row["fonts"] and row["fonts"][0]["characters_on_page"] > 0


def test_cli_writes_json_and_prints_a_one_line_summary(tmp_path, capsys):
    pdf = tmp_path / "plain.pdf"
    _pdf(pdf)
    out = tmp_path / "nested" / "coverage.json"
    import sys

    argv = sys.argv
    sys.argv = ["diag", "--pdf", str(pdf), "--pages", "1", "--json", str(out)]
    try:
        assert main() == 0
    finally:
        sys.argv = argv
    assert "6/6 words trusted" in capsys.readouterr().out
    assert json.loads(out.read_text(encoding="utf-8"))[0]["trusted_words"] == 6


def test_a_page_without_text_reports_zero_words_without_dividing_by_zero(tmp_path):
    document = fitz.open()
    document.new_page(width=300, height=300)
    pdf = tmp_path / "blank.pdf"
    document.save(str(pdf))
    document.close()
    row = coverage(pdf, [1])[0]
    assert row["words"] == 0 and row["trusted_fraction"] is None and row["status_counts"] == {}
