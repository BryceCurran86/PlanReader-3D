"""#4443: unsupported exterior rectangular boxes collapse; genuine alcoves stay."""
from __future__ import annotations

from pb_source_unsupported_rectangular_detour_shadow import (
    collapse_unsupported_rectangular_detours,
)


def test_two_fabricated_boxes_on_straight_wall_collapse_to_one_face():
    # Straight top wall at y=100 with two unsupported outbound boxes.
    poly = [
        (0.0, 100.0),
        (40.0, 100.0),
        (40.0, 40.0),   # box 1 out
        (70.0, 40.0),
        (70.0, 100.0),
        (120.0, 100.0),
        (120.0, 40.0),  # box 2 out
        (150.0, 40.0),
        (150.0, 100.0),
        (200.0, 100.0),
        (200.0, 300.0),
        (0.0, 300.0),
    ]
    # Continuous source wall along the true face y=100 only.
    walls = ((0.0, 100.0, 200.0, 100.0), (200.0, 100.0, 200.0, 300.0),
             (200.0, 300.0, 0.0, 300.0), (0.0, 300.0, 0.0, 100.0))
    receipt = collapse_unsupported_rectangular_detours(poly, walls)
    assert receipt.collapsed_detour_count == 2
    assert receipt.commercial_publishable is False
    ys_at_top = [p for p in receipt.polygon_pdf_pts if abs(p[1] - 100.0) <= 2.5]
    assert all(abs(p[1] - 100.0) <= 2.5 for p in ys_at_top)
    assert not any(abs(p[1] - 40.0) <= 1.0 for p in receipt.polygon_pdf_pts)


def test_genuine_alcove_with_paired_wall_faces_is_retained():
    poly = [
        (0.0, 100.0),
        (40.0, 100.0),
        (40.0, 40.0),
        (70.0, 40.0),
        (70.0, 100.0),
        (200.0, 100.0),
        (200.0, 300.0),
        (0.0, 300.0),
    ]
    walls = (
        (0.0, 100.0, 40.0, 100.0),
        (40.0, 100.0, 40.0, 40.0),   # left return painted
        (40.0, 40.0, 70.0, 40.0),    # far face painted
        (70.0, 40.0, 70.0, 100.0),   # right return painted
        (70.0, 100.0, 200.0, 100.0),
        (200.0, 100.0, 200.0, 300.0),
        (200.0, 300.0, 0.0, 300.0),
        (0.0, 300.0, 0.0, 100.0),
    )
    receipt = collapse_unsupported_rectangular_detours(poly, walls)
    assert receipt.collapsed_detour_count == 0
    assert any(abs(p[1] - 40.0) <= 1.0 for p in receipt.polygon_pdf_pts)


def test_thin_antenna_boxes_collapse_without_requiring_wall_proof():
    # Matches the 3Laurel morphological spike pattern: out and nearly back.
    poly = [
        (142.0, 190.0),
        (370.56, 189.44),
        (358.33, 132.78),
        (369.44, 189.44),
        (219.44, 189.44),
        (218.89, 132.78),
        (218.33, 189.44),
        (142.22, 190.0),
        (148.89, 467.22),
        (756.0, 466.0),
        (756.0, 190.0),
    ]
    receipt = collapse_unsupported_rectangular_detours(poly, ())
    assert receipt.collapsed_detour_count >= 2
    assert not any(abs(p[1] - 132.78) <= 1.0 for p in receipt.polygon_pdf_pts)


def test_ambiguous_wide_box_without_ink_collapses_as_candidate_only():
    poly = [
        (0.0, 0.0),
        (100.0, 0.0),
        (100.0, -40.0),
        (160.0, -40.0),
        (160.0, 0.0),
        (300.0, 0.0),
        (300.0, 200.0),
        (0.0, 200.0),
    ]
    receipt = collapse_unsupported_rectangular_detours(poly, ())
    assert receipt.collapsed_detour_count == 1
    assert receipt.measurement_authorized is False
    assert "collapsed_unsupported_rectangular_detour" in receipt.reason_codes
