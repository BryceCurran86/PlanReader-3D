"""Synthetic proofs for observation-geometry identity (not nearest)."""
from __future__ import annotations

from pb_segment_w4_observation_geometry_identity_shadow import (
    assess_segment_w4_observation_geometry_identity_shadow,
    collinear_overlap_length_pt,
)


def test_collinear_overlap_positive_and_gap_refused():
    overlap = collinear_overlap_length_pt(
        (0.0, 0.0, 10.0, 0.0),
        (4.0, 0.0, 16.0, 0.0),
    )
    assert overlap is not None and overlap > 5.0
    assert collinear_overlap_length_pt(
        (0.0, 0.0, 2.0, 0.0),
        (4.0, 0.0, 6.0, 0.0),
    ) is None
    assert collinear_overlap_length_pt(
        (0.0, 0.0, 10.0, 0.0),
        (0.0, 1.0, 10.0, 1.0),
    ) is None


def test_endpoint_reverse_and_input_order_invariant():
    segs = {"s1": (0.0, 0.0, 5.0, 0.0)}
    geom = {
        "raster_segment:a:1.0.0:1": {
            "observation_id": "vis-1",
            "observation_kind": "raster_pdf_visible_segment",
            "line_pt": [5.0, 0.0, 0.0, 0.0],
        }
    }
    walls_a = [{"wall_candidate_id": "w1", "source_primitive_ids": ["raster_segment:a:1.0.0:1"]}]
    walls_b = [{"wall_candidate_id": "w2", "source_primitive_ids": ["d0i0"]}, *walls_a]
    ra = assess_segment_w4_observation_geometry_identity_shadow(
        physical_opening_id="oid",
        segment_lines_by_id=segs,
        w4_wall_records=walls_a,
        geometries_by_ref=geom,
    )
    rb = assess_segment_w4_observation_geometry_identity_shadow(
        physical_opening_id="oid",
        segment_lines_by_id=segs,
        w4_wall_records=list(reversed(walls_b)),
        geometries_by_ref=geom,
    )
    assert ra["first_remaining_gate"] == "exact_observation_geometry_unique_wall_review_only"
    assert rb["first_remaining_gate"] == ra["first_remaining_gate"]
    assert ra["host_granted"] is False
    assert ra["selected_wall_candidate_id"] is None


def test_collinear_longer_w4_is_review_only_not_host():
    row = assess_segment_w4_observation_geometry_identity_shadow(
        physical_opening_id="oid",
        segment_lines_by_id={"s1": (2.0, 0.0, 5.0, 0.0)},
        w4_wall_records=[{
            "wall_candidate_id": "w1",
            "source_primitive_ids": ["visible:raster_segment:a:1.0.0:9"],
        }],
        geometries_by_ref={
            "raster_segment:a:1.0.0:9": {
                "observation_id": "v",
                "observation_kind": "raster_pdf_segment",
                "line_pt": [0.0, 0.0, 10.0, 0.0],
            }
        },
    )
    assert row["first_remaining_gate"] == "collinear_overlap_unique_wall_review_only"
    assert row["collinear_overlap_match_count"] == 1
    assert row["nearest_wins_applied"] is False
    assert row["host_granted"] is False


def test_two_walls_collinear_overlap_abstains():
    geom = {
        "raster_segment:a:0": {
            "observation_id": "a",
            "observation_kind": "raster_pdf_segment",
            "line_pt": [0.0, 0.0, 10.0, 0.0],
        },
        "raster_segment:b:0": {
            "observation_id": "b",
            "observation_kind": "raster_pdf_segment",
            "line_pt": [1.0, 0.0, 9.0, 0.0],
        },
    }
    row = assess_segment_w4_observation_geometry_identity_shadow(
        physical_opening_id="oid",
        segment_lines_by_id={"s1": (2.0, 0.0, 8.0, 0.0)},
        w4_wall_records=[
            {"wall_candidate_id": "w1", "source_primitive_ids": ["raster_segment:a:0"]},
            {"wall_candidate_id": "w2", "source_primitive_ids": ["raster_segment:b:0"]},
        ],
        geometries_by_ref=geom,
    )
    assert row["first_remaining_gate"] == "collinear_overlap_ambiguous_multi_wall"
    assert len(row["overlap_matched_wall_candidate_ids"]) == 2
    assert row["host_granted"] is False
