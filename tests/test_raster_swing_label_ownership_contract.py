from __future__ import annotations

from types import SimpleNamespace

import pytest

from pb_opening_label_dimension_authority import _gap_span_for_opening


SWING_PATTERN = "raster_door_swing_wall_band_interruption"


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


SOURCE = SimpleNamespace(
    authority=lambda: SimpleNamespace(
        resolve_visible=lambda selector: SimpleNamespace(
            status="abstained",
            observation=None,
        )
    )
)


def test_swing_raster_opening_uses_g17_bbox_for_spatial_label_ownership() -> None:
    """EXPECTED RED until swing apertures share the reviewed raster ownership bridge."""

    gap = _gap_span_for_opening(
        SOURCE,
        _opening(SWING_PATTERN, (100.0, 50.0, 140.0, 60.0)),
    )
    assert gap is not None
    assert gap.axis == pytest.approx((1.0, 0.0))
    assert gap.normal == pytest.approx((0.0, 1.0))
    assert gap.along_min == pytest.approx(100.0)
    assert gap.along_max == pytest.approx(140.0)
    assert gap.cross_center == pytest.approx(55.0)
    assert gap.cross_spread == pytest.approx(10.0)


def test_swing_raster_label_ownership_is_quarter_turn_invariant() -> None:
    """EXPECTED RED until vertical swing apertures use the same spatial proof."""

    gap = _gap_span_for_opening(
        SOURCE,
        _opening(SWING_PATTERN, (50.0, 100.0, 60.0, 140.0)),
    )
    assert gap is not None
    assert gap.axis == pytest.approx((0.0, 1.0))
    assert gap.normal == pytest.approx((-1.0, 0.0))
    assert gap.along_min == pytest.approx(100.0)
    assert gap.along_max == pytest.approx(140.0)
    assert gap.cross_center == pytest.approx(-55.0)
    assert gap.cross_spread == pytest.approx(10.0)


@pytest.mark.parametrize(
    "bbox",
    (
        None,
        (0.0, 0.0, 20.0, 20.0),
        (10.0, 10.0, 10.0, 40.0),
        (10.0, 10.0, 40.0, 10.0),
        (0.0, 0.0, float("nan"), 10.0),
    ),
)
def test_invalid_swing_aperture_cannot_own_source_labels(bbox) -> None:
    assert _gap_span_for_opening(
        SOURCE,
        _opening(SWING_PATTERN, bbox),
    ) is None
