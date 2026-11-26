"""Tests for generic vector-outlined architectural drawing admission preflight shadow."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import fitz
import pytest

from pb_source_outlined_drawing_admission_shadow import (
    OutlinedDrawingAdmissionReport,
    evaluate_outlined_drawing_admission_shadow,
    select_role_pages_for_outlined_ocr_shadow,
)


def _make_outlined_pdf(*, border_titles: tuple[str, ...], drawings_per_page: int = 600, body_words: int = 0) -> bytes:
    doc = fitz.open()
    for title in border_titles:
        page = doc.new_page(width=1000.0, height=700.0)
        # Title block text in right/bottom border region
        page.insert_text((850.0, 650.0), title, fontsize=10)
        page.insert_text((850.0, 670.0), "SCALE 1:100", fontsize=9)
        for i in range(body_words):
            page.insert_text((60.0 + (i % 5) * 120.0, 60.0 + (i // 5) * 20.0), f"ROOM{i}", fontsize=8)
        shape = page.new_shape()
        for j in range(drawings_per_page):
            x = 50.0 + (j % 50) * 12.0
            y = 50.0 + (j // 50) * 12.0
            shape.draw_line(fitz.Point(x, y), fitz.Point(x + 8.0, y))
            shape.finish(color=(0, 0, 0), width=0.5)
        shape.commit()
    raw = doc.tobytes()
    doc.close()
    return raw


def test_admits_vector_outlined_drawing_set_and_abstains_missing_finishes() -> None:
    pdf_bytes = _make_outlined_pdf(
        border_titles=("GROUND FLOOR PLAN", "NORTH ELEVATION", "CROSS SECTION", "WINDOW SCHEDULE"),
        drawings_per_page=600,
        body_words=2,
    )
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    report = evaluate_outlined_drawing_admission_shadow(
        pdf_bytes,
        expected_source_sha256=sha,
        finish_specification_present=False,
    )
    assert isinstance(report, OutlinedDrawingAdmissionReport)
    assert report.status == "ADMITTED_FOR_OUTLINED_TEXT_OCR_SHADOW"
    assert report.page_count == 4
    assert report.outlined_page_count == 4
    assert report.geometry_admission_ready is True
    assert report.finish_authority_status == "ABSTAINED"
    assert report.finish_authority_reason == "material_specification_missing"
    assert report.commercial_projection_allowed is False
    assert report.shadow_only is True

    selected = select_role_pages_for_outlined_ocr_shadow(report)
    assert selected == (0, 1, 2, 3)

    with pytest.raises(ValueError):
        replace(report, commercial_projection_allowed=True)


def test_native_text_drawing_set_not_routed_to_outlined_ocr() -> None:
    pdf_bytes = _make_outlined_pdf(
        border_titles=("GROUND FLOOR PLAN",),
        drawings_per_page=600,
        body_words=45,
    )
    report = evaluate_outlined_drawing_admission_shadow(pdf_bytes)
    assert report.status == "NATIVE_TEXT_DRAWING_SET"
    assert report.outlined_page_count == 0
    assert report.geometry_admission_ready is False
    assert select_role_pages_for_outlined_ocr_shadow(report) == ()


def test_sha_mismatch_and_corrupted_pdf_abstain() -> None:
    pdf_bytes = _make_outlined_pdf(border_titles=("FLOOR PLAN",), drawings_per_page=600)
    r_sha = evaluate_outlined_drawing_admission_shadow(pdf_bytes, expected_source_sha256="0" * 64)
    assert r_sha.status == "ABSTAINED"
    assert "source_sha256_mismatch" in r_sha.reason_codes

    r_empty = evaluate_outlined_drawing_admission_shadow(b"")
    assert r_empty.status == "ABSTAINED"
    assert "empty_or_invalid_pdf_bytes" in r_empty.reason_codes

    r_bad = evaluate_outlined_drawing_admission_shadow(b"not-a-pdf")
    assert r_bad.status == "ABSTAINED"
    assert "unreadable_pdf_stream" in r_bad.reason_codes
