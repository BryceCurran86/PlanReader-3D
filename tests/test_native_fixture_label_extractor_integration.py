from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from pb_native_fixture_label_evidence import count_standalone_chalkboard_spans
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


def _add_drawing_context(page: fitz.Page) -> None:
    page.insert_text((40, 30), "FLOOR PLAN", fontsize=12)
    for index in range(6):
        page.insert_text(
            (40, 48 + index * 12),
            f"DRAWING REFERENCE GENERAL NOTE {index}: VERIFY ALL DIMENSIONS ON SITE.",
            fontsize=8,
        )


def _save_pdf(tmp_path: Path, draw) -> Path:
    pdf_path = tmp_path / "fixture-label-evidence.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    _add_drawing_context(page)
    draw(page)
    doc.save(pdf_path)
    doc.close()
    return pdf_path


def _chalkboard_prediction(pdf_path: Path):
    predictions = GenericPlanReaderExtractor().extract_from_pdf(pdf_path)
    matches = [prediction for prediction in predictions if prediction.tag == "chalkboard"]
    assert len(matches) == 1
    return matches[0]


def _draw_flattened_two_labels(page: fitz.Page) -> None:
    # Close same-baseline native text objects flatten into one plain-text line,
    # while a style boundary preserves two structured spans / source bboxes.
    page.insert_text((50, 150), "Chalkboard", fontsize=11)
    page.insert_text((110, 150), "Chalkboard", fontsize=11, color=(1, 0, 0))


def test_extractor_recovers_two_native_labels_flattened_into_one_plain_text_line(
    tmp_path: Path,
) -> None:
    pdf_path = _save_pdf(tmp_path, _draw_flattened_two_labels)

    with fitz.open(pdf_path) as doc:
        page = doc[0]
        page_text = page.get_text("text")
        assert GenericPlanReaderExtractor._standalone_chalkboard_label_count(page_text) == 0
        assert count_standalone_chalkboard_spans(page.get_text("dict")) == 2

    prediction = _chalkboard_prediction(pdf_path)
    assert prediction.quantity == 2.0
    assert prediction.dimensions is None


def test_extractor_uses_max_not_sum_when_plain_text_already_has_two_labels(
    tmp_path: Path,
) -> None:
    def draw(page: fitz.Page) -> None:
        page.insert_text((50, 150), "Chalkboard", fontsize=11)
        page.insert_text((50, 180), "Chalkboard", fontsize=11, color=(1, 0, 0))

    pdf_path = _save_pdf(tmp_path, draw)

    with fitz.open(pdf_path) as doc:
        page = doc[0]
        page_text = page.get_text("text")
        assert GenericPlanReaderExtractor._standalone_chalkboard_label_count(page_text) == 2
        assert count_standalone_chalkboard_spans(page.get_text("dict")) == 2

    assert _chalkboard_prediction(pdf_path).quantity == 2.0


def test_dimension_note_is_not_promoted_to_native_instance_count(tmp_path: Path) -> None:
    def draw(page: fitz.Page) -> None:
        page.insert_text((50, 150), "2400mm x 1200mm chalkboard", fontsize=11)
        page.insert_text(
            (50, 180),
            "NOTE: provide chalkboard finish only where explicitly dimensioned.",
            fontsize=9,
        )

    pdf_path = _save_pdf(tmp_path, draw)

    with fitz.open(pdf_path) as doc:
        page = doc[0]
        assert count_standalone_chalkboard_spans(page.get_text("dict")) == 0

    prediction = _chalkboard_prediction(pdf_path)
    assert prediction.quantity == 1.0
    assert prediction.dimensions == [2400.0, 1200.0]


@pytest.mark.parametrize("documented_count", [2, 3])
def test_explicit_documented_count_has_priority_and_is_never_summed_with_native_labels(
    tmp_path: Path,
    documented_count: int,
) -> None:
    def draw(page: fitz.Page) -> None:
        _draw_flattened_two_labels(page)
        page.insert_text(
            (50, 190),
            f"{documented_count} No chalkboards",
            fontsize=10,
        )

    pdf_path = _save_pdf(tmp_path, draw)
    prediction = _chalkboard_prediction(pdf_path)

    assert prediction.quantity == float(documented_count)
    assert prediction.quantity != float(documented_count + 2)


def test_structured_evidence_failure_fails_closed_to_existing_exact_line_count(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def draw(page: fitz.Page) -> None:
        page.insert_text((50, 150), "Chalkboard", fontsize=11)

    pdf_path = _save_pdf(tmp_path, draw)

    import pb_native_fixture_label_evidence

    def fail_structured_evidence(_text_dict):
        raise RuntimeError("synthetic structured-text failure")

    monkeypatch.setattr(
        pb_native_fixture_label_evidence,
        "count_standalone_chalkboard_spans",
        fail_structured_evidence,
    )

    prediction = _chalkboard_prediction(pdf_path)
    assert prediction.quantity == 1.0
