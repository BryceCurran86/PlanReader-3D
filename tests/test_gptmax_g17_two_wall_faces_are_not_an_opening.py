"""Cross-gap raster ink is negative for unsupported swing, not positive solid wall.

Source-neutral pixel synthesis. Inset paired ink may be a real framed window
or wall/lintel ABOVE an opening; do not delete its positive G17 frame evidence.
Neither existence case grants kind, a complete host, a count or FIRM area.
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


def test_proven_outer_wall_face_continuity_blocks_framed_and_swing_fallback():
    # These lines sit on the exact original outer face/endpoint rows.
    assert _records(_results(_source_sheet_with_painted_faces((150, 164)))) == ()


@pytest.mark.parametrize("frame_rows", [(151, 163), (152, 162)])
def test_inset_paired_frame_ink_must_not_be_mistaken_for_solid_wall(frame_rows):
    # Distinct internal ink rows have the same 2D geometry as a real window
    # frame; a two-row continuity check alone cannot prove solid wall.
    records = _records(_results(_source_sheet_with_painted_faces(frame_rows)))
    assert len(records) == 1
    assert records[0].structural_pattern == "raster_framed_wall_band_interruption"
    assert records[0].aperture_bbox_pt is not None


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
