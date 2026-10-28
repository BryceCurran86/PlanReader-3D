from __future__ import annotations

import json

import fitz
import pytest

from tools import diag_native_text_trust_by_page as census


def _pdf(tmp_path, pages=2):
    document = fitz.open()
    for index in range(pages):
        page = document.new_page(width=300, height=300)
        page.insert_text((40, 80), f"SECRETWORD{index}", fontsize=12)
    path = tmp_path / "private-name.pdf"
    document.save(path)
    document.close()
    return path


def test_report_is_counts_only_and_never_carries_text_or_names(tmp_path):
    out = tmp_path / "report.json"
    assert census.main(["--pdf", str(_pdf(tmp_path)), "--output", str(out)]) == 0
    raw = out.read_text(encoding="utf-8")
    assert "SECRETWORD" not in raw and "private-name" not in raw
    report = json.loads(raw)
    assert report["authority_granted"] is False
    assert report["page_count"] == 2
    assert set(report["pages"]) == {"1", "2"}
    for row in report["pages"].values():
        assert row["words"] == 1
        assert set(row) == {"words", "default", "opt_in", "rotation"}
        assert 0 <= row["default"]["trusted"] <= row["words"]
        assert 0 <= row["opt_in"]["trusted"] <= row["words"]


def test_totals_add_up_and_the_opt_in_is_never_less_trusting_on_a_plain_page(tmp_path):
    report = census.census_pdf(_pdf(tmp_path, pages=3))
    assert report["totals"]["words"] == 3
    assert report["totals"]["trusted_default"] == sum(
        r["default"]["trusted"] for r in report["pages"].values())
    assert report["totals"]["trusted_opt_in"] >= report["totals"]["trusted_default"]


def test_page_selection_is_one_based_and_validated(tmp_path):
    path = _pdf(tmp_path)
    assert set(census.census_pdf(path, [2])["pages"]) == {"2"}
    for bad in ([0], [3], [True]):
        with pytest.raises(ValueError):
            census.census_pdf(path, bad)


def test_the_census_does_not_modify_the_pdf(tmp_path):
    path = _pdf(tmp_path)
    before = path.read_bytes()
    census.census_pdf(path)
    assert path.read_bytes() == before
