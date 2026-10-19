"""GPT1 source receipt ownership: diagnostic readiness must match signed area preflight.

These tests are source-neutral and make no signed quantity or benchmark claim.
"""
from copy import deepcopy

from tests.test_gptmax_lot16_host_frame_gpt1_handoff import fixture, run


def _host_only():
    rows, canonical = fixture()
    rows[2]["frame_record"] = None
    canonical[2]["host_frame_record_id"] = None
    return rows, canonical


def test_host_only_figured_area_can_reach_gpt1_review_with_owned_host_receipt():
    rows, canonical = _host_only()
    result = run(rows, canonical)
    d = result["opening_decisions"][2]
    assert d["original_host_binding_receipt_bound"]
    assert not d["original_host_frame_receipt_bound"]
    assert d["figured_area_receipt_bound"]
    assert d["new_gpt1_area_candidate_handoff"]
    assert d["figured_area_only_frame_unavailable"]
    assert d["first_remaining_gate"] == "whole_wall_frame_unavailable"
    assert not d["new_gpt1_candidate_handoff"]
    assert not d["measurement_published"] and not d["customer_seal_granted"]
    assert not result["signed_customer_publisher_activated"]


def test_missing_canonical_host_receipt_never_reports_area_ready():
    rows, canonical = _host_only()
    canonical[2]["evidence_ids"] = ["figured"]
    result = run(rows, canonical)
    d = result["opening_decisions"][2]
    assert d["authenticated_host_record_id"] == "binding-3"
    assert not d["original_host_binding_receipt_bound"]
    assert d["opening_area_first_remaining_gate"] == "original_host_binding_receipt_unbound"
    assert not d["new_gpt1_area_candidate_handoff"]
    assert not result["gpt1_new_area_review_candidates"]


def test_missing_host_receipt_blocks_complete_frame_and_both_review_queues():
    rows, canonical = fixture()
    canonical[2]["evidence_ids"] = ["figured", "frame-3"]
    result = run(rows, canonical)
    d = result["opening_decisions"][2]
    assert not d["original_host_binding_receipt_bound"]
    assert d["original_host_frame_receipt_bound"]
    assert d["opening_area_first_remaining_gate"] == "original_host_binding_receipt_unbound"
    assert d["first_remaining_gate"] == "width_height_axis_authority_unproven"
    assert not d["new_gpt1_area_candidate_handoff"]
    assert not d["new_gpt1_candidate_handoff"]


def test_missing_frame_receipt_blocks_claimed_frame_even_for_figured_area():
    rows, canonical = fixture()
    canonical[2]["evidence_ids"] = ["figured", "binding-3"]
    result = run(rows, canonical)
    d = result["opening_decisions"][2]
    assert d["original_host_binding_receipt_bound"]
    assert not d["original_host_frame_receipt_bound"]
    assert d["opening_area_first_remaining_gate"] == "original_host_frame_receipt_unbound"
    assert not d["new_gpt1_area_candidate_handoff"]


def test_unrelated_receipt_cannot_substitute_for_host_receipt():
    rows, canonical = _host_only()
    canonical[2]["evidence_ids"] = ["figured", "binding-2"]
    result = run(rows, canonical)
    assert result["opening_decisions"][2]["opening_area_first_remaining_gate"] == (
        "original_host_binding_receipt_unbound"
    )


def test_original_source_immutability_and_order_invariance():
    rows, canonical = _host_only()
    original = deepcopy((rows, canonical))
    forward = run(rows, canonical)
    reverse = run(rows[::-1], canonical[::-1])
    assert forward == reverse
    assert (rows, canonical) == original


def test_already_signed_host_only_area_cannot_be_rediscovered_as_ninth():
    rows, canonical = _host_only()
    rows[2]["quantity_id"] = "original-signed-area"
    result = run(rows, canonical)
    d = result["opening_decisions"][2]
    assert d["opening_area_first_remaining_gate"] == "original_signed_area_already_retained"
    assert not result["gpt1_new_area_review_candidates"]
    assert not result["signed_customer_publisher_activated"]


def test_host_and_frame_receipts_with_firm_independent_axes_get_3d_review():
    rows, canonical = fixture()
    canonical[2].update(
        width_record_id="issued-width-3", height_record_id="issued-height-3",
        width_m=1.2, height_m=1.8, geometry_complete=True,
        evidence_ids=["figured", "binding-3", "frame-3",
                      "issued-width-3", "issued-height-3"],
    )
    result = run(rows, canonical)
    d = result["opening_decisions"][2]
    assert d["original_host_binding_receipt_bound"]
    assert d["original_host_frame_receipt_bound"]
    assert d["axis_order_authenticated"]
    assert d["new_gpt1_candidate_handoff"]
    assert d["new_gpt1_area_candidate_handoff"]
    assert not d["measurement_published"]


def test_all_claimed_receipts_still_do_not_mint_a_quantity():
    rows, canonical = _host_only()
    output = run(rows, canonical)
    assert output["original_signed_area_quantities"] == 0
    assert output["global_opening_count_granted"] is False
    assert output["signed_customer_publisher_activated"] is False
    assert all(not d["measurement_published"] and not d["customer_seal_granted"]
               for d in output["opening_decisions"])
