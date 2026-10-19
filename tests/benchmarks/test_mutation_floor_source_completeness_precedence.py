"""Select source-complete legacy floor envelopes over partial larger estimates.

All plans here are synthetic: this is NOT a frozen benchmark fixture.
"""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


def _package(tmp_path: Path, page_specs: tuple[tuple[int, int, bool], ...]) -> Path:
    doc = fitz.open()
    for length_mm, width_mm, unmeasured_secondary in page_specs:
        page = doc.new_page(width=842, height=595)
        lines = [
            "GROUND FLOOR PLAN",
            "SCALE 1:100",
            f"{length_mm:,}",
            f"{width_mm:,}",
        ]
        if unmeasured_secondary:
            lines.append("VERANDAH")
        for i, line in enumerate(lines):
            page.insert_text((72, 65 + 32 * i), line, fontsize=11)
    path = tmp_path / ("package_" + "_".join(
        f"{length}_{width}_{int(partial)}"
        for length, width, partial in page_specs
    ) + ".pdf")
    doc.save(path)
    doc.close()
    return path


def _floor(path: Path):
    quantities = GenericPlanReaderExtractor().extract_from_pdf(
        path, collect_item35_shadow=False,
    )
    return {row.tag: row for row in quantities}["floor_screed"]


def test_larger_partial_compound_does_not_displace_complete_original_floor(tmp_path: Path):
    complete = _floor(_package(tmp_path, ((10000, 6000, False),)))
    assert complete.quantity == pytest.approx(60.0)
    assert complete.metadata["commercial_area_authorized"] is True

    selected = _floor(_package(tmp_path, (
        (10000, 6000, False),
        (12000, 8000, True),
    )))
    assert selected.quantity == pytest.approx(60.0)
    assert selected.source_page == 1
    assert selected.metadata["commercial_area_authorized"] is True


def test_later_complete_floor_recovers_from_larger_partial_original(tmp_path: Path):
    unmeasured = _floor(_package(tmp_path, ((12000, 8000, True),)))
    assert unmeasured.quantity == pytest.approx(96.0)
    assert unmeasured.metadata["commercial_area_authorized"] is False

    selected = _floor(_package(tmp_path, (
        (12000, 8000, True),
        (10000, 6000, False),
    )))
    assert selected.quantity == pytest.approx(60.0)
    assert selected.source_page == 2
    assert selected.metadata["commercial_area_authorized"] is True


def test_same_source_quality_retains_existing_largest_legacy_envelope(tmp_path: Path):
    selected = _floor(_package(tmp_path, (
        (10000, 6000, False),
        (11000, 7000, False),
    )))
    assert selected.quantity == pytest.approx(77.0)
    assert selected.source_page == 2
    assert selected.metadata["commercial_area_authorized"] is True
