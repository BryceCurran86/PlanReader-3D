"""Regression tests for fail-closed external key-pointing publication.

A finish keyword ("key to finish externally", "external key pointing to
exposed masonry", ...) establishes at most that a finish is specified
somewhere on the drawing. It does not supply the measured wall-face extent
that finish covers, so GenericPlanReaderExtractor must not copy
perimeter_walling's quantity into external_key_pointing merely because the
keyword appears in page text. The keyword is kept as visible diagnostic
evidence (extraction_status["external_key_pointing"] ==
"evidence_present_unresolved") rather than silently dropped, but no
commercial quantity is published until a producer-owned finish/face-binding
authority can supply an independently measured extent.
"""
from __future__ import annotations

from pathlib import Path

import fitz

from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


def _make_plan(tmp_path: Path, note: str, name: str = "key-pointing.pdf") -> Path:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        "\n".join(
            [
                "GROUND FLOOR PLAN",
                "SCALE 1:100",
                "10,000",
                "6,000",
                note,
            ]
        ),
        fontsize=11,
    )
    path = tmp_path / name
    doc.save(str(path))
    doc.close()
    return path


def _extract(path: Path) -> tuple[dict, GenericPlanReaderExtractor]:
    extractor = GenericPlanReaderExtractor()
    predictions = extractor.extract_from_pdf(path)
    return {pred.tag: pred for pred in predictions}, extractor


def test_key_to_finish_keyword_does_not_copy_wall_area_to_pointing(
    tmp_path: Path,
) -> None:
    preds, extractor = _extract(
        _make_plan(
            tmp_path,
            "150mm thick concrete walling blocks key to finish externally.",
        )
    )
    assert "external_key_pointing" not in preds
    assert (
        extractor.extraction_status.get("external_key_pointing")
        == "evidence_present_unresolved"
    )


def test_explicit_key_pointing_words_without_face_extent_still_fail_closed(
    tmp_path: Path,
) -> None:
    preds, extractor = _extract(
        _make_plan(
            tmp_path,
            "External key pointing to exposed masonry walls.",
            name="explicit-key-pointing.pdf",
        )
    )
    assert "external_key_pointing" not in preds
    assert (
        extractor.extraction_status.get("external_key_pointing")
        == "evidence_present_unresolved"
    )


def test_unrelated_plan_never_mints_external_key_pointing(tmp_path: Path) -> None:
    preds, extractor = _extract(
        _make_plan(tmp_path, "General masonry note.", name="unrelated.pdf")
    )
    assert "external_key_pointing" not in preds
    # No finish keyword at all: not even the diagnostic-unresolved status
    # should appear, since there is no evidence to be unresolved about.
    assert "external_key_pointing" not in extractor.extraction_status


def test_key_finish_keyword_does_not_disturb_perimeter_walling(
    tmp_path: Path,
) -> None:
    """Sanity check: removing the unsafe copy must not regress the
    independent perimeter_walling extraction it used to copy from -- this
    minimal fixture has no opening-deduction evidence so Item 21a's own
    fail-closed gate leaves quantity=None regardless, but the prediction
    itself (with its own diagnostic metadata) must still be produced."""
    preds, _ = _extract(
        _make_plan(
            tmp_path,
            "150mm thick concrete walling blocks key to finish externally.",
            name="perimeter-sanity.pdf",
        )
    )
    assert "perimeter_walling" in preds
