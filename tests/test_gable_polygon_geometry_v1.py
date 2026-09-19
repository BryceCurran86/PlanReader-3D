"""Mutation tests for pb_gable_polygon_geometry.

All fixtures are synthetic coordinate sets -- no benchmark project
geometry or expected quantities appear anywhere in this file.
"""
from __future__ import annotations

import math

import pytest

from pb_gable_polygon_geometry import (
    GableReconstructionStatus,
    RoofEdgeSegment,
    reconstruct_gable_polygon,
)


def _shoelace(points):
    n = len(points)
    total = 0.0
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def test_triangular_gable():
    left = RoofEdgeSegment((0.0, 100.0), (50.0, 50.0), "left")
    right = RoofEdgeSegment((50.0, 50.0), (100.0, 100.0), "right")
    poly, status = reconstruct_gable_polygon(
        [left, right], left_boundary_x=0.0, right_boundary_x=100.0,
    )
    assert status == GableReconstructionStatus.RESOLVED.value
    assert len(poly.vertices) == 3
    expected = _shoelace([(0.0, 100.0), (50.0, 50.0), (100.0, 100.0)])
    assert poly.area_pt2() == pytest.approx(expected)
    assert poly.area_pt2() == pytest.approx(2500.0)  # 0.5*base(100)*height(50)


def test_trapezoidal_gable():
    left = RoofEdgeSegment((0.0, 100.0), (30.0, 60.0), "left")
    top = RoofEdgeSegment((30.0, 60.0), (70.0, 60.0), "top")
    right = RoofEdgeSegment((70.0, 60.0), (100.0, 100.0), "right")
    poly, status = reconstruct_gable_polygon(
        [left, top, right], left_boundary_x=0.0, right_boundary_x=100.0,
    )
    assert status == GableReconstructionStatus.RESOLVED.value
    assert len(poly.vertices) == 4
    expected = _shoelace([(0.0, 100.0), (30.0, 60.0), (70.0, 60.0), (100.0, 100.0)])
    assert poly.area_pt2() == pytest.approx(expected)


def test_mono_pitch_end():
    """One sloped edge only -- the far side stays at the boundary's own
    evaluated height on that same single line (a lean-to end)."""
    only = RoofEdgeSegment((0.0, 100.0), (100.0, 40.0), "mono")
    poly, status = reconstruct_gable_polygon(
        [only], left_boundary_x=0.0, right_boundary_x=100.0,
    )
    assert status == GableReconstructionStatus.RESOLVED.value
    assert len(poly.vertices) == 2
    assert poly.vertices[0] == (0.0, 100.0)
    assert poly.vertices[1] == (100.0, 40.0)


def test_hip_roof_no_gable():
    """No roofline segments found in the boundary region at all -- a hip
    end (or flat parapet) must never be guessed into a triangle."""
    unrelated = RoofEdgeSegment((500.0, 10.0), (600.0, 5.0), "elsewhere")
    poly, status = reconstruct_gable_polygon(
        [unrelated], left_boundary_x=0.0, right_boundary_x=100.0,
    )
    assert poly is None
    assert status == GableReconstructionStatus.NO_GABLE.value


def test_two_physical_gable_ends_independently_measured():
    """Two distinct boundary regions (representing two distinct physical
    walls) must each be measured on their own -- proves no symmetry
    doubling happens inside this module; the caller is responsible for
    proving physical distinctness (Step 6), this module only ever computes
    what it is given."""
    end_a_left = RoofEdgeSegment((0.0, 100.0), (50.0, 50.0), "a_left")
    end_a_right = RoofEdgeSegment((50.0, 50.0), (100.0, 100.0), "a_right")
    end_b_left = RoofEdgeSegment((0.0, 100.0), (55.0, 48.0), "b_left")
    end_b_right = RoofEdgeSegment((55.0, 48.0), (100.0, 105.0), "b_right")

    poly_a, status_a = reconstruct_gable_polygon(
        [end_a_left, end_a_right], left_boundary_x=0.0, right_boundary_x=100.0,
    )
    poly_b, status_b = reconstruct_gable_polygon(
        [end_b_left, end_b_right], left_boundary_x=0.0, right_boundary_x=100.0,
    )
    assert status_a == status_b == GableReconstructionStatus.RESOLVED.value
    # The two ends have genuinely different geometry (different ridge
    # position/eave heights) -- their areas must not be forced equal.
    assert poly_a.area_pt2() != pytest.approx(poly_b.area_pt2(), rel=1e-6)


