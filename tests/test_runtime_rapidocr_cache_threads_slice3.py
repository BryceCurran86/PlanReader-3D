"""Tests for Runtime Slice 3 RapidOCR bounded thread config & RGB-SHA LRU cache."""
from __future__ import annotations

from types import SimpleNamespace
from PIL import Image

from pb_portable_raster_ocr_authority import RapidOCRBackend


def test_rapidocr_passes_bounded_ort_threads_and_falls_back_for_zero_arg_mock(monkeypatch) -> None:
    RapidOCRBackend._reset_engine_cache_for_tests()
    seen_params: list[dict | None] = []

    class _ParamEngine:
        def __init__(self, *, params=None):
            seen_params.append(params)

        def __call__(self, array, **kwargs):
            return SimpleNamespace(txts=["A"], boxes=[[[0, 0], [10, 0], [10, 10], [0, 10]]], scores=[0.95])

    monkeypatch.setattr(RapidOCRBackend, "_load_rapidocr", staticmethod(lambda: SimpleNamespace(RapidOCR=_ParamEngine)))
    try:
        eng = RapidOCRBackend._get_engine()
        assert isinstance(eng, _ParamEngine)
        assert seen_params == [dict(RapidOCRBackend._DEFAULT_ORT_PARAMS)]
    finally:
        RapidOCRBackend._reset_engine_cache_for_tests()

    # Zero-arg mock constructor must continue to work cleanly via TypeError fallback
    class _ZeroArgEngine:
        def __init__(self):
            pass

    monkeypatch.setattr(RapidOCRBackend, "_load_rapidocr", staticmethod(lambda: SimpleNamespace(RapidOCR=_ZeroArgEngine)))
    try:
        eng2 = RapidOCRBackend._get_engine()
        assert isinstance(eng2, _ZeroArgEngine)
    finally:
        RapidOCRBackend._reset_engine_cache_for_tests()


def test_rapidocr_rgb_sha_cache_hits_on_identical_pixels_and_isolates_dpi_detect_and_pixels(monkeypatch) -> None:
    RapidOCRBackend._reset_engine_cache_for_tests()
    calls: list[tuple[tuple[int, ...], bool]] = []

    class _CountingEngine:
        def __init__(self, *, params=None):
            self.use_det = True

        def update_params(self, **kwargs):
            if "use_det" in kwargs:
                self.use_det = kwargs["use_det"]

        def __call__(self, array, **kwargs):
            det = kwargs.get("use_det", True)
            calls.append((tuple(array.shape), bool(det)))
            return SimpleNamespace(
                txts=["3600"],
                boxes=[[[1, 2], [20, 2], [20, 12], [1, 12]]] if det else None,
                scores=[0.97],
            )

    monkeypatch.setattr(RapidOCRBackend, "_load_rapidocr", staticmethod(lambda: SimpleNamespace(RapidOCR=_CountingEngine)))
    try:
        backend = RapidOCRBackend()
        img1 = Image.new("RGB", (40, 20), color=(255, 255, 255))
        img1_same = Image.new("RGB", (40, 20), color=(255, 255, 255))
        img2_diff = Image.new("RGB", (40, 20), color=(240, 240, 240))

        r1 = backend.extract_lines(img1, dpi=216, detect=True)
        r2 = backend.extract_lines(img1_same, dpi=216, detect=True)
        assert r1 == r2
        assert len(calls) == 1  # exact pixel + dpi + detect hit

        # Different DPI must miss cache (pt scaling differs)
        r_dpi = backend.extract_lines(img1, dpi=300, detect=True)
        assert len(calls) == 2
        assert r_dpi[0].bbox_pt != r1[0].bbox_pt

        # Different detect mode must miss cache
        r_nodet = backend.extract_lines(img1, dpi=216, detect=False)
        assert len(calls) == 3
        assert len(r_nodet) == 1

        # Different pixel bytes must miss cache
        backend.extract_lines(img2_diff, dpi=216, detect=True)
        assert len(calls) == 4

        # Reset clears pixel cache cleanly
        RapidOCRBackend._reset_engine_cache_for_tests()
        backend.extract_lines(img1, dpi=216, detect=True)
        assert len(calls) == 5
    finally:
        RapidOCRBackend._reset_engine_cache_for_tests()
