"""Never attach a later drawing's finish note to a prior page's floor.

These PDF pages are synthetic and do not encode any benchmark truth.
"""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


def _pdf(tmp_path: Path, *, plaster_on_main: bool, second_plan: bool) -> Path:
    doc = fitz.open()
    main = doc.new_page(width=842, height=595)
    main_lines = [
        "GROUND FLOOR PLAN",
        "SCALE 1:100",
        "10,000",
        "6,000",
    ]
    if plaster_on_main:
        main_lines.append("INTERNAL PLASTER TO WALL SURFACES")
    for index, line in enumerate(main_lines):
        main.insert_text((72, 60 + index * 31), line, fontsize=11)
    if second_plan:
        other = doc.new_page(width=842, height=595)
        # A separate smaller physical plan is not an authoritative link to
        # the main floor. Earlier code retained the larger global envelope,
        # then issued a finish row on this later page from the main wall.
        for index, line in enumerate([
            "FIRST FLOOR PLAN",
            "SCALE 1:100",
            "4,000",
            "2,000",
            "INTERNAL PLASTER TO WALL SURFACES",
        ]):
            other.insert_text((72, 60 + index * 31), line, fontsize=11)
    path = tmp_path / f"floor_scope_{int(plaster_on_main)}_{int(second_plan)}.pdf"
    doc.save(path)
    doc.close()
    return path


def _by_tag(path: Path) -> dict:
    result = GenericPlanReaderExtractor().extract_from_pdf(
        path, collect_item35_shadow=False,
    )
    return {item.tag: item for item in result}


def test_unrelated_second_floor_finish_cannot_borrow_larger_main_footprint(tmp_path: Path):
    baseline = _by_tag(_pdf(tmp_path, plaster_on_main=False, second_plan=False))
    combined = _by_tag(_pdf(tmp_path, plaster_on_main=False, second_plan=True))
    assert baseline["floor_screed"].quantity == pytest.approx(60.0)
    assert combined["floor_screed"].quantity == pytest.approx(60.0)
    assert combined["floor_screed"].source_page == 1
    assert combined["perimeter_walling"].source_page == 1
    assert "internal_plaster" not in baseline
    assert "internal_plaster" not in combined
    assert "internal_paint" not in combined


def test_own_page_finish_still_resolves_from_its_own_source_wall(tmp_path: Path):
    own = _by_tag(_pdf(tmp_path, plaster_on_main=True, second_plan=False))
    assert own["floor_screed"].source_page == 1
    assert own["perimeter_walling"].source_page == 1
    assert own["internal_plaster"].source_page == 1
    assert own["internal_paint"].source_page == 1
    assert own["internal_plaster"].quantity > 0
