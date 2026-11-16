"""Unsealed exterior source review overlay is never a billable footprint."""
from dataclasses import replace

import pytest

from pb_new_source_trace_preview import _draw_unsealed_source_ring_preview
from pb_source_unbounded_building_face_walk_shadow import OutsideFacingBuildingWalk


class SpyCanvas:
    def __init__(self):
        self.calls = []

    def draw_polyline(self, points, **kwargs):
        self.calls.append((points, kwargs))


RING = ((0.0, 0.0), (20.0, 0.0), (20.0, 15.0), (0.0, 15.0), (0.0, 0.0))


def _unsealed():
    return OutsideFacingBuildingWalk(
        "ABSTAINED", "source_other_structural_walls_outside_candidate",
        enclosed_dwelling_zone_count=2, other_source_wall_band_count=1,
        diagnostic_unsealed_ring_pdf_pts=RING,
    )


def test_unsealed_receipt_draws_only_dashed_review_ring():
    walk = _unsealed()
    canvas = SpyCanvas()
    assert _draw_unsealed_source_ring_preview(canvas, walk) is True
    assert len(canvas.calls) == 1
    pts, style = canvas.calls[0]
    assert len(pts) == len(RING)
    assert style["dashes"] == "[6 4] 0"
    assert style["width"] < 3.0
    assert walk.clockwise_pdf_pts == ()
    assert walk.outer_wall_native_path_ids == ()
    assert walk.building_footprint_authenticated is False
    assert walk.measurement_authorized is False
    assert walk.to_dict()["diagnostic_unsealed_not_measurement"] is True


@pytest.mark.parametrize("bad_walk", [
    replace(_unsealed(), status="CANDIDATE"),
    replace(_unsealed(), reason="source_dwelling_region_still_open_to_outside"),
    replace(_unsealed(), measurement_authorized=True),
    replace(_unsealed(), building_footprint_authenticated=True),
    replace(_unsealed(), diagnostic_unsealed_ring_pdf_pts=RING[:-1]),
    replace(_unsealed(), diagnostic_unsealed_ring_pdf_pts=()),
    replace(_unsealed(), diagnostic_unsealed_ring_pdf_pts=(
        (0.0, 0.0), (20.0, 0.0), (float("inf"), 15.0),
        (0.0, 15.0), (0.0, 0.0),
    )),
])
def test_unsealed_renderer_never_draws_unapproved_or_invalid_ring(bad_walk):
    canvas = SpyCanvas()
    assert _draw_unsealed_source_ring_preview(canvas, bad_walk) is False
    assert canvas.calls == []


def test_nonpreview_receipts_keep_original_json_contract():
    walk = OutsideFacingBuildingWalk("ABSTAINED", "source_unbounded_face_not_closed")
    assert "diagnostic_unsealed_ring_pdf_pts" not in walk.to_dict()
    assert "diagnostic_unsealed_not_measurement" not in walk.to_dict()
