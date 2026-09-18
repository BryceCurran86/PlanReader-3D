from pathlib import Path

import fitz

from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


def _drawing_with_external_key_finish(tmp_path: Path) -> Path:
    path = tmp_path / "external_key_finish.pdf"
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text((40, 40), "GROUND FLOOR PLAN", fontsize=12)
    page.insert_text((40, 70), "10,000", fontsize=10)
    page.insert_text((140, 70), "8,000", fontsize=10)
    page.insert_text(
        (40, 110),
        "150mm thick concrete walling blocks key to finish externally.",
        fontsize=10,
    )
    doc.save(path)
    doc.close()
    return path


def test_external_key_finish_keyword_does_not_publish_copied_wall_area(
    tmp_path: Path,
) -> None:
    pdf = _drawing_with_external_key_finish(tmp_path)
    extractor = GenericPlanReaderExtractor()
    predictions = extractor.extract_from_pdf(pdf)
    by_tag = {prediction.tag: prediction for prediction in predictions}

    assert "perimeter_walling" in by_tag
    assert by_tag["perimeter_walling"].quantity is not None

    # A specification keyword is not measurement authority.  Until a
    # source-bound finish-face area exists, no live quantity may be minted by
    # copying perimeter_walling.
    assert "external_key_pointing" not in by_tag
    assert (
        extractor.extraction_status.get("external_key_pointing")
        == "evidence_present_unresolved"
    )
