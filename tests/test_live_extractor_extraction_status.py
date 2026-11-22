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


def test_native_review_stages_use_consistent_page_bounds_across_rotations(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "native-plan-frames.pdf"
    with fitz.open() as doc:
        for rotation in (0, 270, 90):
            page = doc.new_page(width=600, height=800)
            page.insert_text((50, 55), "GROUND FLOOR PLAN\nSCALE 1:100")
            page.insert_text((440, 680), "LEGEND")
            # Both the wall at y=600 and the legend symbol below it are
            # inside the native page. The display bounds at 90 degrees
            # instead put them on or beyond the bottom edge.
            corners = ((60, 150), (350, 150), (350, 600), (60, 600))
            for start, end in zip(corners, corners[1:] + corners[:1]):
                page.draw_line(start, end, width=2.5)
            page.draw_bezier(
                (455, 720), (455, 709), (464, 700), (475, 700), width=0.5,
            )
            page.set_rotation(rotation)
        doc.save(str(pdf_path))

    extractor = GenericPlanReaderExtractor()
    with patch(
        "pb_drawing_ocr_evidence_layer.DrawingOCREngine.recognize_page_rect",
        return_value=[],
    ):
        extractor.extract_from_pdf(pdf_path, collect_item35_shadow=False)

    inside = extractor.external_footprint_trace_live["inside_face_footprint_stages"]
    legend = extractor.door_legend_read_live["pages"]
    for stages in (inside, legend):
        assert [stage["page_index"] for stage in stages] == [0, 1, 2]
        assert all(stage["measurement_authorized"] is False for stage in stages)
    assert inside[0]["inside_face_start"] == inside[2]["inside_face_start"]
    assert inside[0]["clockwise_walk"] == inside[2]["clockwise_walk"]
    assert inside[0]["commercial_publishable"] is False
    assert inside[2]["commercial_publishable"] is False
    assert legend[0]["legend_variant_count"] == legend[2]["legend_variant_count"] == 1
    assert legend[0]["legend_variants"] == legend[2]["legend_variants"]
    assert legend[0]["physical_openings_authenticated"] is False
    assert legend[2]["physical_openings_authenticated"] is False
    for unresolved in (inside[1], legend[1]):
        assert unresolved["status"] == "ABSTAINED"
        assert unresolved["reason"] == "native_page_frame_unresolved"
