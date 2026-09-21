"""Production integration tests for the Item 35 authority shadow."""
from __future__ import annotations

import fitz

from pb_generic_opening_count_authority import (
    GENERIC_OPENING_COUNT_COMPLETENESS_NOT_SOURCE_AUTHENTICATED,
)
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
    assert shadow["physical_opening_universe_complete"] is False
    assert shadow["commercial_count_unlocked"] is False
    assert shadow["generic_count_status"] == "abstained"
    assert (
        GENERIC_OPENING_COUNT_COMPLETENESS_NOT_SOURCE_AUTHENTICATED
        in shadow["generic_count_reason_codes"]
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
    assert shadow["commercial_count_unlocked"] is False
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
    assert shadow["commercial_count_unlocked"] is False
    assert extractor.extraction_status["item35_authority_shadow"] == "evidence_present"
