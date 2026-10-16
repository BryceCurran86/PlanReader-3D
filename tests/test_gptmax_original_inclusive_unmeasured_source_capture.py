"""Source-positive inclusive-cell capture remains opt-in and never lowers 4pt."""
from __future__ import annotations

import numpy as np
import cv2
import pytest

from pb_raster_unchanged_band_segments import (
    detect_unchanged_terminal_band_segments,
)
from pb_raster_visible_segment_detector import _MIN_LINE_LENGTH_PT


def render_source(cells: int, *, changed=False) -> tuple[bytes, bytes]:
    # Two rows of original dark painted cells with an end cap. The original
    # unchanged-terminal detector reauthenticates end closure from the bitmap.
    src = np.full((64, 90, 3), 255, dtype=np.uint8)
    src[28:37, 24:24+cells] = 0
    full = src.copy()
    if changed:
        full[31, 24+cells//2] = 255
    ok, png_src = cv2.imencode(".png", src)
    assert ok
    ok, png_full = cv2.imencode(".png", full)
    assert ok
    return png_src.tobytes(), png_full.tobytes()


@pytest.mark.parametrize("cells", [16, 17, 18, 19, 30])
def test_inclusive_cell_support_never_changes_source_minimum(cells):
    a,b=render_source(cells)
    normal=detect_unchanged_terminal_band_segments(a,b,dpi=300)
    opt=detect_unchanged_terminal_band_segments(
        a,b,dpi=300,shadow_inclusive_source_cells=True)
    assert _MIN_LINE_LENGTH_PT==4.0
    assert set(normal).issubset(set(opt))
    assert not any(s.orientation!="horizontal" for s in opt)
    if cells < 17:
        assert not opt
    elif cells == 17:
        assert not normal
        assert opt
    else:
        assert normal == opt


def test_changed_full_render_can_never_become_eligible():
    a,b=render_source(17,changed=True)
    opt=detect_unchanged_terminal_band_segments(
        a,b,dpi=300,shadow_inclusive_source_cells=True)
    assert not opt


def test_boolean_only_source_mode():
    a,b=render_source(17)
    for bad in ("true",1,None,{},[]):
        with pytest.raises(ValueError):
            detect_unchanged_terminal_band_segments(
                a,b,dpi=300,shadow_inclusive_source_cells=bad)