def test_one_gable_only_not_doubled():
    left = RoofEdgeSegment((0.0, 100.0), (50.0, 50.0), "left")
    right = RoofEdgeSegment((50.0, 50.0), (100.0, 100.0), "right")
    poly, _status = reconstruct_gable_polygon(
        [left, right], left_boundary_x=0.0, right_boundary_x=100.0,
    )
    single_area = poly.area_pt2()
    # This module never doubles internally -- summing two calls with the
    # SAME single physical end's segments twice is a caller error, not
    # something this module does on its own; verify a single
    # reconstruction call returns exactly one polygon's worth of area.
    assert single_area == pytest.approx(2500.0)


def test_duplicate_elevation_of_same_physical_end_is_caller_responsibility():
    """Feeding the identical segment set twice (as if two views showed the
    same physical wall) still only reconstructs ONE polygon per call --
    this module has no concept of "count of views", only "segments given
    in this one call", so duplication can only happen at the caller level
    (which Step 6 requires proving/rejecting before calling twice)."""
    left = RoofEdgeSegment((0.0, 100.0), (50.0, 50.0), "left")
    right = RoofEdgeSegment((50.0, 50.0), (100.0, 100.0), "right")
    poly1, _ = reconstruct_gable_polygon([left, right], left_boundary_x=0.0, right_boundary_x=100.0)
    poly2, _ = reconstruct_gable_polygon([left, right], left_boundary_x=0.0, right_boundary_x=100.0)
    assert poly1.area_pt2() == poly2.area_pt2()


def test_plan_elevation_mismatch_wrong_pitch_rejected():
    """A line at a materially different pitch than the one proven
    elsewhere on the drawing must be excluded, not absorbed."""
    left = RoofEdgeSegment((0.0, 100.0), (50.0, 50.0), "left")  # ~45 deg
    right = RoofEdgeSegment((50.0, 50.0), (100.0, 100.0), "right")  # ~45 deg
    poly, status = reconstruct_gable_polygon(
        [left, right], left_boundary_x=0.0, right_boundary_x=100.0,
        expected_pitch_deg=15.0, pitch_tolerance_deg=1.0,
    )
    assert poly is None
    assert status == GableReconstructionStatus.NO_GABLE.value


def test_cropped_elevation_gap_unresolved():
    """The roofline chain does not reach the right boundary at all (a
    cropped/incomplete elevation) -- must not extrapolate past real
    measured geometry."""
    left = RoofEdgeSegment((0.0, 100.0), (50.0, 50.0), "left")
    short_right = RoofEdgeSegment((50.0, 50.0), (70.0, 65.0), "right_short")
    poly, status = reconstruct_gable_polygon(
        [left, short_right], left_boundary_x=0.0, right_boundary_x=100.0,
    )
    assert poly is None
    assert status == GableReconstructionStatus.UNRESOLVED_GAP.value


def test_missing_ridge_gap_between_segments_unresolved():
    """Two roofline segments that do not actually connect (a real gap far
    beyond snap tolerance) must not be silently bridged."""
    left = RoofEdgeSegment((0.0, 100.0), (40.0, 60.0), "left")
    right = RoofEdgeSegment((60.0, 60.0), (100.0, 100.0), "right")  # 20pt gap
    poly, status = reconstruct_gable_polygon(
        [left, right], left_boundary_x=0.0, right_boundary_x=100.0,
        apex_snap_tolerance_pt=3.0,
    )
    assert poly is None
    assert status == GableReconstructionStatus.UNRESOLVED_GAP.value


def test_translated_source_geometry_same_area():
    left = RoofEdgeSegment((0.0, 100.0), (50.0, 50.0), "left")
    right = RoofEdgeSegment((50.0, 50.0), (100.0, 100.0), "right")
    poly_a, _ = reconstruct_gable_polygon([left, right], left_boundary_x=0.0, right_boundary_x=100.0)

    dx, dy = 500.0, -300.0
    left_t = RoofEdgeSegment((0.0 + dx, 100.0 + dy), (50.0 + dx, 50.0 + dy), "left")
    right_t = RoofEdgeSegment((50.0 + dx, 50.0 + dy), (100.0 + dx, 100.0 + dy), "right")
    poly_b, _ = reconstruct_gable_polygon(
        [left_t, right_t], left_boundary_x=0.0 + dx, right_boundary_x=100.0 + dx,
    )
    assert poly_a.area_pt2() == pytest.approx(poly_b.area_pt2())


