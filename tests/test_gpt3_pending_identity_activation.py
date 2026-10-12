from __future__ import annotations

import json
from pathlib import Path

import pytest

import tools.prepare_gpt3_pending_identity_activation as module


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    ROOT
    / "docs/engineering/lot16_original_identity_reconciliation_20261012"
)
MANIFEST = (
    ROOT
    / "benchmarks/frozen_holdout/full_plan_v2/projects"
    / "au_qld_lot16_power/source_manifest.json"
)
SOURCE_SHA = (
    "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
)
PHYSICAL = (
    "physical_opening_existence_c4d87543028146e1cff0b5e2ca480c55"
)
ITEM = "lot16-1218-sgw-01-area"
OBJECT_REF = "lot16:opening:p3:1218_sgw:01"


def _json(name):
    return json.loads(
        (EVIDENCE / name).read_text(encoding="utf-8")
    )


def _manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _pending(
    physical=PHYSICAL,
    item=ITEM,
    object_ref=OBJECT_REF,
):
    return {
        "project_id": "au_qld_lot16_power",
        "source_sha256": SOURCE_SHA,
        "status": "IDENTITY_READY_QUANTITY_UNSEALED",
        "physical_opening_id": physical,
        "benchmark_item_id": item,
        "benchmark_object_ref": object_ref,
    }


def _empty_map():
    return {
        "schema_version": "1.0.0",
        "project_id": "au_qld_lot16_power",
        "source_sha256s": [SOURCE_SHA],
        "bindings": [],
    }


def _activate(
    *,
    pending=None,
    sealed=None,
    rows=None,
    active=None,
    manifest=None,
):
    return module.build_activation(
        pending_ledger=_pending() if pending is None else pending,
        sealed_run_payload=(
            _json("source_sealed_run.json")
            if sealed is None
            else sealed
        ),
        customer_rows=(
            _json("verified_customer_rows.json")
            if rows is None
            else rows
        ),
        active_identity_map_payload=(
            _empty_map() if active is None else active
        ),
        source_manifest=(
            _manifest() if manifest is None else manifest
        ),
    )


def test_real_signed_run_and_customer_rows_activate_exact_pre_certified_identity():
    output, receipt = _activate()

    assert receipt["activated_count"] == 1
    assert receipt["benchmark_score_granted"] is False
    assert receipt["benchmark_accuracy"] is None
    assert receipt["evaluator_invoked"] is False
    assert receipt["activated"][0][
        "physical_opening_id"
    ] == PHYSICAL
    assert receipt["activated"][0][
        "benchmark_item_id"
    ] == ITEM
    assert output["bindings"] == [{
        "benchmark_item_id": ITEM,
        "production_family": "opening_area",
        "production_object_identity_refs": [PHYSICAL],
    }]



def test_real_partial_map_preserves_existing_bindings_when_target_activates():
    active = _json("identity_map.json")
    original_bindings = list(active["bindings"])
    target = next(
        binding
        for binding in original_bindings
        if binding["benchmark_item_id"] == ITEM
    )
    active["bindings"] = [
        binding
        for binding in original_bindings
        if binding is not target
    ]

    output, receipt = _activate(active=active)

    assert receipt["activated_count"] == 1
    assert len(output["bindings"]) == len(original_bindings)
    preserved = {
        (
            binding["benchmark_item_id"],
            binding.get("production_family"),
            tuple(binding["production_object_identity_refs"]),
        )
        for binding in output["bindings"]
        if binding["benchmark_item_id"] != ITEM
    }
    expected_preserved = {
        (
            binding["benchmark_item_id"],
            binding.get("production_family"),
            tuple(binding["production_object_identity_refs"]),
        )
        for binding in original_bindings
        if binding["benchmark_item_id"] != ITEM
    }
    assert preserved == expected_preserved
    activated = next(
        binding
        for binding in output["bindings"]
        if binding["benchmark_item_id"] == ITEM
    )
    assert activated["production_object_identity_refs"] == [PHYSICAL]


