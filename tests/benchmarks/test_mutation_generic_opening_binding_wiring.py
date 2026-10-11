from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import fitz

from pb_planreader_pdf_extractor import GenericPlanReaderExtractor
from pb_raster_schedule_extractor import GenericScheduleTableExtractor


def _schedule_pdf(tmp_path: Path, name: str, rows: list[list[str]], extra_text: str = "") -> Path:
    path = tmp_path / name
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text((40, 35), "DRAWING TITLE: WINDOW & DOOR SCHEDULE", fontsize=10)
    page.insert_text((40, 50), "SCALE 1:100", fontsize=9)
    x = [40, 130, 300, 390, 650]
    y0 = 85
    rh = 28
    for ridx, row in enumerate(rows):
        y = y0 + ridx * rh
        page.draw_line(fitz.Point(x[0], y), fitz.Point(x[-1], y))
        for cidx, cell in enumerate(row):
            page.draw_line(fitz.Point(x[cidx], y), fitz.Point(x[cidx], y + rh))
            page.insert_text((x[cidx] + 5, y + 18), cell, fontsize=9)
        page.draw_line(fitz.Point(x[-1], y), fitz.Point(x[-1], y + rh))
    page.draw_line(fitz.Point(x[0], y0 + len(rows) * rh), fitz.Point(x[-1], y0 + len(rows) * rh))
    if extra_text:
        page.insert_text((40, y0 + len(rows) * rh + 35), extra_text, fontsize=9)
    doc.save(path)
    doc.close()
    return path


def test_arbitrary_documented_tags_wire_end_to_end(tmp_path: Path) -> None:
    pdf = _schedule_pdf(
        tmp_path,
        "arbitrary_tags.pdf",
        [
            ["Mark", "Dimensions", "Quantity", "Description"],
            ["W-17", "1840 x 1260 mm", "6 No.", "Powder coated casement window"],
            ["DOOR 12", "940 x 2140 mm", "3 No.", "Timber flush door"],
        ],
    )
    preds = {p.tag: p for p in GenericPlanReaderExtractor().extract_from_pdf(pdf)}
    assert preds["W17"].quantity == 6.0
    assert preds["W17"].dimensions == [1840.0, 1260.0]
    assert preds["W17"].trade_type == "windows"
    assert preds["D12"].quantity == 3.0
    assert preds["D12"].dimensions == [940.0, 2140.0]
    assert preds["D12"].trade_type == "doors"


def test_row_aligned_fallback_does_not_depend_on_structured_table_detection(tmp_path: Path) -> None:
    pdf = _schedule_pdf(
        tmp_path,
        "row_fallback.pdf",
        [
            ["Mark", "Dimensions", "Quantity", "Description"],
            ["WINDOW 42", "1610 x 1180 mm", "7 No.", "Casement window"],
            ["DR-19", "920 x 2110 mm", "2 No.", "Flush door"],
        ],
    )
    with patch.object(GenericScheduleTableExtractor, "_extract_tables_from_page", return_value=[]):
        preds = {p.tag: p for p in GenericPlanReaderExtractor().extract_from_pdf(pdf)}

    assert preds["W42"].quantity == 7.0
    assert preds["W42"].dimensions == [1610.0, 1180.0]
    assert preds["D19"].quantity == 2.0
    assert preds["D19"].dimensions == [920.0, 2110.0]


def test_mutating_source_count_changes_only_that_opening(tmp_path: Path) -> None:
    first = _schedule_pdf(
        tmp_path,
        "before.pdf",
        [
            ["Mark", "Dimensions", "Quantity", "Description"],
            ["WIN 8", "1730 x 1190 mm", "4 No.", "Casement window"],
            ["DR-3", "910 x 2080 mm", "2 No.", "Panel door"],
        ],
    )
    second = _schedule_pdf(
        tmp_path,
        "after.pdf",
        [
            ["Mark", "Dimensions", "Quantity", "Description"],
            ["WIN 8", "1730 x 1190 mm", "9 No.", "Casement window"],
            ["DR-3", "910 x 2080 mm", "2 No.", "Panel door"],
        ],
    )
    p1 = {p.tag: p for p in GenericPlanReaderExtractor().extract_from_pdf(first)}
    p2 = {p.tag: p for p in GenericPlanReaderExtractor().extract_from_pdf(second)}
    assert p1["W8"].quantity == 4.0
    assert p2["W8"].quantity == 9.0
    assert p1["D3"].quantity == p2["D3"].quantity == 2.0


