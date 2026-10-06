from __future__ import annotations

from types import SimpleNamespace

import pytest

import pb_opening_host_binding_authority as host
from pb_physical_opening_authority import (
    JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
    RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION,
)


def _opening(pattern: str, bbox):
    return SimpleNamespace(
        structural_pattern=pattern,
        aperture_bbox_pt=bbox,
        source_observation_ids=(),
        document_id="doc",
        revision_id="rev",
        source_sha256="a" * 64,
        snapshot_id="snap",
        page_id="1",
    )


AUTHORITY = SimpleNamespace(source_visibility_authority=lambda: None)


def test_swing_raster_opening_consumes_g17_sealed_horizontal_aperture() -> None:
    """EXPECTED RED until host geometry accepts G17 swing apertures."""

    geometry = host._opening_geometry(
        AUTHORITY,
        _opening(
            RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION,
            (100.0, 50.0, 140.0, 60.0),
        ),
    )
    assert geometry is not None
    assert geometry.origin == pytest.approx((100.0, 55.0))
    assert geometry.axis == pytest.approx((1.0, 0.0))
    assert geometry.normal == pytest.approx((0.0, 1.0))
    assert geometry.length == pytest.approx(40.0)
    assert geometry.thickness == pytest.approx(10.0)


def test_swing_raster_opening_consumes_g17_sealed_vertical_aperture() -> None:
    """EXPECTED RED until the swing host bridge is quarter-turn invariant."""

    geometry = host._opening_geometry(
        AUTHORITY,
        _opening(
            RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION,
            (50.0, 100.0, 60.0, 140.0),
        ),
    )
    assert geometry is not None
    assert geometry.origin == pytest.approx((55.0, 100.0))
    assert geometry.axis == pytest.approx((0.0, 1.0))
    assert geometry.normal == pytest.approx((-1.0, 0.0))
    assert geometry.length == pytest.approx(40.0)
    assert geometry.thickness == pytest.approx(10.0)


@pytest.mark.parametrize(
    "bbox",
    (
        None,
        (100.0, 50.0, 100.0, 60.0),
        (100.0, 50.0, 110.0, 50.0),
        (100.0, 50.0, 110.0, 60.0),
        (100.0, 50.0, 115.0, 60.0),
        (100.0, 50.0, float("nan"), 60.0),
    ),
)
def test_invalid_or_non_opening_swing_bbox_stays_unavailable(bbox) -> None:
    assert host._opening_geometry(
        AUTHORITY,
        _opening(RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION, bbox),
    ) is None


def test_non_raster_pattern_cannot_borrow_sealed_bbox_shortcut() -> None:
    assert host._opening_geometry(
        AUTHORITY,
        _opening(
            JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
            (100.0, 50.0, 140.0, 60.0),
        ),
    ) is None
