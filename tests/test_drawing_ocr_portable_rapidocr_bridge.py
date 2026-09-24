from __future__ import annotations

from PIL import Image

from pb_drawing_ocr_evidence_layer import DrawingOCREngine
from pb_portable_raster_ocr_authority import OCRLine, RapidOCRBackend


def test_drawing_ocr_uses_available_portable_rapidocr(monkeypatch) -> None:
    monkeypatch.setattr(RapidOCRBackend, "is_available", lambda self: True)
    monkeypatch.setattr(
        RapidOCRBackend,
        "extract_lines",
        lambda self, image, dpi=150: (
            OCRLine(
                text="POLYTHENE SHEET 1000g",
                confidence=0.99,
                bbox_px=(10.0, 20.0, 210.0, 40.0),
            ),
        ),
    )

    image = Image.new("RGB", (300, 100), "white")
    lines = DrawingOCREngine().recognize_pil_image(image)

    assert [line["text"] for line in lines] == ["POLYTHENE SHEET 1000g"]
    assert lines[0]["bounding_box"] == [10.0, 20.0, 210.0, 40.0]
    assert 0.0 < lines[0]["confidence"] <= 0.99


def test_drawing_ocr_skips_unavailable_portable_rapidocr(monkeypatch) -> None:
    monkeypatch.setattr(RapidOCRBackend, "is_available", lambda self: False)
    monkeypatch.setattr(
        DrawingOCREngine,
        "_recognize_with_tesseract",
        staticmethod(lambda image, quality: []),
    )

    image = Image.new("RGB", (300, 100), "white")
    assert DrawingOCREngine().recognize_pil_image(image) == []