def test_removing_explicit_identity_removes_firm_opening(tmp_path: Path) -> None:
    tagged = _schedule_pdf(
        tmp_path,
        "tagged.pdf",
        [
            ["Mark", "Dimensions", "Quantity", "Description"],
            ["W-21", "1680 x 1110 mm", "5 No.", "Casement window"],
        ],
    )
    untagged = _schedule_pdf(
        tmp_path,
        "untagged.pdf",
        [
            ["Mark", "Dimensions", "Quantity", "Description"],
            ["", "1680 x 1110 mm", "5 No.", "Casement window"],
        ],
    )
    tagged_preds = {p.tag: p for p in GenericPlanReaderExtractor().extract_from_pdf(tagged)}
    untagged_preds = {p.tag: p for p in GenericPlanReaderExtractor().extract_from_pdf(untagged)}
    assert tagged_preds["W21"].quantity == 5.0
    assert "W21" not in untagged_preds


def test_sparse_complete_native_schedule_does_not_create_redundant_ocr_claim(tmp_path):
    pdf=_schedule_pdf(tmp_path,"short_native.pdf",[
        ["Mark","Dimensions","Quantity","Description"],
        ["W-21","1680 x 1110 mm","5 No.","Casement window"],
    ])
    with fitz.open(pdf) as source:
        assert len(source[0].get_text().strip())<150
    def recognize(_page,**kwargs):
        # Other evidence collectors may request OCR independently at 120 DPI.
        # The opening reconciliation pass at 150 DPI is the redundant claim.
        assert kwargs.get('dpi')!=150
        return []
    with patch("pb_drawing_ocr_evidence_layer.DrawingOCREngine.recognize_page_rect",
               side_effect=recognize) as ocr:
        extractor=GenericPlanReaderExtractor()
        rows={r.tag:r for r in extractor.extract_from_pdf(pdf)}
    assert not [c for c in ocr.call_args_list if c.kwargs.get('dpi')==150]
    assert rows['W21'].quantity==5.
    assert rows['W21'].dimensions==[1680.,1110.]
    assert not rows['W21'].metadata.get('publication_blocked',False)


def test_sparse_page_without_complete_native_rows_still_requests_ocr(tmp_path):
    pdf=_schedule_pdf(tmp_path,"native_missing.pdf",[
        ["Mark","Dimensions","Quantity","Description"],
        ["W-21","1680 x 1110 mm","","Casement window"],
    ])
    with patch.object(GenericScheduleTableExtractor,'extract_from_document',return_value=[]):
        with patch("pb_drawing_ocr_evidence_layer.DrawingOCREngine.recognize_page_rect",
                   return_value=[]) as ocr:
            rows={r.tag:r for r in GenericPlanReaderExtractor().extract_from_pdf(pdf)}
    assert len([c for c in ocr.call_args_list if c.kwargs.get('dpi')==150])==1
    assert 'W21' not in rows or rows['W21'].quantity is None


def test_untagged_dimensions_never_synthesize_benchmark_shaped_identities(tmp_path: Path) -> None:
    path = tmp_path / "untagged_callouts.pdf"
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text((40, 35), "GROUND FLOOR PLAN", fontsize=10)
    page.insert_text((40, 50), "SCALE 1:100", fontsize=9)
    page.insert_text((60, 100), "2,900mm x 900mm steel casement windows with 4mm thick glass", fontsize=9)
    page.insert_text((60, 130), "3,000mm x 900mm steel casement windows with 4mm thick glass", fontsize=9)
    page.insert_text((60, 160), "1,000mm x 2,100mm timber batten door with 3 nos. butt hinges", fontsize=9)
    doc.save(path)
    doc.close()

    preds = {p.tag: p for p in GenericPlanReaderExtractor().extract_from_pdf(path)}
    assert "W1" not in preds
    assert "W2" not in preds
    assert "D1" not in preds


def test_conflicting_alias_rows_fail_closed(tmp_path: Path) -> None:
    pdf = _schedule_pdf(
        tmp_path,
        "conflict.pdf",
        [
            ["Mark", "Dimensions", "Quantity", "Description"],
            ["W-33", "1870 x 1240 mm", "4 No.", "Casement window"],
            ["WINDOW 33", "1870 x 1240 mm", "7 No.", "Casement window"],
        ],
    )
    doc = fitz.open(pdf)
    rows = GenericScheduleTableExtractor().extract_from_document(doc)
    assert not [r for r in rows if r.tag == "W33" and not r.is_provisional]


def test_production_no_longer_contains_three_special_case_opening_pipeline() -> None:
    import inspect
    import pb_planreader_pdf_extractor as mod

    src = inspect.getsource(mod.GenericPlanReaderExtractor.extract_from_pdf)
    assert "sched_spec_w1" not in src
    assert "sched_spec_w2" not in src
    assert "sched_spec_d1" not in src
    assert "w1_occs" not in src
    assert "w2_occs" not in src
    assert "d1_occs" not in src
