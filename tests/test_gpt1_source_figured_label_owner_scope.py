"""Source-figured area MUST bind original text/page/viewport to one opening.

The test-only handoff cannot grant FIRM or invent 3D width/height.
"""
from copy import deepcopy

import pytest

from tests.test_gptmax_lot16_host_frame_gpt1_handoff import fixture, run


def _figure_only_host():
    rows, canonical = fixture()
    rows[2]["frame_record"] = None
    canonical[2]["host_frame_record_id"] = None
    return rows, canonical


def test_same_owner_original_figure_without_frame_enters_area_review_only():
    rows, canonical = _figure_only_host()
    original = deepcopy((rows, canonical))
    report = run(rows, canonical)
    item = report["opening_decisions"][2]
    assert item["original_figured_label_source_scope_bound"]
    assert item["new_gpt1_area_candidate_handoff"]
    assert item["first_remaining_gate"] == "whole_wall_frame_unavailable"
    assert not item["new_gpt1_candidate_handoff"]
    assert not item["measurement_published"] and not item["customer_seal_granted"]
    assert original == (rows, canonical)


@pytest.mark.parametrize("change", [
    lambda r,c: r[2]["original_label_dimension_result"]["evidence"].update(
        basis="inferred_gap_geometry"),
    lambda r,c: r[2]["original_label_dimension_result"]["evidence"].update(
        page_id="5"),
    lambda r,c: r[2]["original_label_dimension_result"]["evidence"].update(
        page_id=3),
    lambda r,c: r[2]["original_label_dimension_result"]["evidence"].update(
        viewport_id="foreign_page_view"),
    lambda r,c: r[2]["original_label_dimension_result"]["evidence"].update(
        semantic_kind="door"),
    lambda r,c: r[2]["original_label_dimension_result"]["evidence"].update(
        source_text_observation_ids=()),
    lambda r,c: r[2]["original_label_dimension_result"]["evidence"].update(
        source_text_observation_ids=("foreign-text",)),
    lambda r,c: r[2]["original_label_dimension_result"]["evidence"].update(
        source_text_observation_ids=("figured-word-3", "figured-word-3")),
    lambda r,c: r[2]["original_label_dimension_result"]["evidence"].update(
        source_text_observation_ids="figured-word-3"),
    lambda r,c: c[2]["evidence_ids"].remove("figured-word-3"),
])
def test_foreign_figured_source_never_becomes_gross_area_review(change):
    rows, canonical = _figure_only_host()
    change(rows, canonical)
    r = run(rows, canonical)
    item = r["opening_decisions"][2]
    assert item["figured_pair_area_support"]
    assert item["figured_area_receipt_bound"]
    assert not item["original_figured_label_source_scope_bound"]
    assert item["opening_area_first_remaining_gate"] == (
        "original_figured_label_source_scope_unverified"
    )
    assert not item["new_gpt1_area_candidate_handoff"]
    assert not r["gpt1_new_area_review_candidates"]
    assert not r["signed_customer_publisher_activated"]


def test_original_label_without_independent_semantic_claim_keeps_real_structural_kind():
    rows, canonical = _figure_only_host()
    e = rows[2]["original_label_dimension_result"]["evidence"]
    e["semantic_kind"] = None
    r = run(rows, canonical)
    item = r["opening_decisions"][2]
    assert item["original_figured_label_source_scope_bound"]
    assert item["new_gpt1_area_candidate_handoff"]
    assert not item["opening_count_granted"]


def test_original_label_view_unset_may_retain_producer_owned_page():
    rows, canonical = _figure_only_host()
    rows[2]["original_label_dimension_result"]["evidence"]["viewport_id"] = None
    r=run(rows,canonical)
    assert r["opening_decisions"][2]["original_figured_label_source_scope_bound"]


def test_figure_source_scope_gate_survives_unordered_3d_handoff():
    rows, canonical = fixture()
    canonical[2].update(
        width_record_id="width-3", height_record_id="height-3",
        width_m=1.2, height_m=1.8, geometry_complete=True,
        evidence_ids=["source-own-1", "figured", "figured-word-3", "binding-3",
                      "frame-3", "width-3", "height-3"],
    )
    rows[2]["original_label_dimension_result"]["evidence"]["page_id"] = "2"
    r = run(rows, canonical)
    x = r["opening_decisions"][2]
    assert x["axis_order_authenticated"]
    assert x["first_remaining_gate"] == "original_figured_label_source_scope_unverified"
    assert not x["new_gpt1_candidate_handoff"]
    assert not x["measurement_published"]


def test_gross_area_review_first_gate_census_consistent():
    rows, canonical=_figure_only_host()
    rows[2]["original_label_dimension_result"]["evidence"]["page_id"]="foreign"
    report = run(rows, canonical)
    assert report["area_first_gate_counts"]["original_figured_label_source_scope_unverified"] == 1
    assert sum(report["area_first_gate_counts"].values()) == len(report["opening_decisions"])
