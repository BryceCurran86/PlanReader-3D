"""Raster spatial snap acceleration must exactly preserve original source order."""
from __future__ import annotations

from random import Random

import pytest

from pb_raster_visible_segment_detector import _dedupe, _snap_intersections


def _reference(horizontal, vertical, tolerance):
    """Original three-pass full scan; retained only as a regression oracle."""
    snapped_h = []
    for x0, y0, x1, _ in horizontal:
        left, right = x0, x1
        for vx, vy0, _, vy1 in vertical:
            if vy0 - tolerance <= y0 <= vy1 + tolerance:
                if abs(left - vx) <= tolerance:
                    left = vx
                if abs(right - vx) <= tolerance:
                    right = vx
        if right - left > 0:
            snapped_h.append((left, y0, right, y0))
    snapped_v = []
    for x0, y0, _, y1 in vertical:
        top, bottom = y0, y1
        for hx0, hy0, hx1, _ in snapped_h:
            if hx0 - tolerance <= x0 <= hx1 + tolerance:
                if abs(top - hy0) <= tolerance:
                    top = hy0
                if abs(bottom - hy0) <= tolerance:
                    bottom = hy0
        if bottom - top > 0:
            snapped_v.append((x0, top, x0, bottom))
    final_h = []
    for x0, y0, x1, _ in snapped_h:
        left, right = x0, x1
        for vx, vy0, _, vy1 in snapped_v:
            if vy0 - tolerance <= y0 <= vy1 + tolerance:
                if abs(left - vx) <= tolerance:
                    left = vx
                if abs(right - vx) <= tolerance:
                    right = vx
        final_h.append((left, y0, right, y0))
    return _dedupe(final_h), _dedupe(snapped_v)


@pytest.mark.parametrize("seed", range(40))
def test_source_order_snap_spatial_buckets_match_baseline(seed):
    rnd = Random(seed)
    horizontal, vertical = [], []
    for _ in range(120):
        x = float(rnd.randrange(-100, 200))
        y = float(rnd.randrange(-100, 200))
        horizontal.append((x, y, x + float(rnd.randrange(1, 300)), y))
        vertical.append((x, y, x, y + float(rnd.randrange(1, 300))))
    tolerance = [1.0, 2.0, 4.5, 16.0][seed % 4]
    assert _snap_intersections(horizontal, vertical, tolerance_px=tolerance) == (
        _reference(horizontal, vertical, tolerance)
    )


def test_source_order_chain_snaps_across_multiple_candidates():
    horizontal = [(1.0, 10.0, 81.0, 10.0), (5.0, 38.0, 75.0, 38.0)]
    vertical = [
        (2.0, 9.0, 2.0, 41.0),
        (3.0, 8.0, 3.0, 42.0),
        (80.0, 9.0, 80.0, 39.0),
        (79.0, 8.0, 79.0, 40.0),
    ]
    assert _snap_intersections(horizontal, vertical, tolerance_px=2) == (
        _reference(horizontal, vertical, 2)
    )


def test_source_order_many_distant_segments_do_not_change_geometry():
    # Source locality is only a performance index, never an evidence filter.
    horizontal = [
        (float(x * 12), float(y * 12), float(x * 12 + 7), float(y * 12))
        for y in range(24) for x in range(32)
    ]
    vertical = [
        (float(x * 12), float(y * 12), float(x * 12), float(y * 12 + 7))
        for y in range(24) for x in range(32)
    ]
    assert _snap_intersections(horizontal, vertical, tolerance_px=2) == (
        _reference(horizontal, vertical, 2)
    )
