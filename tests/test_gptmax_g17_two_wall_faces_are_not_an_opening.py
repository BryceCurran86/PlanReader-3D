"""Real cross-gap wall faces prevent false G17 swing/framed openings.

All assertions are source-neutral original-pixel synthesis. A reported wall
face is opposing evidence only; no opening count, host or FIRM area is granted.
"""
from __future__ import annotations

import cv2
import numpy as np
import pytest

from pb_physical_opening_authority import (
    _RasterBandPair,
    _raster_double_continuous_face_gap,
)
from test_raster_door_swing_g17_contract import _records, _results, _sheet, SWING_PATTERN


def _source_sheet_with_painted_faces(rows: tuple[int, ...]) -> np.ndarray:
    image = _sheet(leaf=True, arc=True)
    for row in rows:
        cv2.line(image, (242, row), (399, row), 0, 1)
    return image


def test_independently_valid_door_still_proves_exactly_one_swing():
    openings = _records(_results(_source_sheet_with_painted_faces(())))
    assert len(openings) == 1
    assert openings[0].structural_pattern == SWING_PATTERN


@pytest.mark.parametrize("face_rows", [(150, 164), (151, 163), (152, 162)])
def test_two_spanning_wall_faces_cannot_mint_a_swing_or_framed_opening(face_rows):
    assert _records(_results(_source_sheet_with_painted_faces(face_rows),
                            raster_double_face_negative_shadow=True)) == ()


def _pair() -> _RasterBandPair:
    return _RasterBandPair(
        a=(10, 150, 240, 164), b=(400, 150, 600, 164),
        gap_x0=241, gap_x1=399, row0=150, row1=164,
        thickness_a=15, thickness_b=15, reasons=(),
    )


def test_one_face_line_is_insufficient_but_two_full_source_rows_are_opposition():
    pair = _pair()
    image = np.zeros((360, 640), dtype=np.uint8)
    image[151, 241:400] = 1
    assert not _raster_double_continuous_face_gap(image, pair)
    image[163, 241:400] = 1
    assert _raster_double_continuous_face_gap(image, pair)
    image[163, 300] = 0
    assert _raster_double_continuous_face_gap(image, pair)
    image[163, 241:350] = 0
    assert not _raster_double_continuous_face_gap(image, pair)


def test_partial_wall_face_and_tiny_band_do_not_create_false_opposition():
    pair = _pair()
    image = np.zeros((360, 640), dtype=np.uint8)
    image[151, 241:300] = 1
    image[163, 241:400] = 1
    assert not _raster_double_continuous_face_gap(image, pair)
    too_short = _RasterBandPair(
        a=pair.a, b=pair.b,
        gap_x0=pair.gap_x0, gap_x1=pair.gap_x1,
        row0=150, row1=153, thickness_a=15, thickness_b=15, reasons=(),
    )
    assert not _raster_double_continuous_face_gap(image, too_short)


def test_out_of_page_gap_cannot_supply_fake_wall_face_evidence():
    pair = _pair()
    image = np.zeros((360, 640), dtype=np.uint8)
    out_of_page = _RasterBandPair(
        a=pair.a, b=pair.b,
        gap_x0=pair.gap_x0, gap_x1=1000,
        row0=150, row1=164, thickness_a=15, thickness_b=15, reasons=(),
    )
    assert not _raster_double_continuous_face_gap(image, out_of_page)
