from __future__ import annotations

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
