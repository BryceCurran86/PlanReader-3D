"""Publisher-equivalent source FIGURED area requires canonical value and basis.

Shadow review only: never seal, count, invent host or read frozen gold.
"""
from copy import deepcopy

import pytest

from tests.test_gptmax_lot16_host_frame_gpt1_handoff import fixture, run


def _host_only():
    rows, canonical = fixture()
    rows[2]["frame_record"] = None
    canonical[2]["host_frame_record_id"] = None
    return rows, canonical


def test_source_owned_host_only_figured_area_value_can_reach_review_not_publication():
    rows, canonical = _host_only()
    before = deepcopy((rows, canonical))
    result = run(rows, canonical)
    d = result["opening_decisions"][2]
    assert d["canonical_figured_area_publication_basis_bound"]
    assert d["canonical_figured_area_value_bound"]
    assert d["new_gpt1_area_candidate_handoff"]
    assert d["first_remaining_gate"] == "whole_wall_frame_unavailable"
    assert not d["new_gpt1_candidate_handoff"]
    assert not result["signed_customer_publisher_activated"]
    assert before == (rows, canonical)


@pytest.mark.parametrize("wrong_basis", [
    None, "", "resolved_opening_geometry", "authenticated_elevation_frame",
    "figured_opening_label ", True, 1,
])
def test_wrong_canonical_area_basis_cannot_masquerade_as_figured_label(wrong_basis):
    rows, canonical = _host_only()
    canonical[2]["area_basis"] = wrong_basis
    result = run(rows, canonical)
    d = result["opening_decisions"][2]
    assert d["opening_area_first_remaining_gate"] == (
        "canonical_figured_area_publication_basis_unproven"
    )
    assert not d["canonical_figured_area_publication_basis_bound"]
    assert not d["new_gpt1_area_candidate_handoff"]
    assert not result["gpt1_new_area_review_candidates"]


@pytest.mark.parametrize("wrong_value", [
    None, 0, -1.0, False, "2.16", float("nan"), float("inf"),
    2.159, 2.161, 8.82,
])
def test_missing_inconsistent_or_untyped_canonical_area_is_not_ready(wrong_value):
    rows, canonical = _host_only()
    canonical[2]["area_m2"] = wrong_value
    result = run(rows, canonical)
    d = result["opening_decisions"][2]
    assert d["opening_area_first_remaining_gate"] == "canonical_figured_area_value_unproven"
    assert d["canonical_figured_area_publication_basis_bound"]
    assert not d["canonical_figured_area_value_bound"]
    assert not d["new_gpt1_area_candidate_handoff"]


def test_already_signed_original_source_area_stays_retained_not_rediscovered():
    rows, canonical = _host_only()
    rows[2]["quantity_id"] = "original-source-signed-before-this-change"
    result = run(rows, canonical)
    assert result["original_signed_area_quantities"] == 1
    assert result["opening_decisions"][2]["opening_area_first_remaining_gate"] == (
        "original_signed_area_already_retained"
    )
    assert not result["gpt1_new_area_review_candidates"]


def test_canonical_area_cannot_borrow_a_different_original_figure():
    rows, canonical = _host_only()
    original = deepcopy((rows, canonical))
    canonical[2]["area_m2"] = 5.67
    result = run(rows, canonical)
    assert result["opening_decisions"][2]["opening_area_first_remaining_gate"] == (
        "canonical_figured_area_value_unproven"
    )
    assert rows == original[0]


def test_first_gate_census_does_not_count_unpublishable_numeric_area():
    rows, canonical = _host_only()
    canonical[2]["area_m2"] = 2.20
    r = run(rows, canonical)
    assert r["area_first_gate_counts"]["canonical_figured_area_value_unproven"] == 1
    assert sum(r["area_first_gate_counts"].values()) == 3
    assert r["global_opening_count_granted"] is False
