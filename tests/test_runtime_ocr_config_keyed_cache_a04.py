"""A04: OCR cache keys include exact model/config signature and preserve provenance."""
from __future__ import annotations

from types import SimpleNamespace
from PIL import Image

from pb_portable_raster_ocr_authority import RapidOCRBackend


def test_ocr_cache_isolates_incompatible_engine_config_and_preserves_provenance(monkeypatch) -> None:
    RapidOCRBackend._reset_engine_cache_for_tests()
    calls = 0

    class _FakeEngine:
        def __init__(self) -> None:
            self.use_det = True
            self.use_cls = False
            self.use_rec = True
            self.text_score = 0.5
            self.box_thresh = 0.5
            self.lang_type = "en"

        def __call__(self, array, **kwargs):
            nonlocal calls
            calls += 1
            return SimpleNamespace(
                txts=[f"TEXT_{calls}_S{self.text_score}"],
                boxes=[[[0.0, 0.0], [20.0, 0.0], [20.0, 10.0], [0.0, 10.0]]],
                scores=[0.98],
            )

    fake_engine = _FakeEngine()
    monkeypatch.setattr(
        RapidOCRBackend,
        "_load_rapidocr",
        staticmethod(lambda: SimpleNamespace(RapidOCR=lambda **kw: fake_engine)),
    )

    backend = RapidOCRBackend()
    img = Image.new("RGB", (32, 16), color=(255, 255, 255))

    # First call populates cache; second call with identical config hits cache
    out1 = backend.extract_lines(img, dpi=144, detect=True)
    out2 = backend.extract_lines(img, dpi=144, detect=True)
    assert calls == 1
    assert out1 == out2
    assert out1[0].text == "TEXT_1_S0.5"
    assert out1[0].confidence == 0.98
    assert out1[0].bbox_px == (0.0, 0.0, 20.0, 10.0)
    assert out1[0].bbox_pt == (0.0, 0.0, 10.0, 5.0)

    # Changing config (text_score / use_cls) MUST miss cache and re-run engine
    fake_engine.text_score = 0.8
    out3 = backend.extract_lines(img, dpi=144, detect=True)
    assert calls == 2
    assert out3[0].text == "TEXT_2_S0.8"

    fake_engine.use_cls = True
    out4 = backend.extract_lines(img, dpi=144, detect=True)
    assert calls == 3
    assert out4 != out3

    # Different DPI MUST miss cache (pt geometry provenance depends on DPI)
    out5 = backend.extract_lines(img, dpi=288, detect=True)
    assert calls == 4
    assert out5[0].bbox_pt == (0.0, 0.0, 5.0, 2.5)

    RapidOCRBackend._reset_engine_cache_for_tests()
