"""Live extractor failure visibility regressions."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import fitz

from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


def _blank_pdf(tmp_path: Path) -> Path:
    pdf_path = tmp_path / "blank.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def test_schedule_parser_failure_records_extraction_failed_not_absence(
    tmp_path: Path,
) -> None:
    extractor = GenericPlanReaderExtractor()
    pdf_path = _blank_pdf(tmp_path)

    with patch(
        "pb_raster_schedule_extractor.GenericScheduleTableExtractor.extract_from_document",
        side_effect=RuntimeError("synthetic schedule parser failure"),
    ):
        extractor.extract_from_pdf(pdf_path, pages=[0])

    assert extractor.extraction_status.get("schedule") == "extraction_failed"


def test_genuine_empty_schedule_records_no_evidence_found(tmp_path: Path) -> None:
    extractor = GenericPlanReaderExtractor()
    pdf_path = _blank_pdf(tmp_path)

    with patch(
        "pb_raster_schedule_extractor.GenericScheduleTableExtractor.extract_from_document",
        return_value=[],
    ):
        extractor.extract_from_pdf(pdf_path, pages=[0])

    assert extractor.extraction_status.get("schedule") == "no_evidence_found"


def test_schedule_failure_must_not_become_zero_predictions_authority(
    tmp_path: Path,
) -> None:
    extractor = GenericPlanReaderExtractor()
    pdf_path = _blank_pdf(tmp_path)

    with patch(
        "pb_raster_schedule_extractor.GenericScheduleTableExtractor.extract_from_document",
        side_effect=RuntimeError("synthetic schedule parser failure"),
    ):
        preds = extractor.extract_from_pdf(pdf_path, pages=[0])

    assert extractor.extraction_status.get("schedule") == "extraction_failed"
    assert not any(
        p.tag == "D01" and p.quantity is not None and p.quantity > 0 for p in preds
    )
