"""Never certify an assumed full-frontage verandah from a depth figure alone.

Synthetic PDFs only; no original plans or benchmark truth.
"""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


def _synthetic(tmp_path: Path, extra: str | None) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    lines = ["GROUND FLOOR PLAN", "SCALE 1:100", "10,000", "6,000"]
    if extra:
        lines.append(extra)
    for n, line in enumerate(lines):
        page.insert_text((72, 50 + 30 * n), line, fontsize=11)
    path = tmp_path / f"depth_only_{bool(extra)}.pdf"
    doc.save(path)
    doc.close()
    return path


def _floor(path: Path):
    preds = GenericPlanReaderExtractor().extract_from_pdf(
        path, collect_item35_shadow=False,
    )
    return {p.tag: p for p in preds}["floor_screed"]


def test_figured_depth_does_not_prove_verandah_frontage_or_commercial_sum(tmp_path: Path):
    measured = _floor(_synthetic(tmp_path, "2m wide verandah"))
    # Numeric legacy diagnostic can still include a speculative full frontage;
    # it must not be sealed as a physical source-complete compound.
    assert measured.quantity == pytest.approx(80.0)
    assert measured.metadata["commercial_area_authorized"] is False
    assert measured.metadata["secondary_span_source_owned"] is False
    assert measured.metadata["original_source_compound_complete"] is False
    assert measured.confidence <= 0.45


def test_unfigured_verandah_remains_incomplete(tmp_path: Path):
    measured = _floor(_synthetic(tmp_path, "VERANDAH"))
    assert measured.metadata["commercial_area_authorized"] is False
    assert measured.metadata["secondary_span_source_owned"] is False


def test_without_secondary_label_retains_complete_figured_rectangle(tmp_path: Path):
    measured = _floor(_synthetic(tmp_path, None))
    assert measured.quantity == pytest.approx(60.0)
    assert measured.metadata["commercial_area_authorized"] is True
    assert measured.metadata["secondary_span_source_owned"] is True
