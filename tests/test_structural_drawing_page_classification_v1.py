"""Structural drawing-page classification and cross-sheet DPM regressions.

Structural sheets often carry authoritative substructure material notes even when
there is no architectural floor-plan title on the same page. These tests use
invented dimensions/material wording only; they do not read benchmark manifests,
gold quantities, project names, or expected values.
"""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


def _save_cross_sheet_fixture(
    tmp_path: Path,
    *,
    structural_title: str,
    structural_note: str,
) -> Path:
    doc = fitz.open()
    plan = doc.new_page(width=842, height=595)
    plan.insert_text(
        (60, 60),
        "\n".join(
            (
                "GROUND FLOOR PLAN",
                "SCALE 1:100",
                "16,000",
                "8,200",
            )
        ),
        fontsize=11,
    )
    structural = doc.new_page(width=842, height=595)
    structural.insert_text(
        (60, 60),
        "\n".join((structural_title, structural_note)),
        fontsize=11,
    )
    path = tmp_path / "cross_sheet_substructure.pdf"
    doc.save(path)
    doc.close()
    return path


@pytest.mark.parametrize(
    "title",
    (
        "FOUNDATION PLAN",
        "FOUNDATION LAYOUT",
        "GROUND FLOOR SLAB DETAILS",
        "SLAB DETAIL",
    ),
)
def test_structural_sheet_titles_are_recognized_as_drawing_pages(title: str) -> None:
    extractor = GenericPlanReaderExtractor()
    assert extractor.is_drawing_page(title)


def test_foundation_sheet_polythene_note_can_authorize_dpm_on_plan_footprint(
    tmp_path: Path,
) -> None:
    pdf = _save_cross_sheet_fixture(
        tmp_path,
        structural_title="FOUNDATION PLAN",
        structural_note="POLYTHENE SHEET 1000g below ground floor slab",
    )
    predictions = {
        pred.tag: pred
        for pred in GenericPlanReaderExtractor().extract_from_pdf(pdf)
    }
    assert "floor_screed" in predictions
    assert predictions["floor_screed"].quantity == pytest.approx(131.2)
    assert "substructure_bed_dpm" in predictions
    assert predictions["substructure_bed_dpm"].quantity == pytest.approx(131.2)
    assert predictions["substructure_bed_dpm"].quantity == predictions[
        "floor_screed"
    ].metadata["structural_bed_area_m2"]


def test_foundation_sheet_without_membrane_evidence_does_not_mint_dpm(
    tmp_path: Path,
) -> None:
    pdf = _save_cross_sheet_fixture(
        tmp_path,
        structural_title="FOUNDATION PLAN",
        structural_note="Typical ground beam reinforcement details",
    )
    predictions = {
        pred.tag: pred
        for pred in GenericPlanReaderExtractor().extract_from_pdf(pdf)
    }
    assert "floor_screed" in predictions
    assert "substructure_bed_dpm" not in predictions


def test_boq_like_text_still_fails_drawing_page_gate() -> None:
    extractor = GenericPlanReaderExtractor()
    assert not extractor.is_drawing_page(
        "BILL OF QUANTITIES RATE AMOUNT\nFoundation plan allowance item"
    )
