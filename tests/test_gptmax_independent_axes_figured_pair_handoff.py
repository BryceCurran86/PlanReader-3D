"""GPT MAX -> GPT1: original unordered callout versus independently issued axes.

No test here issues an opening, trusts an inferred height, or maps frozen V2.
Every test uses source-neutral producer-shaped receipts.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from tests.test_gptmax_lot16_host_frame_gpt1_handoff import fixture, run
from tools.diag_gptmax_lot16_host_frame_gpt1_handoff import (
    _source_owned_axes_agree_with_figured_pair,
    verify_archived_signed_predecessors,
    original_host_frame_dimension_report,
)


def _independent_source_axes():
    rows, canonical = fixture()
    canonical[2].update(
        width_record_id="original-width:physical-3",
        height_record_id="original-height:physical-3",
        width_m=1.2,
        height_m=1.8,
        geometry_complete=True,
        evidence_ids=["figured", "original-width:physical-3",
                      "original-height:physical-3"],
    )
    # Original two-number label is corroborated only as an unordered pair.
    assert rows[2]["original_label_dimension_result"]["evidence"]["axis_order_resolved"] is False
    return rows, canonical


def test_unordered_label_plus_independent_producer_axes_is_gpt1_candidate_only():
    rows, canonical = _independent_source_axes()
    originals = deepcopy((rows, canonical))
    result = run(rows, canonical)
    target = next(x for x in result["opening_decisions"]
                  if x["physical_opening_id"] == "physical-3")
    assert target["figured_pair_area_support"]
    assert target["axis_order_authenticated"]
    assert target["original_figured_label_order_source_resolved"] is False
    assert target["independent_source_axis_record_ids"] == [
        "original-width:physical-3", "original-height:physical-3",
    ]
    assert target["first_remaining_gate"] == "independent_gpt1_measurement_validation_required"
    assert target["new_gpt1_candidate_handoff"]
    assert len(result["gpt1_new_handoff_candidates"]) == 1
    assert (rows, canonical) == originals
    assert not target["measurement_published"]
    assert not target["customer_seal_granted"]
    assert not target["opening_count_granted"]
    assert not result["signed_customer_publisher_activated"]


@pytest.mark.parametrize("claimed_receipts", [
    ["figured"],
    ["figured", "original-width:physical-3"],
    ["figured", "original-height:physical-3"],
    None,
    "figured original-width:physical-3 original-height:physical-3",
])
def test_unowned_axis_ids_cannot_claim_authentication(claimed_receipts):
    rows, canonical = _independent_source_axes()
    canonical[2]["evidence_ids"] = claimed_receipts
    result = run(rows, canonical)
    opening = result["opening_decisions"][2]
    assert opening["figured_pair_area_support"]
    assert not opening["axis_order_authenticated"]
    assert opening["first_remaining_gate"] == "width_height_axis_authority_unproven"
    assert not opening["new_gpt1_candidate_handoff"]
    assert not result["gpt1_new_handoff_candidates"]


def test_area_receipt_id_must_be_in_producer_evidence_set():
    rows, canonical = fixture()
    canonical[2]["evidence_ids"] = ["unrelated-receipt"]
    result = run(rows, canonical)
    opening = result["opening_decisions"][2]
    assert opening["figured_pair_area_support"]
    assert not opening["figured_area_receipt_bound"]
    assert opening["opening_area_first_remaining_gate"] == "original_figured_area_receipt_unbound"
    assert not result["gpt1_new_area_review_candidates"]


def test_equal_area_product_but_different_axes_does_not_enter_review_queue():
    rows, canonical = _independent_source_axes()
    # 900 x 2400 gives the identical 2.16 m² product as the real label
    # 1200 x 1800. A product check alone cannot establish source axes.
    canonical[2].update(width_m=0.9, height_m=2.4)
    result = run(rows, canonical)
    record = result["opening_decisions"][2]
    assert record["figured_pair_area_support"]
    assert not record["axis_order_authenticated"]
    assert record["first_remaining_gate"] == "width_height_axis_authority_unproven"
    assert not result["gpt1_new_handoff_candidates"]


@pytest.mark.parametrize("mutate", [
    lambda c,e:c.update(width_record_id=""),
    lambda c,e:c.update(width_record_id="original-height:physical-3"),
    lambda c,e:c.update(height_record_id=True),
    lambda c,e:c.update(width_record_id=" padded "),
    lambda c,e:c.update(geometry_complete="true"),
    lambda c,e:c.update(width_m=True),
    lambda c,e:c.update(height_m=float("inf")),
    lambda c,e:c.update(width_m=0.0),
    lambda c,e:e.update(dimension_values_mm=[1200]),
    lambda c,e:e.update(dimension_values_mm=[1200, True]),
    lambda c,e:e.update(dimension_values_mm=[1200, 1900]),
    lambda c,e:e.update(width_mm=1200.0),
    lambda c,e:e.update(width_mm=1800.0, height_mm=1200.0),
])
def test_unissued_foreign_untyped_or_disagreeing_axes_cannot_be_gpt1_candidate(mutate):
    rows, canonical = _independent_source_axes()
    e = rows[2]["original_label_dimension_result"]["evidence"]
    mutate(canonical[2], e)
    # If a forged dimension payload invalidates the figured area entirely,
    # the existing strict source pair check raises; in either case NO positive.
    try:
        result = run(rows, canonical)
    except (ValueError, TypeError):
        return
    assert not result["gpt1_new_handoff_candidates"]
    assert result["opening_decisions"][2]["first_remaining_gate"] in {
        "width_height_axis_authority_unproven",
        "source_figured_dimension_pair_unproven",
    }


def test_corresponding_typed_width_height_claims_remain_source_only():
    rows, canonical = _independent_source_axes()
    e = rows[2]["original_label_dimension_result"]["evidence"]
    e.update(axis_order_resolved=True, width_mm=1200.0, height_mm=1800.0)
    result = run(rows, canonical)
    assert result["opening_decisions"][2]["original_figured_label_order_source_resolved"]
    assert result["opening_decisions"][2]["axis_order_authenticated"]
    assert result["opening_decisions"][2]["new_gpt1_candidate_handoff"]
    assert not result["global_opening_count_granted"]


def test_prior_signed_area_never_reappears_as_new_gpt1_candidate():
    rows, canonical = _independent_source_axes()
    rows[2]["quantity_id"] = "old-source-sealed-opening-area-id"
    result = run(rows, canonical)
    assert result["opening_decisions"][2]["axis_order_authenticated"]
    assert result["original_signed_area_quantities"] == 1
    assert not result["gpt1_new_handoff_candidates"]


def test_missing_independent_axis_cannot_be_invented_from_area():
    rows, canonical = _independent_source_axes()
    canonical[2].update(height_record_id=None, height_m=None)
    result = run(rows, canonical)
    assert result["first_gate_counts"]["width_height_axis_authority_unproven"] == 1
    assert not result["gpt1_new_handoff_candidates"]


def test_unordered_original_pair_does_not_block_independent_area_review():
    rows, canonical = fixture()
    result = run(rows, canonical)
    x = result["opening_decisions"][2]
    assert x["figured_area_receipt_bound"]
    assert x["opening_area_first_remaining_gate"] == (
        "independent_gpt1_opening_area_measurement_validation_required"
    )
    assert x["new_gpt1_area_candidate_handoff"]
    assert len(result["gpt1_new_area_review_candidates"]) == 1
    assert not x["axis_order_authenticated"]
    assert not x["new_gpt1_candidate_handoff"]
    assert not x["measurement_published"] and not x["customer_seal_granted"]


def test_unowned_figured_area_receipt_never_enters_area_review():
    rows, canonical = fixture()
    canonical[2]["figured_area_record_id"] = "foreign-source-receipt"
    # Existing original producer scope already rejects a contradictory
    # canonical figured receipt. Retain that stronger first failure instead
    # of asking the optional review queue to soften the source-integrity gate.
    with pytest.raises(ValueError, match="canonical source dimension identity mismatch"):
        run(rows, canonical)


def test_area_review_still_requires_owned_kind_and_complete_host_frame():
    rows, canonical = fixture()
    canonical[2]["opening_kind"] = None
    result = run(rows, canonical)
    assert result["opening_decisions"][2]["opening_area_first_remaining_gate"] == (
        "opening_filling_kind_unproven"
    )
    assert not result["gpt1_new_area_review_candidates"]
    rows, canonical = fixture()
    rows[2]["frame_record"] = None
    canonical[2]["host_frame_record_id"] = None
    result = run(rows, canonical)
    assert result["opening_decisions"][2]["opening_area_first_remaining_gate"] == (
        "whole_wall_frame_unavailable"
    )
    assert not result["gpt1_new_area_review_candidates"]


def test_prior_source_sealed_area_is_not_sent_for_ninth_area_review():
    rows, canonical = fixture()
    rows[2]["quantity_id"] = "archived-original-quantity"
    result = run(rows, canonical)
    assert result["opening_decisions"][2]["opening_area_first_remaining_gate"] == (
        "original_signed_area_already_retained"
    )
    assert not result["gpt1_new_area_review_candidates"]


def test_area_first_gate_counts_are_complete_deterministic_inventory():
    result = run()
    assert result["area_first_gate_counts"] == {
        "independent_gpt1_opening_area_measurement_validation_required": 1,
        "structural_host_unavailable": 1,
        "whole_wall_frame_unavailable": 1,
    }
    assert sum(result["area_first_gate_counts"].values()) == 3



_ARCHIVE = Path("docs/engineering/lot16_original_signed_eight_row_20261015/production")


def _historical_archive():
    """Repository-pinned eight real historical rows; never a prediction input."""
    signed = json.loads((_ARCHIVE / "source_sealed_run.json").read_text())
    customers = json.loads((_ARCHIVE / "verified_customer_rows.json").read_text())
    assert len(signed["quantities"]) == len(customers) == 8
    return signed, customers


def test_reissued_historical_sealed_and_customer_bodies_require_exact_parity():
    signed, customers = _historical_archive()
    current = {"sealed_run": deepcopy(signed), "customer_rows": deepcopy(customers)}
    verify_archived_signed_predecessors(signed, customers, current)
    # Consumer order is not a physical identity or historical-body mutation.
    current["customer_rows"].reverse()
    verify_archived_signed_predecessors(signed, customers, current)


@pytest.mark.parametrize("change", [
    "quantity_value", "quantity_fingerprint", "quantity_lineage",
    "signed_row_missing", "customer_nested_quantity", "customer_fingerprint",
    "customer_missing", "customer_duplicate",
])
def test_predecessor_mutations_cannot_hide_behind_unchanged_quantity_id(change):
    signed, customers = _historical_archive()
    current = {"sealed_run": deepcopy(signed), "customer_rows": deepcopy(customers)}
    if change == "quantity_value":
        current["sealed_run"]["quantities"][0]["value"] += 1
    elif change == "quantity_fingerprint":
        current["sealed_run"]["quantities"][0]["fingerprint"] = "0" * 64
    elif change == "quantity_lineage":
        current["sealed_run"]["quantities"][0]["evidence_ids"].pop()
    elif change == "signed_row_missing":
        current["sealed_run"]["quantities"].pop()
    elif change == "customer_nested_quantity":
        current["customer_rows"][0]["commercial_projection_provenance"]["quantity"]["value"] += 1
    elif change == "customer_fingerprint":
        current["customer_rows"][0]["commercial_projection_fingerprint"] = "0" * 64
    elif change == "customer_missing":
        current["customer_rows"].pop()
    elif change == "customer_duplicate":
        current["customer_rows"].append(deepcopy(current["customer_rows"][0]))
    with pytest.raises((RuntimeError, ValueError)):
        verify_archived_signed_predecessors(signed, customers, current)


def test_signed_customer_archive_cannot_be_half_supplied_before_source_ingestion():
    signed, _ = _historical_archive()
    with pytest.raises(ValueError, match="supplied together"):
        original_host_frame_dimension_report(
            b"synthetic input, never client original", page_id="3",
            archived_signed_run=signed,
        )
