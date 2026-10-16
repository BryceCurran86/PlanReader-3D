"""Integrity regressions for the *diagnostic* GPT MAX original-source ledger.

This only guards a pinned serialized witness against accidental identity/receipt
drift. It does NOT replay the original PDF, certify geometry, create an authority
record, or permit production quantity/count publication.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest


LEDGER = (
    Path(__file__).resolve().parents[1]
    / "docs/engineering/gptmax_lot16_host_source_queue_20261016.json"
)
SOURCE_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
SNAPSHOT = "source_snapshot_3fcb6bc5c44b51d930e9600080501d27"
UNHOSTED = {
    "physical_opening_existence_33d277d4c6b6ce758b0594f9d47ce4d8",
    "physical_opening_existence_81a45c3a33c2a4c0bfdf243aa45a780d",
    "physical_opening_existence_a68d0b7d738b5de9a1588b4e680e1a8f",
    "physical_opening_existence_b248972669988c108ebc90c6ca3908fd",
    "physical_opening_existence_ba7f75a2e5f68bcce87cd00ac1acf90b",
    "physical_opening_existence_f819752382d44a00d9f28feca4b00787",
}
HOSTED_FRAMELESS = {
    "physical_opening_existence_2c31ccb074d8eae86cac281c0fde1176",
    "physical_opening_existence_dbcec9c3cfa8e22b332479d09a601985",
}
PREEXISTING_SIGNED_CASES = {
    "physical_opening_existence_2c31ccb074d8eae86cac281c0fde1176":
        ("opening_area_4227fdeb71838722a4a7f0251c3dda60", 10.08),
    "physical_opening_existence_dbcec9c3cfa8e22b332479d09a601985":
        ("opening_area_6809b61112132ffd701e6eae02076876", 1.26),
}


def _read_ledger() -> dict:
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def _assert_locked_evidence(ledger: dict) -> None:
    # Never mix the all-pages diagnostic snapshot with the selected collector.
    assert ledger["source_sha256"] == SOURCE_SHA
    assert ledger["snapshot_id"] == SNAPSHOT
    assert ledger["decision_scope_id"] == "wall-source:page-3"
    assert ledger["current_main_sealed_handoff"]["source_sha256"] == SOURCE_SHA

    base = ledger["baseline_summary"]
    assert (
        base["physical_existence_claims"],
        base["authenticated_hosts"],
        base["resolved_source_frames"],
        base["canonical_opening_area_records"],
    ) == (21, 15, 9, 8)

    # Incomplete original G17 candidate universe prevents a count claim.
    closure = ledger["raw_raster_candidate_closure"]
    assert closure["page_id"] == "3"
    assert closure["candidate_universe_complete"] is False
    assert (closure["raw_candidate_count"], closure["resolved_candidate_count"]) == (30, 21)
    assert len(set(closure["unresolved_candidate_ids"])) == 9

    grants = ledger["authority_grants"]
    assert set(grants) == {
        "benchmark_score", "new_frame", "new_height", "new_host",
        "new_quantity", "new_wall", "new_width", "opening_count",
    }
    assert all(value is False for value in grants.values())

    cases = ledger["case_evidence"]
    ids = [case["physical_opening_id"] for case in cases]
    assert len(ids) == len(set(ids)) == 8
    assert set(ids) == UNHOSTED | HOSTED_FRAMELESS

    for case in cases:
        opening_id = case["physical_opening_id"]
        host = case["host_binding"]
        frame = case["frame"]
        metric = case["measurement"]
        assert metric["opening_identity_id"] == opening_id
        assert frame["opening_identity_id"] == opening_id
        assert metric["decision_scope_id"] == "wall-source:page-3"
        assert metric["page_id"] == "3"
        assert metric["width_record_id"] is None
        assert metric["height_record_id"] is None
        assert metric["width_status"] == "abstained"
        assert metric["height_status"] == "abstained"
        assert frame["status"] == "abstained"
        assert frame["record_id"] is None
        if opening_id in UNHOSTED:
            assert host["status"] == "abstained"
            assert host["record_id"] is None
            assert case["existing_signed_quantity_receipts"] == []
        else:
            assert host["status"] == "corroborated"
            assert host["record_id"]
            assert len(case["existing_signed_quantity_receipts"]) == 1
            receipt = case["existing_signed_quantity_receipts"][0]
            expected_id, expected_area = PREEXISTING_SIGNED_CASES[opening_id]
            assert receipt["quantity_id"] == expected_id
            assert receipt["value"] == expected_area
            assert receipt["unit"] == "m2"
            assert receipt["lineage_ok"] is True
            assert receipt["status"] == "corroborated"
            assert receipt["object_identity_refs"] == [opening_id]

    signed = ledger["current_main_sealed_handoff"]
    sealed_ids = signed["sealed_quantity_ids"]
    customer_ids = signed["customer_verified_quantity_ids"]
    assert signed["quantity_count"] == 8
    assert len(sealed_ids) == len(set(sealed_ids)) == 8
    assert len(customer_ids) == len(set(customer_ids)) == 8
    assert set(sealed_ids) == set(customer_ids)
    assert all(quantity_id in sealed_ids for quantity_id, _ in
               PREEXISTING_SIGNED_CASES.values())
    assert signed["signed_run_and_customer_parity"] is True
    assert signed["benchmark_score_granted"] is False
    assert signed["frozen_v2_reconciliation_complete"] is False


def test_gptmax_selected_original_source_witness_is_internally_consistent() -> None:
    _assert_locked_evidence(_read_ledger())


@pytest.mark.parametrize("mutation", [
    "host_promoted",
    "frame_promoted",
    "source_snapshot_swapped",
    "selected_host_count_changed",
    "opening_count_falsely_authorized",
    "quantity_mutated",
    "customer_id_duplicated",
    "case_duplicated",
    "metric_height_invented",
])
def test_gptmax_queue_rejects_signed_or_source_promotion_drift(mutation: str) -> None:
    record = deepcopy(_read_ledger())
    by_id = {case["physical_opening_id"]: case for case in record["case_evidence"]}
    if mutation == "host_promoted":
        by_id[next(iter(sorted(UNHOSTED)))]["host_binding"]["status"] = "corroborated"
    elif mutation == "frame_promoted":
        by_id[next(iter(sorted(HOSTED_FRAMELESS)))]["frame"]["status"] = "corroborated"
    elif mutation == "source_snapshot_swapped":
        record["snapshot_id"] = "source_snapshot_7ad8bf09e3ebbec9797df89842574683"
    elif mutation == "selected_host_count_changed":
        record["baseline_summary"]["authenticated_hosts"] = 16
    elif mutation == "opening_count_falsely_authorized":
        record["raw_raster_candidate_closure"]["candidate_universe_complete"] = True
    elif mutation == "quantity_mutated":
        by_id[next(iter(sorted(HOSTED_FRAMELESS)))]["existing_signed_quantity_receipts"][0]["value"] = 9.9
    elif mutation == "customer_id_duplicated":
        record["current_main_sealed_handoff"]["customer_verified_quantity_ids"][0] = (
            record["current_main_sealed_handoff"]["customer_verified_quantity_ids"][1]
        )
    elif mutation == "case_duplicated":
        record["case_evidence"].append(deepcopy(record["case_evidence"][0]))
    elif mutation == "metric_height_invented":
        by_id[next(iter(sorted(UNHOSTED)))]["measurement"]["height_record_id"] = "unproved-height"
    with pytest.raises(AssertionError):
        _assert_locked_evidence(record)
