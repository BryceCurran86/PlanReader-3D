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


def test_viewport_scoped_exterior_closure_isolates_outlying_wall():
    # Outlying wall at x=420..470 causes un-scoped preflight to fail closed.
    drawings = _ring() + [_wall((420, 100, 470, 110))]
    unscoped = attempt_source_native_outer_wall_first(
        drawings, source_ink_already_scoped=True,
    )
    assert unscoped.status == "ABSTAINED"
    assert unscoped.reason == "source_exterior_other_wall_ink_outside_candidate"
    assert unscoped.diagnostic_wall_bands_outside_loop >= 1

    # When scoped to the primary drawing viewport, the outlying wall is excluded
    # and the primary ring closes authentically.
    scoped = attempt_source_native_outer_wall_first(
        drawings,
        source_ink_already_scoped=True,
        viewport_pdf_pts=(50.0, 50.0, 350.0, 350.0),
    )
    assert scoped.status == "CANDIDATE"
    assert scoped.diagnostic_closed_wall_loop_count == 1
    assert scoped.diagnostic_wall_bands_outside_loop == 0
    assert len(scoped.polygon_pdf_pts) >= 4
    assert scoped.viewport_pdf_pts == ((50.0, 50.0, 350.0, 350.0),)


def test_viewport_scoped_exterior_closure_multi_scheme_rings():
    # Two distinct building schemes on the same sheet.
    ring1 = _ring()
    ring2 = [
        _wall((500, 100, 700, 110)),
        _wall((500, 290, 700, 300)),
        _wall((500, 100, 510, 300)),
        _wall((690, 100, 700, 300)),
    ]
    drawings = ring1 + ring2

    # Whole-sheet un-scoped attempt fails closed due to multiple rival loops.
    unscoped = attempt_source_native_outer_wall_first(
        drawings, source_ink_already_scoped=True,
    )
    assert unscoped.status == "ABSTAINED"
    assert unscoped.diagnostic_closed_wall_loop_count == 2
    assert unscoped.reason == "source_exterior_perimeter_not_unique_and_closed"

    # Scoping to Scheme 1 viewport closes Ring 1 uniquely.
    scoped1 = attempt_source_native_outer_wall_first(
        drawings,
        source_ink_already_scoped=True,
        viewport_pdf_pts=(50.0, 50.0, 350.0, 350.0),
    )
    assert scoped1.status == "CANDIDATE"
    assert scoped1.diagnostic_closed_wall_loop_count == 1
    assert scoped1.diagnostic_wall_bands_outside_loop == 0

    # Scoping to Scheme 2 viewport closes Ring 2 uniquely.
    scoped2 = attempt_source_native_outer_wall_first(
        drawings,
        source_ink_already_scoped=True,
        viewport_pdf_pts=(450.0, 50.0, 750.0, 350.0),
    )
    assert scoped2.status == "CANDIDATE"
    assert scoped2.diagnostic_closed_wall_loop_count == 1
    assert scoped2.diagnostic_wall_bands_outside_loop == 0


def test_internal_partition_wall_inside_envelope_does_not_fail_closure():
    # A central internal partition wall inside the building envelope.
    drawings = _ring() + [_wall((195, 110, 205, 290))]
    result = attempt_source_native_outer_wall_first(
        drawings, source_ink_already_scoped=True,
    )
    assert result.status == "CANDIDATE"
    assert result.diagnostic_closed_wall_loop_count == 1
    assert result.diagnostic_wall_bands_outside_loop == 0


def test_exterior_wall_unifies_across_internal_t_junction_gap():
    # An exterior wall with a continuous outer stroke (x=300, y=100..300)
    # opposed by inner face strokes (x=290) interrupted by a 10pt internal
    # partition T-junction gap at y=195..205.
    def stroke(p0, p1, layer="Enclosure_WallExternal", width=0.8):
        return {
            "rect": fitz.Rect(
                min(p0[0], p1[0]),
                min(p0[1], p1[1]),
                max(p0[0], p1[0]),
                max(p0[1], p1[1]),
            ),
            "layer": layer,
            "fill": None,
            "color": (0.0, 0.0, 0.0),
            "width": width,
            "items": (("l", fitz.Point(*p0), fitz.Point(*p1)),),
        }

    drawings = [
        _wall((100, 100, 300, 110)),
        _wall((100, 290, 300, 300)),
        _wall((100, 100, 110, 300)),
        # Continuous exterior face stroke
        stroke((300, 100), (300, 300)),
        # Inner face strokes interrupted by T-junction gap
        stroke((290, 100), (290, 195)),
        stroke((290, 205), (290, 300)),
        # Internal partition wall meeting the inner face
        _wall((195, 195, 290, 205)),
    ]
    result = attempt_source_native_outer_wall_first(
        drawings, source_ink_already_scoped=True,
    )
    assert result.status == "CANDIDATE"
    assert result.diagnostic_closed_wall_loop_count == 1
    assert result.diagnostic_wall_bands_outside_loop == 0


def test_banksia_brisbane_east_wall_unification_across_t_junction():
    import os
    pdf_path = r"C:\Users\bryce\OneDrive\Desktop\documents\sources\other plans\05_banksia_brisbane.pdf"
    if not os.path.exists(pdf_path):
        return
    from pb_new_exterior_wall_preflight import (
        _source_wall_ink_candidate_drawings,
        _collect_source_wide_face_pairs,
    )
    doc = fitz.open(pdf_path)
    page = doc[1]
    drawings = page.get_drawings()
    wall_ink = _source_wall_ink_candidate_drawings(drawings)[0]
    strips = _collect_source_wide_face_pairs(wall_ink)
    east_strips = [
        s for s in strips
        if abs(s.polygon.bounds[0] - 941.458) < 0.2
        and abs(s.polygon.bounds[2] - 949.783) < 0.2
        and 280.0 <= s.polygon.bounds[1] <= 300.0
    ]
    assert len(east_strips) == 1
    east = east_strips[0]
    assert abs(east.polygon.bounds[1] - 291.414) < 0.2
    assert abs(east.polygon.bounds[3] - 387.147) < 0.2
    assert 8730 in east.path_indices
    assert 8702 in east.path_indices
    assert 8729 in east.path_indices


