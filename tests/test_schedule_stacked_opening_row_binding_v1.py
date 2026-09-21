from __future__ import annotations

from pathlib import Path

import fitz

from pb_planreader_pdf_extractor import GenericPlanReaderExtractor
from pb_raster_schedule_extractor import GenericScheduleTableExtractor


def _write_stacked_schedule(
    path: Path,
    *,
    tag: str = "W-17",
    dimensions: str = "1840 x 1260 mm",
    quantity: str = "6 No.",
    second_tag: str | None = None,
) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=700, height=500)
    page.insert_text((40, 35), "WINDOW & DOOR SCHEDULE", fontsize=10)

    # One logical CAD schedule cell exported as three separate text baselines.
    # Their x-ranges overlap, but no single baseline contains all evidence.
    page.insert_text((100, 100), tag, fontsize=10)
    if second_tag is not None:
        page.insert_text((100, 111), second_tag, fontsize=10)
        dim_y, qty_y = 122, 133
    else:
        dim_y, qty_y = 111, 122
    page.insert_text((100, dim_y), dimensions, fontsize=10)
    page.insert_text((100, qty_y), quantity, fontsize=10)

    doc.save(path)
    doc.close()
    return path


def _row_map(path: Path) -> dict[str, object]:
    doc = fitz.open(path)
    try:
        rows = GenericScheduleTableExtractor().extract_from_page(doc[0], 1)
    finally:
        doc.close()
    return {row.tag: row for row in rows if not row.is_provisional}


def test_stacked_explicit_tag_dimensions_and_count_bind_to_one_row(tmp_path: Path) -> None:
    path = _write_stacked_schedule(tmp_path / "stacked.pdf")
    rows = _row_map(path)

    row = rows["W17"]
    assert row.quantity == 6.0
    assert row.dimensions == [1840.0, 1260.0]
    assert row.trade_type == "windows"
    assert "Stacked native schedule evidence" in row.evidence_text


def test_stacked_schedule_mutation_changes_source_backed_quantity(tmp_path: Path) -> None:
    before = _write_stacked_schedule(tmp_path / "before.pdf", quantity="6 No.")
    after = _write_stacked_schedule(tmp_path / "after.pdf", quantity="9 No.")

    assert _row_map(before)["W17"].quantity == 6.0
    assert _row_map(after)["W17"].quantity == 9.0


def test_stacked_dimensions_and_count_without_explicit_identity_fail_closed(tmp_path: Path) -> None:
    path = _write_stacked_schedule(
        tmp_path / "no-tag.pdf",
        tag="OPENING",
        dimensions="1840 x 1260 mm",
        quantity="6 No.",
    )
    assert "W17" not in _row_map(path)


def test_competing_explicit_identities_in_same_stack_fail_closed(tmp_path: Path) -> None:
    path = _write_stacked_schedule(
        tmp_path / "ambiguous.pdf",
        tag="W-17",
        second_tag="W-18",
        dimensions="1840 x 1260 mm",
        quantity="6 No.",
    )
    rows = _row_map(path)
    assert "W17" not in rows
    assert "W18" not in rows


def test_engineering_tag_with_second_numeric_segment_is_not_opening_identity(tmp_path: Path) -> None:
    path = _write_stacked_schedule(
        tmp_path / "engineering-tag.pdf",
        tag="D8-03-200 C/C",
        dimensions="1000 x 2100 mm",
        quantity="3 No.",
    )
    assert "D8" not in _row_map(path)


def test_stacked_schedule_wires_through_live_extractor(tmp_path: Path) -> None:
    path = _write_stacked_schedule(
        tmp_path / "live.pdf",
        tag="WINDOW 42",
        dimensions="1610 x 1180 mm",
        quantity="7 Nos.",
    )
    predictions = {
        prediction.tag: prediction
        for prediction in GenericPlanReaderExtractor().extract_from_pdf(path)
    }

    assert predictions["W42"].quantity == 7.0
    assert predictions["W42"].dimensions == [1610.0, 1180.0]
    assert predictions["W42"].trade_type == "windows"
