from copy import deepcopy
import math

import pytest

from tools.gptmax_w2_source_junction_forensics import compare_wall_records


def _wall(edges, path=None, parent="source-x"):
    return {
        "wall_candidate_id": "source-wall",
        "physical_identity": {"source_primitive_ids": [parent]},
        "source_edge_fragments": [
            {"edge_id": f"e{i}", "geometry": edge,
             "source_primitive_ids": [parent]}
            for i, edge in enumerate(edges)],
        "wall_candidate": {"centerline_pts": path or [(10., 0.), (30., 0.)]},
    }


def test_split_same_line_exposes_missing_interval_in_both_versions():
    before = _wall([(10., 0., 20., 0.), (22., 0., 30., 0.)],
                   [(10., 0.), (21., .2), (30., 0.)])
    after = _wall([(10., 0., 20., 0.), (22., 0., 25., 0.), (25., 0., 30., 0.)],
                  [(10., 0.), (21., .2), (25., -.36), (30., 0.)])
    report = compare_wall_records([before], [after])
    row = report["matched_source_ancestries"][0]
    assert row["baseline"]["unproven_source_gaps_page_pt"] == [(10., 12.)]
    assert row["candidate"]["unproven_source_gaps_page_pt"] == [(10., 12.)]
    assert abs(row["candidate"]["snapped_path_offsets_page_pt"][2]["signed_normal_offset_pt"]) == pytest.approx(.36)
    assert row["continuity_authenticated"] is False
    assert report["may_publish_hosts"] is False
    assert report["benchmark_accuracy"] is None


def test_edge_order_and_direction_do_not_remove_gap():
    before = _wall([(10., 0., 20., 0.), (22., 0., 30., 0.)])
    after = deepcopy(before)
    after["source_edge_fragments"] = [
        {**x, "geometry": (*x["geometry"][2:], *x["geometry"][:2])}
        for x in reversed(after["source_edge_fragments"])]
    row = compare_wall_records([before], [after])["matched_source_ancestries"][0]
    assert row["baseline"]["unproven_source_gaps_page_pt"] == row["candidate"]["unproven_source_gaps_page_pt"]


def test_ambiguous_candidate_ancestry_is_never_chosen_by_nearest_match():
    old = _wall([(0., 0., 20., 0.)])
    report = compare_wall_records([old], [old, deepcopy(old)])
    assert not report["matched_source_ancestries"]
    assert report["unmatched_or_ambiguous"][0]["reason"] == "unmatched_or_ambiguous_source_owner"


@pytest.mark.parametrize("damage", ["nan", "invalid_geometry", "missing_parent", "duplicated_parent"])
def test_bad_source_fails_closed(damage):
    item = _wall([(10., 0., 20., 0.)])
    if damage == "nan": item["source_edge_fragments"][0]["geometry"] = [math.nan, 0, 20, 0]
    elif damage == "invalid_geometry": item["source_edge_fragments"][0]["geometry"] = [10, 0, 20]
    elif damage == "missing_parent": item["physical_identity"]["source_primitive_ids"] = []
    else: item["physical_identity"]["source_primitive_ids"] = ["source-x", "source-x"]
    with pytest.raises(ValueError):
        compare_wall_records([item], [deepcopy(item)])


def test_non_collinear_candidate_fragment_never_becomes_continuity():
    old = _wall([(10., 0., 20., 0.)])
    new = _wall([(10., 0., 20., .1)])
    row = compare_wall_records([old], [new])["matched_source_ancestries"][0]
    assert row["candidate"]["source_aligned_intervals_page_pt"] == []
    assert row["candidate"]["off_axis_fragment_edge_ids"] == ["e0"]


def test_absent_candidate_source_is_unmatched_without_guess():
    old = _wall([(10., 0., 20., 0.)])
    data = compare_wall_records([old], [])
    assert data["unmatched_or_ambiguous"][0]["candidate_candidate_count"] == 0
    assert data["may_publish_quantities"] is False
