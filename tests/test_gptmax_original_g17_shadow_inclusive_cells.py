"""Original RGB-positive G17 cells remain source shadow; production unchanged."""
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

import pb_raster_unchanged_band_segments as capture
from pb_raster_opening_source_primitives import (
    RASTER_WALL_BAND_END,
    RASTER_WALL_BAND_FACE,
)


def _png(rgb):
    ok, image = cv2.imencode(".png", rgb)
    assert ok
    return image.tobytes()


def _source_rectangle(monkeypatch, *, painted_columns):
    left, top, bottom = 20, 50, 56
    right = left + painted_columns - 1
    image = np.full((120, 120, 3), 255, dtype=np.uint8)
    image[top:bottom+1, left:right+1] = 0
    primitives = (
        SimpleNamespace(primitive_kind=RASTER_WALL_BAND_FACE,
                        pixel_geometry=(left, top, right, top)),
        SimpleNamespace(primitive_kind=RASTER_WALL_BAND_FACE,
                        pixel_geometry=(left, bottom, right, bottom)),
        SimpleNamespace(primitive_kind=RASTER_WALL_BAND_END,
                        pixel_geometry=(left, top, left, bottom)),
        SimpleNamespace(primitive_kind=RASTER_WALL_BAND_END,
                        pixel_geometry=(right, top, right, bottom)),
    )
    monkeypatch.setattr(capture, "detect_raster_opening_source_primitives",
                        lambda *args, **kwargs: primitives)
    return image, (left, top, right, bottom)


@pytest.mark.parametrize("columns, default_expected, shadow_expected", [
    (16, False, False),
    (17, False, True),
    (18, True, True),
    (30, True, True),
])
def test_only_explicit_source_shadow_can_count_inclusive_original_painted_cells(
    monkeypatch, columns, default_expected, shadow_expected,
):
    image, bbox = _source_rectangle(monkeypatch, painted_columns=columns)
    source_png = _png(image)
    production = capture.detect_unchanged_terminal_band_segments(
        source_png, source_png, dpi=300,
    )
    shadow = capture.detect_unchanged_terminal_band_segments(
        source_png, source_png, dpi=300, shadow_inclusive_source_cells=True,
    )
    assert bool(production) is default_expected
    assert bool(shadow) is shadow_expected
    if production:
        assert production == shadow
    if shadow:
        assert len(shadow) == 1
        assert shadow[0].pixel_support_bounds == bbox
    # The input original producer images must never be modified.
    assert np.array_equal(cv2.imdecode(np.frombuffer(source_png, np.uint8), 1), image)


def test_original_full_page_overlay_change_cannot_create_missing_source_claim(monkeypatch):
    source, _ = _source_rectangle(monkeypatch, painted_columns=17)
    full = source.copy()
    full[52:55, 21:36, 1] = 127  # Different RGB from images-only original
    source_only = capture.detect_unchanged_terminal_band_segments(
        _png(source), _png(source), dpi=300,
        shadow_inclusive_source_cells=True,
    )
    changed = capture.detect_unchanged_terminal_band_segments(
        _png(source), _png(full), dpi=300,
        shadow_inclusive_source_cells=True,
    )
    assert len(source_only) == 1
    assert changed == ()


@pytest.mark.parametrize("bad_mode", ["yes", 1, None, {}, []])
def test_shadow_mode_must_be_explicit_boolean(monkeypatch, bad_mode):
    img, _ = _source_rectangle(monkeypatch, painted_columns=17)
    with pytest.raises(ValueError, match="mode must be bool"):
        capture.detect_unchanged_terminal_band_segments(
            _png(img), _png(img), dpi=300,
            shadow_inclusive_source_cells=bad_mode,
        )
