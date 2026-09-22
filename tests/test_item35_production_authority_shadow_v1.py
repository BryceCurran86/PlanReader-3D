"""Production integration tests for the Item 35 authority shadow."""
from __future__ import annotations

import fitz

from pb_item35_production_authority_shadow import (
    collect_item35_authority_shadow,
)
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


def _draw_opening(page: fitz.Page) -> None:
    for first, second in (
        ((20.0, 100.0), (100.0, 100.0)),
        ((140.0, 100.0), (220.0, 100.0)),
        ((20.0, 110.0), (100.0, 110.0)),
        ((140.0, 110.0), (220.0, 110.0)),
        ((100.0, 100.0), (100.0, 110.0)),
        ((140.0, 100.0), (140.0, 110.0)),
    ):
        page.draw_line(
            fitz.Point(*first),
            fitz.Point(*second),
            color=(0, 0, 0),
            width=1,
        )


def _write_minimal_drawing(path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=700, height=650)
    page.insert_text(fitz.Point(40, 40), "GROUND FLOOR PLAN", color=(0, 0, 0))
    _draw_opening(page)
    doc.save(path)
    doc.close()


def test_item35_shadow_executes_real_source_chain_but_keeps_commerce_locked(tmp_path) -> None:
    pdf_path = tmp_path / "item35-shadow.pdf"
    _write_minimal_drawing(pdf_path)

    shadow = collect_item35_authority_shadow(
        pdf_path,
        document_id="item35-shadow-test",
    )

    assert shadow["status"] == "evidence_present"
    assert shadow["visible_observation_count"] == 6
    assert shadow["semantic_opening_count"] == 1
    assert shadow["support_observation_count"] == 6
    assert shadow["residual_visible_observation_count"] == 0
    assert shadow["structural_enumeration_complete"] is True
    assert shadow["physical_opening_universe_complete"] is True
    assert shadow["commercial_count_unlocked"] is True
    assert shadow["generic_count_status"] == "corroborated"
    assert shadow["generic_count"] == 1



def _write_classified_window_drawing(path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=700, height=650)
    page.insert_text(fitz.Point(40, 40), "GROUND FLOOR PLAN", color=(0, 0, 0))
    _draw_opening(page)
    page.insert_text(fitz.Point(112, 106), "W1", color=(0, 0, 0))
    y = 500.0
    for row in (("MARK", "WIDTH", "HEIGHT"), ("W1", "900", "2100")):
        for text, x in zip(row, (50.0, 150.0, 250.0)):
            page.insert_text(fitz.Point(x, y), text, color=(0, 0, 0))
        y += 30.0
    doc.save(path)
    doc.close()


def test_item35_shadow_composes_schedule_binding_and_family_mark_counts(tmp_path) -> None:
    pdf_path = tmp_path / "item35-classified-window.pdf"
    _write_classified_window_drawing(pdf_path)

    shadow = collect_item35_authority_shadow(
        pdf_path,
        document_id="item35-classified-window",
        pages=(0,),
    )

    assert shadow["status"] == "evidence_present"
    assert shadow["semantic_opening_count"] == 1
    assert shadow["classified_opening_count"] == 1
    assert shadow["opening_family_counts"] == {"window": 1}
    assert shadow["opening_mark_counts"] == {"W1": 1}
    assert any(
        item["status"] == "corroborated" and item["tag_mark"] == "W1"
        for item in shadow["schedule_binding_statuses"]
    )

def test_live_extractor_populates_item35_shadow_without_publishing_opening_count(tmp_path) -> None:
    pdf_path = tmp_path / "live-item35-shadow.pdf"
    _write_minimal_drawing(pdf_path)

    extractor = GenericPlanReaderExtractor()
    predictions = extractor.extract_from_pdf(pdf_path)

    # No schedule/dimension/quantity evidence exists in this fixture. Executing
    # Item 35 must not manufacture a commercial opening prediction.
    assert not [
        prediction
        for prediction in predictions
        if prediction.trade_type in {"doors", "windows"}
    ]

    shadow = extractor.item35_authority_shadow
    assert shadow["status"] == "evidence_present"
    assert shadow["semantic_opening_count"] == 1
    assert shadow["physical_opening_universe_complete"] is True
    assert shadow["commercial_count_unlocked"] is True
    assert shadow["generic_count"] == 1
    assert extractor.extraction_status["item35_authority_shadow"] == "evidence_present"


def test_scoped_live_extraction_runs_item35_only_on_requested_pages(tmp_path) -> None:
    pdf_path = tmp_path / "scoped-live-item35-shadow.pdf"
    _write_minimal_drawing(pdf_path)

    extractor = GenericPlanReaderExtractor()
    predictions = extractor.extract_from_pdf(pdf_path, pages=[0])

    assert not [
        prediction
        for prediction in predictions
        if prediction.trade_type in {"doors", "windows"}
    ]
    shadow = extractor.item35_authority_shadow
    assert shadow["status"] == "evidence_present"
    assert shadow["semantic_opening_count"] == 1
    assert shadow["visible_observation_count"] == 6
    assert shadow["physical_opening_universe_complete"] is True
    assert shadow["commercial_count_unlocked"] is True
    assert shadow["generic_count_status"] == "corroborated"
    assert shadow["generic_count"] == 1
    assert extractor.extraction_status["item35_authority_shadow"] == "evidence_present"


def test_live_extractor_publishes_only_fully_corroborated_item35_mark(tmp_path) -> None:
    pdf_path = tmp_path / "live-item35-authoritative-window.pdf"
    _write_classified_window_drawing(pdf_path)

    extractor = GenericPlanReaderExtractor()
    predictions = {prediction.tag: prediction for prediction in extractor.extract_from_pdf(pdf_path)}

    assert "W1" in predictions, extractor.item35_authority_shadow
    window = predictions["W1"]
    assert window.trade_type == "windows"
    assert window.quantity == 1.0
    assert window.dimensions == [900.0, 2100.0]
    assert (window.metadata or {}).get("derivation") == "item35_source_authenticated_opening_mark"
    assert (window.metadata or {}).get("authority") == "item35_generic_opening_count"
    assert (window.metadata or {}).get("physical_opening_universe_complete") is True
    assert (window.metadata or {}).get("all_members_classified") is True


def test_item35_conflicting_schedule_dimensions_never_publish_mark_prediction(tmp_path) -> None:
    pdf_path = tmp_path / "item35-conflicting-window-size.pdf"
    doc = fitz.open()
    page = doc.new_page(width=700, height=650)
    page.insert_text(fitz.Point(40, 40), "GROUND FLOOR PLAN", color=(0, 0, 0))
    _draw_opening(page)
    page.insert_text(fitz.Point(112, 106), "W1", color=(0, 0, 0))

    y = 470.0
    for row in (
        ("MARK", "WIDTH", "HEIGHT"),
        ("W1", "900", "2100"),
        ("W1", "1200", "2100"),
    ):
        for text, x in zip(row, (50.0, 150.0, 250.0)):
            page.insert_text(fitz.Point(x, y), text, color=(0, 0, 0))
        y += 30.0
    doc.save(pdf_path)
    doc.close()

    shadow = collect_item35_authority_shadow(
        pdf_path,
        document_id="item35-conflicting-window-size",
        pages=(0,),
    )
    assert "W1" not in shadow["opening_mark_predictions"]

    extractor = GenericPlanReaderExtractor()
    predictions = {prediction.tag: prediction for prediction in extractor.extract_from_pdf(pdf_path)}
    assert not (
        "W1" in predictions
        and (predictions["W1"].metadata or {}).get("derivation")
        == "item35_source_authenticated_opening_mark"
    )