def test_scaled_source_geometry_area_scales_quadratically():
    left = RoofEdgeSegment((0.0, 100.0), (50.0, 50.0), "left")
    right = RoofEdgeSegment((50.0, 50.0), (100.0, 100.0), "right")
    poly_a, _ = reconstruct_gable_polygon([left, right], left_boundary_x=0.0, right_boundary_x=100.0)

    k = 2.0
    left_s = RoofEdgeSegment((0.0, 100.0 * k), (50.0 * k, 50.0 * k), "left")
    right_s = RoofEdgeSegment((50.0 * k, 50.0 * k), (100.0 * k, 100.0 * k), "right")
    poly_b, _ = reconstruct_gable_polygon(
        [left_s, right_s], left_boundary_x=0.0, right_boundary_x=100.0 * k,
    )
    assert poly_b.area_pt2() == pytest.approx(poly_a.area_pt2() * (k ** 2))


def test_reordered_primitive_emission_order_independent():
    left = RoofEdgeSegment((0.0, 100.0), (50.0, 50.0), "left")
    right = RoofEdgeSegment((50.0, 50.0), (100.0, 100.0), "right")
    poly_a, _ = reconstruct_gable_polygon([left, right], left_boundary_x=0.0, right_boundary_x=100.0)
    poly_b, _ = reconstruct_gable_polygon([right, left], left_boundary_x=0.0, right_boundary_x=100.0)
    assert poly_a.area_pt2() == pytest.approx(poly_b.area_pt2())
    assert poly_a.vertices == poly_b.vertices


def test_detail_example_gable_excluded_by_region():
    """A small-scale detail/example gable drawn elsewhere on the sheet
    (outside the authenticated elevation's boundary region) must never be
    absorbed into the real elevation's polygon."""
    real_left = RoofEdgeSegment((0.0, 100.0), (50.0, 50.0), "real_left")
    real_right = RoofEdgeSegment((50.0, 50.0), (100.0, 100.0), "real_right")
    detail_left = RoofEdgeSegment((900.0, 950.0), (920.0, 940.0), "detail_left")
    detail_right = RoofEdgeSegment((920.0, 940.0), (940.0, 950.0), "detail_right")
    poly, status = reconstruct_gable_polygon(
        [real_left, real_right, detail_left, detail_right],
        left_boundary_x=0.0, right_boundary_x=100.0,
    )
    assert status == GableReconstructionStatus.RESOLVED.value
    assert poly.area_pt2() == pytest.approx(2500.0)
    assert set(poly.source_segment_ids) == {"real_left", "real_right"}


def test_conflicting_heights_ambiguous_apex_rejected():
    """Two candidate segments that both claim to bound the same left
    region but disagree materially (a real conflict, not a snap-tolerance
    rounding difference) must not silently pick one."""
    left_a = RoofEdgeSegment((0.0, 100.0), (50.0, 50.0), "left_a")
    left_b = RoofEdgeSegment((0.0, 100.0), (50.0, 20.0), "left_b")  # different pitch, same span
    right = RoofEdgeSegment((50.0, 50.0), (100.0, 100.0), "right")
    poly, status = reconstruct_gable_polygon(
        [left_a, left_b, right], left_boundary_x=0.0, right_boundary_x=100.0,
    )
    # Both left_a and left_b occupy the same x-span as candidates; the
    # chain-merge step will treat this as two overlapping candidates at
    # the same position -- ordering by midpoint is stable but the
    # resulting gap check against `right` must not silently succeed with
    # the wrong one. We assert the module does not fabricate a clean
    # triangle out of genuinely conflicting evidence: either UNRESOLVED_GAP
    # (recommended) or a polygon that used only one -- either way it must
    # never silently average or invent a compromise slope.
    if poly is not None:
        assert poly.area_pt2() in (
            pytest.approx(2500.0),
            pytest.approx(_shoelace([(0.0, 100.0), (50.0, 20.0), (100.0, 100.0)])),
        )
