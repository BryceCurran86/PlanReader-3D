"""A03 & A08: bounded PNG->RGB/BGR decode cache, pixmap->PIL direct parity, integer green mask."""
from __future__ import annotations

import io
import cv2
import fitz
import numpy as np
import pytest
from PIL import Image

import pb_opening_local_g17_wall_shadow as g17
import pb_raster_unchanged_band_segments as ubs


def _make_png(val: int) -> bytes:
    arr = np.full((16, 20, 3), val, dtype=np.uint8)
    ok, buf = cv2.imencode(".png", arr)
    assert ok
    return buf.tobytes()


def test_g17_rgb_and_unchanged_bgr_caches_are_readonly_bounded_and_exact(monkeypatch) -> None:
    g17._DECODED_PNG_RGB_CACHE.clear()
    ubs._DECODED_PNG_BGR_CACHE.clear()

    png_a = _make_png(42)
    png_b = _make_png(99)

    rgb1 = g17._decode_png_rgb_cached(png_a)
    rgb2 = g17._decode_png_rgb_cached(png_a)
    assert rgb1 is rgb2
    assert rgb1.flags.writeable is False
    with pytest.raises(ValueError):
        rgb1[0, 0, 0] = 0
    assert np.array_equal(rgb1, np.full((16, 20, 3), 42, dtype=np.uint8))

    bgr1 = ubs._decode_png_bgr_cached(png_a)
    bgr2 = ubs._decode_png_bgr_cached(png_a)
    assert bgr1 is bgr2 and bgr1 is not None
    assert bgr1.flags.writeable is False
    with pytest.raises(ValueError):
        bgr1[0, 0, 0] = 0

    # Bounded LRU eviction check
    monkeypatch.setattr(g17, "_DECODED_PNG_RGB_CACHE_MAX", 2)
    for v in (10, 20, 30, 40):
        g17._decode_png_rgb_cached(_make_png(v))
    assert len(g17._DECODED_PNG_RGB_CACHE) <= 2

    monkeypatch.setattr(ubs, "_DECODED_PNG_BGR_CACHE_MAX", 2)
    for v in (10, 20, 30, 40):
        ubs._decode_png_bgr_cached(_make_png(v))
    assert len(ubs._DECODED_PNG_BGR_CACHE) <= 2

    # Distinct PNGs never collide
    assert not np.array_equal(g17._decode_png_rgb_cached(png_a), g17._decode_png_rgb_cached(png_b))


def test_pixmap_frombytes_matches_png_roundtrip_pixel_exact() -> None:
    doc = fitz.open()
    page = doc.new_page(width=120, height=80)
    page.draw_rect(fitz.Rect(10, 10, 110, 70), color=(0.1, 0.2, 0.3), fill=(0.8, 0.9, 0.7))
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    try:
        via_png = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        direct = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        assert via_png.size == direct.size
        assert via_png.tobytes() == direct.tobytes()
    finally:
        del pix
        doc.close()


def test_footprint_integer_green_mask_matches_float_exhaustively() -> None:
    v = np.arange(256, dtype=np.int16)
    g = v[:, None]
    other = v[None, :]
    assert np.array_equal(g > other * 1.25, g * 4 > other * 5)
    assert np.array_equal(g > other * 1.08, g * 25 > other * 27)
