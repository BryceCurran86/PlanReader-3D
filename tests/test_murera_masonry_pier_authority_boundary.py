from __future__ import annotations

from pathlib import Path

import fitz

from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


def _extract_tags(pdf_path: Path) -> dict[str, object]:
    extractor = GenericPlanReaderExtractor()
    return {
        prediction.tag: prediction
        for prediction in extractor.extract_from_pdf(pdf_path)
    }


def _murera_like_unowned_shape_pdf(
    tmp_path: Path,
    *,
    include_explicit_count_text: bool = False,
) -> Path:
    """Synthetic source shaped after the real-source blocker, not its quantity.

    The real Murera source probe found a compact/elongated filled rectangle on
    the relevant drawing page plus nearby numeric tokens, but no bound member
    role or source instance mark. This fixture preserves only that failure
    class; it does not copy any expected benchmark quantity.
    """
    doc = fitz.open()
    page = doc.new_page(width=792, height=612)
    page.insert_text((72, 72), "GROUND FLOOR PLAN\nSCALE 1:100", fontsize=10)

    # A line-like/elongated closed primitive is geometry only. Nearby axis-like
    # tokens are deliberately present to prove that proximity does not mint a
    # physical masonry-pier observation.
    page.draw_rect(
        fitz.Rect(369.5, 108.2, 382.0, 108.6),
        color=(0, 0, 0),
        fill=(0, 0, 0),
        width=0.5,
    )
    page.insert_text((393.0, 132.0), "AT 4", fontsize=8)

    if include_explicit_count_text:
        page.insert_text((72, 110), "7 Nos masonry piers", fontsize=9)

    path = tmp_path / "murera_like_unowned_masonry_pier_evidence.pdf"
    doc.save(str(path))
    doc.close()
    return path


def test_unowned_pier_like_geometry_and_nearby_numbers_do_not_publish_masonry_piers(
    tmp_path: Path,
) -> None:
    pdf_path = _murera_like_unowned_shape_pdf(tmp_path)
    predictions = _extract_tags(pdf_path)
    assert "masonry_piers" not in predictions


def test_explicit_count_plus_unowned_geometry_still_cannot_publish_masonry_piers(
    tmp_path: Path,
) -> None:
    pdf_path = _murera_like_unowned_shape_pdf(
        tmp_path,
        include_explicit_count_text=True,
    )
    predictions = _extract_tags(pdf_path)
    assert "masonry_piers" not in predictions
