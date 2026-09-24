from __future__ import annotations

import fitz

from pb_drawing_ocr_evidence_layer import DrawingOCREngine
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


def test_extractor_uses_memory_bounded_ocr_raster_dpi(monkeypatch) -> None:
    seen: dict[str, int] = {}

    def fake_recognize_page_rect(self, page, clip_rect=None, dpi=150):
        seen["dpi"] = int(dpi)
        return [{"text": "POLYTHENE SHEET 1000g"}]

    monkeypatch.setattr(
        DrawingOCREngine,
        "recognize_page_rect",
        fake_recognize_page_rect,
    )

    extractor = GenericPlanReaderExtractor()
    text = extractor._ocr_text_for_page(object(), 0)

    assert text == "POLYTHENE SHEET 1000g"
    assert seen["dpi"] == 120


def test_page_ocr_renders_grayscale_before_backend() -> None:
    seen: dict[str, object] = {}

    def fake_ocr(image):
        seen["mode"] = image.mode
        seen["size"] = image.size
        return []

    doc = fitz.open()
    try:
        page = doc.new_page(width=612.0, height=792.0)
        engine = DrawingOCREngine(custom_ocr_func=fake_ocr)
        assert engine.recognize_page_rect(page, dpi=120) == []
    finally:
        doc.close()

    assert seen["mode"] == "L"
    assert seen["size"][0] > 0
    assert seen["size"][1] > 0


def test_memory_bounded_ocr_dpi_keeps_a3_at_preferred_resolution() -> None:
    doc = fitz.open()
    try:
        page = doc.new_page(width=842.0, height=1191.0)
        dpi = GenericPlanReaderExtractor._memory_bounded_ocr_dpi(page)
    finally:
        doc.close()

    assert dpi == 120


def test_memory_bounded_ocr_dpi_reduces_large_sheet_pixel_area() -> None:
    doc = fitz.open()
    try:
        page = doc.new_page(width=1684.0, height=2384.0)
        dpi = GenericPlanReaderExtractor._memory_bounded_ocr_dpi(page)
    finally:
        doc.close()

    assert 60 <= dpi < 120
    raster_pixels = 1684.0 * 2384.0 * (dpi / 72.0) ** 2
    assert raster_pixels <= 3_100_000


def test_ocr_fallback_has_bounded_page_budget(monkeypatch) -> None:
    calls: list[int] = []

    def fake_recognize_page_rect(self, page, clip_rect=None, dpi=150):
        calls.append(int(dpi))
        return [{"text": "OCR EVIDENCE"}]

    monkeypatch.setattr(
        DrawingOCREngine,
        "recognize_page_rect",
        fake_recognize_page_rect,
    )

    extractor = GenericPlanReaderExtractor()
    texts = [
        extractor._ocr_text_for_page(object(), page_index)
        for page_index in range(10)
    ]

    assert texts[:8] == ["OCR EVIDENCE"] * 8
    assert texts[8:] == ["", ""]
    assert len(calls) == 8
    assert extractor._ocr_text_for_page(object(), 0) == "OCR EVIDENCE"
    assert len(calls) == 8
