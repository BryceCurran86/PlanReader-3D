"""Tests for pb_source_ocr_glyph_fastpath."""

from pb_portable_raster_ocr_authority import OCRLine, RapidOCRBackend
from pb_source_ocr_glyph_fastpath import get_source_words_with_glyph_fastpath


class DummyPageWithWords:
    def __init__(self, words):
        self._words = words

    def get_text(self, kind="words"):
        if kind == "words":
            return self._words
        return ""


def test_native_words_with_arch_keywords_bypass_ocr(monkeypatch):
    words = [
        (10.0, 10.0, 50.0, 20.0, "BEDROOM", 0, 0, 0),
        (60.0, 10.0, 90.0, 20.0, "1", 0, 0, 1),
    ]
    page = DummyPageWithWords(words)

    called = False

    def fake_extract(*args, **kwargs):
        nonlocal called
        called = True
        return ()

    monkeypatch.setattr(RapidOCRBackend, "extract_lines", fake_extract)
    got = get_source_words_with_glyph_fastpath(page)
    assert len(got) == 2
    assert got[0][4] == "BEDROOM"
    assert not called


def test_native_words_without_arch_keywords_use_ocr(monkeypatch):
    words = [
        (10.0, 10.0, 50.0, 20.0, "PROJECT", 0, 0, 0),
        (60.0, 10.0, 90.0, 20.0, "NOTES", 0, 0, 1),
    ]
    page = DummyPageWithWords(words)

    # Mock pixmap and RapidOCRBackend
    class DummyPixmap:
        def tobytes(self, fmt):
            import io

            from PIL import Image
            buf = io.BytesIO()
            Image.new("RGB", (100, 100), color=(255, 255, 255)).save(buf, format="PNG")
            return buf.getvalue()

    page.get_pixmap = lambda dpi=150: DummyPixmap()

    ocr_lines = (
        OCRLine(text="W2", confidence=0.9, bbox_px=(200, 100, 220, 110), bbox_pt=(100.0, 50.0, 110.0, 55.0)),
        OCRLine(text="BEDROOM 2", confidence=0.95, bbox_px=(300, 200, 400, 220), bbox_pt=(150.0, 100.0, 200.0, 110.0)),
    )
    monkeypatch.setattr(RapidOCRBackend, "is_available", lambda self: True)
    monkeypatch.setattr(RapidOCRBackend, "extract_lines", lambda self, img, dpi=150: ocr_lines)

    got = get_source_words_with_glyph_fastpath(page)
    # 2 native + (W2) + (BEDROOM 2 full + BEDROOM + 2) = 2 + 1 + 3 = 6 words
    assert len(got) == 6
    texts = [w[4] for w in got]
    assert "PROJECT" in texts
    assert "NOTES" in texts
    assert "W2" in texts
    assert "BEDROOM 2" in texts
    assert "BEDROOM" in texts
    assert "2" in texts


def test_ocr_unavailable_returns_native_words(monkeypatch):
    words = [
        (10.0, 10.0, 50.0, 20.0, "NOTES", 0, 0, 0),
    ]
    page = DummyPageWithWords(words)
    monkeypatch.setattr(RapidOCRBackend, "is_available", lambda self: False)

    got = get_source_words_with_glyph_fastpath(page)
    assert len(got) == 1
    assert got[0][4] == "NOTES"
