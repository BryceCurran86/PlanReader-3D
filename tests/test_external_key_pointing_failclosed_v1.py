"""Regression tests for fail-closed external key-pointing publication.

A finish keyword may establish that a finish is mentioned, but it cannot
supply measured wall-face extent. The legacy GenericPlanReaderExtractor must
not copy perimeter-wall area into external_key_pointing until an exact
producer-owned finish/face binding resolves.
"""

from __future__ import annotations

from pathlib import Path

import fitz

from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


def _make_plan(tmp_path: Path, note: str) -> Path:
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
    path = tmp_path / "key-pointing.pdf"
    doc.save(str(path))
    doc.close()
    return path


def _predictions(path: Path):
    return {
        pred.tag: pred
        for pred in GenericPlanReaderExtractor().extract_from_pdf(path)
    }


def test_key_to_finish_keyword_does_not_copy_wall_area_to_pointing(
    tmp_path: Path,
) -> None:
    preds = _predictions(
        _make_plan(
            tmp_path,
            "150mm thick concrete walling blocks key to finish externally.",
        )
    )
    assert "external_key_pointing" not in preds


def test_explicit_key_pointing_words_without_face_extent_still_fail_closed(
    tmp_path: Path,
) -> None:
    preds = _predictions(
        _make_plan(
            tmp_path,
            "External key pointing to exposed masonry walls.",
        )
    )
    assert "external_key_pointing" not in preds


def test_unrelated_plan_never_mints_external_key_pointing(
    tmp_path: Path,
) -> None:
    preds = _predictions(
        _make_plan(tmp_path, "General masonry note.")
    )
    assert "external_key_pointing" not in preds
