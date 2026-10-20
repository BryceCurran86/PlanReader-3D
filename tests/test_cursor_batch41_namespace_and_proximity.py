"""Synthetic proofs for batch41 namespace bridge + proximity abstain."""
from __future__ import annotations

from pb_g17_face_end_span_length_census_shadow import geometric_proximity_abstain_shadow
from pb_opening_universe_completeness_shadow import (
    assess_opening_universe_completeness_shadow,
)
from pb_segment_w4_id_namespace_bridge_shadow import (
    assess_segment_w4_namespace_bridge_variants,
    classify_id_namespace_taxonomy,
)
from pb_three_laurel_q5446_first_gate_stub_shadow import (
    build_three_laurel_q5446_missing_stub_report,
)
from tools.diag_gptmax_lot16_host_frame_gpt1_handoff import (
    _axis_values_match_figured_pair,
)


def test_namespace_taxonomy_separates_raster_and_w4_d_index():
    tax = classify_id_namespace_taxonomy(
        segment_line_ids=[
            "raster_opening_primitive:abc:2.0.0:raster_wall_band_face:1467",
        ],
        w4_primitive_ids=["d0i0", "d1467i0"],
    )
    assert tax["segment_prefix_counts"]["raster_opening_primitive"] == 1
    assert tax["w4_prefix_counts"]["w4_d_index"] == 2
    assert tax["host_granted"] is False


def test_digit_tail_collision_abstains_without_host():
    row = assess_segment_w4_namespace_bridge_variants(
        physical_opening_id="physical_opening_existence_synthetic",
        segment_line_ids=[
            "raster_opening_primitive:x:2.0.0:raster_wall_band_face:1467",
        ],
        w4_primitive_ids=["d1467i0", "d999i0"],
    )
    assert row["first_remaining_gate"] == "digit_tail_collision_ambiguous_abstain"
    assert row["digit_tail_collision_count"] == 1
    assert row["host_granted"] is False
    assert row["nearest_wins_applied"] is False


def test_disjoint_namespaces_remain_disjoint():
    row = assess_segment_w4_namespace_bridge_variants(
        physical_opening_id="oid",
        segment_line_ids=[
            "raster_opening_primitive:x:2.0.0:raster_wall_band_face:11",
        ],
        w4_primitive_ids=["d0i0"],
    )
    assert row["first_remaining_gate"] == "all_namespace_bridge_variants_disjoint"


def test_proximity_multi_candidate_abstains():
    row = geometric_proximity_abstain_shadow(
        candidate_distances_pdf_pts=[
            {"wall_candidate_id": "a", "distance_pdf_pts": 0.5},
            {"wall_candidate_id": "b", "distance_pdf_pts": 0.1},
        ],
    )
    assert row["selected_wall_candidate_id"] is None
    assert row["nearest_wins_applied"] is False
    assert row["first_remaining_gate"] == "geometric_proximity_ambiguous_abstain"


def test_universe_incomplete_invariant():
    row = assess_opening_universe_completeness_shadow(
        instance_ids=["a", "b"],
        universe_complete=False,
    )
    assert row["first_remaining_gate"] == "opening_universe_incomplete"
    assert row["opening_count_granted"] is False


def test_four_project_stubs_remain_missing():
    stub = build_three_laurel_q5446_missing_stub_report(
        lot16_and_maryborough_rows=[{
            "project_key": "au_qld_lot16_power",
            "physical_object_id": "o1",
            "first_remaining_gate": "structural_host_unavailable",
            "source_sha256": "abc",
            "snapshot_id": "s1",
        }],
    )
    assert "au_qld_3laurel" in stub["missing_project_keys"]
    assert "au_qld_q5446" in stub["missing_project_keys"]


def test_axis_values_match_helper_restored():
    assert _axis_values_match_figured_pair(0.9, 2.1, (900.0, 2100.0)) is True
    assert _axis_values_match_figured_pair(0.7, 2.7, (900.0, 2100.0)) is False
