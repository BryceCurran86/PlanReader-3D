"""Synthetic proofs for exact geometry identity shadow."""
from __future__ import annotations

from pb_segment_w4_exact_geometry_identity_shadow import (
    assess_segment_w4_exact_geometry_identity_shadow,
    canonicalize_line_endpoints,
    lines_exactly_equal,
)


def test_endpoint_order_invariant():
    a = (0.0, 0.0, 10.0, 0.0)
    b = (10.0, 0.0, 0.0, 0.0)
    assert canonicalize_line_endpoints(a) == canonicalize_line_endpoints(b)
    assert lines_exactly_equal(a, b)


def test_input_order_invariance_of_matches():
    segs = {"s1": (0.0, 0.0, 5.0, 0.0), "s2": (1.0, 1.0, 2.0, 1.0)}
    walls_a = [
        {"wall_candidate_id": "w1", "centerline_pts": [(0.0, 0.0), (5.0, 0.0)],
         "source_primitive_ids": ["raster_segment:x:1"]},
        {"wall_candidate_id": "w2", "centerline_pts": [(9.0, 9.0), (10.0, 9.0)],
         "source_primitive_ids": ["d0i0"]},
    ]
    walls_b = list(reversed(walls_a))
    ra = assess_segment_w4_exact_geometry_identity_shadow(
        physical_opening_id="oid", segment_lines_by_id=segs, w4_wall_records=walls_a,
    )
    rb = assess_segment_w4_exact_geometry_identity_shadow(
        physical_opening_id="oid", segment_lines_by_id=segs, w4_wall_records=walls_b,
    )
    assert ra["first_remaining_gate"] == rb["first_remaining_gate"]
    assert ra["matched_wall_candidate_ids"] == rb["matched_wall_candidate_ids"]
    assert ra["exact_match_count"] == rb["exact_match_count"] == 1
    assert ra["host_granted"] is False
    assert ra["selected_wall_candidate_id"] is None


def test_multi_wall_exact_match_abstains():
    segs = {"s1": (0.0, 0.0, 5.0, 0.0)}
    walls = [
        {"wall_candidate_id": "w1", "centerline_pts": [(0.0, 0.0), (5.0, 0.0)],
         "source_primitive_ids": ["a"]},
        {"wall_candidate_id": "w2", "centerline_pts": [(5.0, 0.0), (0.0, 0.0)],
         "source_primitive_ids": ["b"]},
    ]
    row = assess_segment_w4_exact_geometry_identity_shadow(
        physical_opening_id="oid", segment_lines_by_id=segs, w4_wall_records=walls,
    )
    assert row["first_remaining_gate"] == "exact_geometry_identity_ambiguous_multi_wall"
    assert row["exact_match_count"] == 2
    assert row["host_granted"] is False


def test_no_match_unavailable():
    row = assess_segment_w4_exact_geometry_identity_shadow(
        physical_opening_id="oid",
        segment_lines_by_id={"s1": (0.0, 0.0, 1.0, 0.0)},
        w4_wall_records=[{
            "wall_candidate_id": "w1",
            "centerline_pts": [(2.0, 2.0), (3.0, 2.0)],
            "source_primitive_ids": ["d0i0"],
        }],
    )
    assert row["first_remaining_gate"] == "exact_geometry_identity_unavailable"
    assert row["digit_tail_used"] is False
