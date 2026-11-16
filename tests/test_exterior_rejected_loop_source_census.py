"""Rejected native enclosure diagnostics cannot authorize a building footprint."""
from __future__ import annotations

import fitz

from pb_new_exterior_wall_preflight import attempt_source_native_outer_wall_first


def _wall(bounds):
    return {
        "rect": fitz.Rect(*bounds),
        "layer": "Enclosure_WallExternal",
        "fill": (0.0, 0.0, 0.0),
        "items": (("re", fitz.Rect(*bounds), 1),),
    }


def _ring():
    return [
        _wall((100, 100, 300, 110)),
        _wall((100, 290, 300, 300)),
        _wall((100, 100, 110, 300)),
        _wall((290, 100, 300, 300)),
    ]


def test_closed_ring_plus_genuine_outlying_wall_is_still_abstained():
    drawings = _ring() + [_wall((420, 100, 470, 110))]
    result = attempt_source_native_outer_wall_first(
        drawings, source_ink_already_scoped=True,
    )
    assert result.status == "ABSTAINED"
    assert result.reason == "source_exterior_other_wall_ink_outside_candidate"
    assert result.diagnostic_closed_wall_loop_count == 1
    assert result.diagnostic_rejected_loop_bbox_pdf_pts == (
        100.0, 100.0, 300.0, 300.0
    )
    assert result.diagnostic_wall_bands_outside_loop >= 1
    assert 4 in result.diagnostic_outside_source_path_sample
    assert result.polygon_pdf_pts == ()
    assert result.physical_wall_authenticated is False
    assert result.measurement_authorized is False


def test_unblocked_ring_is_still_a_candidate_not_commercial_authority():
    result = attempt_source_native_outer_wall_first(
        _ring(), source_ink_already_scoped=True,
    )
    assert result.status == "CANDIDATE"
    assert result.diagnostic_closed_wall_loop_count == 1
    assert result.diagnostic_wall_bands_outside_loop == 0
    assert result.measurement_authorized is False
    assert result.physical_wall_authenticated is False


def test_three_sides_never_use_a_guessed_outer_loop():
    result = attempt_source_native_outer_wall_first(
        _ring()[:3], source_ink_already_scoped=True,
    )
    assert result.status == "ABSTAINED"
    assert result.diagnostic_rejected_loop_bbox_pdf_pts is None
    assert result.diagnostic_wall_bands_outside_loop == 0
    assert result.polygon_pdf_pts == ()