def test_real_active_map_prevents_duplicate_activation():
    with pytest.raises(ValueError, match="already active"):
        _activate(active=_json("identity_map.json"))


def test_tampered_sealed_fingerprint_fails_before_activation():
    sealed = _json("source_sealed_run.json")
    sealed["fingerprint"] = "0" * 64
    with pytest.raises(Exception):
        _activate(sealed=sealed)


def test_customer_row_tamper_fails_before_activation():
    rows = _json("verified_customer_rows.json")
    sealed = _json("source_sealed_run.json")
    target = next(
        quantity
        for quantity in sealed["quantities"]
        if quantity["object_identity_refs"] == [PHYSICAL]
    )
    row = next(
        customer
        for customer in rows
        if customer.get("quantity_id") == target["quantity_id"]
    )
    row["unit"] = "ea"
    with pytest.raises(Exception):
        _activate(sealed=sealed, rows=rows)


def test_unsealed_pre_certified_identity_cannot_be_activated():
    pending = _pending(
        physical="physical_opening_existence_not_sealed",
        item=ITEM,
        object_ref=OBJECT_REF,
    )
    with pytest.raises(
        ValueError,
        match="no pre-certified identity is newly sealed",
    ):
        _activate(pending=pending)


def test_multi_pending_ledger_activates_only_rows_actually_sealed():
    ledger = {
        "project_id": "au_qld_lot16_power",
        "source_sha256": SOURCE_SHA,
        "status": "PENDING_IDENTITIES_READY_QUANTITIES_UNSEALED",
        "pending_identities": [
            {
                "physical_opening_id": PHYSICAL,
                "benchmark_item_id": ITEM,
                "benchmark_object_ref": OBJECT_REF,
                "status": "IDENTITY_READY_QUANTITY_UNSEALED",
            },
            {
                "physical_opening_id": (
                    "physical_opening_existence_future"
                ),
                "benchmark_item_id": (
                    "lot16-internal-access-0870-laundry-area"
                ),
                "benchmark_object_ref": (
                    "lot16:opening:p3:internal_access:0870_laundry"
                ),
                "status": "IDENTITY_READY_QUANTITY_UNSEALED",
            },
        ],
    }
    output, receipt = _activate(pending=ledger)
    assert receipt["activated_count"] == 1
    assert len(output["bindings"]) == 1
    assert output["bindings"][0]["benchmark_item_id"] == ITEM


def test_pending_item_must_be_frozen_denominator_item():
    pending = _pending(item="made-up-item")
    with pytest.raises(
        ValueError,
        match="not denominator eligible",
    ):
        _activate(pending=pending)


def test_pending_item_must_retain_exact_frozen_object_relationship():
    pending = _pending(
        object_ref=(
            "lot16:opening:p3:internal_access:0870_laundry"
        )
    )
    with pytest.raises(
        ValueError,
        match="not frozen-authorized",
    ):
        _activate(pending=pending)



def test_sealed_quantity_unit_must_match_frozen_item_unit():
    manifest = _manifest()
    target = next(
        item
        for item in manifest["verified_takeoff_items"]
        if item["item_id"] == ITEM
    )
    target["unit"] = "ea"
    with pytest.raises(
        ValueError,
        match="unit does not match frozen item",
    ):
        _activate(manifest=manifest)


def test_foreign_manifest_source_envelope_fails_closed():
    manifest = _manifest()
    for row in manifest["source_documents"]:
        if row.get("sha256") == SOURCE_SHA:
            row["sha256"] = "f" * 64
    with pytest.raises(
        ValueError,
        match="does not cover sealed source envelope",
    ):
        _activate(manifest=manifest)


def test_malformed_pending_identity_fails_closed():
    ledger = _pending()
    ledger["physical_opening_id"] = True
    with pytest.raises(ValueError):
        _activate(pending=ledger)
