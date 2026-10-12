"""Fail-closed Lot16 verified-seal inventory must never mint benchmark identity."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace as N

import pytest

from tools.diag_gpt3_lot16_unmapped_produced_items import (
    build_unmapped_inventory, PROJECT,
)

SHA = "a" * 64
PHYSICAL = "physical_opening_existence_" + "b" * 32
QID = "opening_area_" + "c" * 32


def _inputs():
    q = N(
        quantity_id=QID, project_id=PROJECT, source_sha256=SHA,
        family="opening_area", source_page="3", unit="m2", value=2.16,
        abstained=False, lineage_ok=True, status="corroborated",
        object_identity_refs=(PHYSICAL,), evidence_ids=("source_observation_1",),
        fingerprint="d" * 64,
        authority="producer_source_figured_dimension",
    )
    seal = N(
        project_id=PROJECT, source_sha256s=(SHA,), run_id="source_run_1",
        fingerprint="e" * 64, quantities=(q,),
    )
    rows = [{
        "quantity_id": QID, "quantity_family": "opening_area",
        "canonical_entity_ids": [PHYSICAL],
        "source_sha256": SHA, "project_id": PROJECT,
    }]
    verified = N(verified_quantity_ids=(QID,), valid_quantity_count=1)
    receipt = {
        "source_sha256": SHA, "sealed_run_fingerprint": seal.fingerprint,
        "sealed_run_id": seal.run_id, "sealed_quantity_ids": [QID],
        "customer_verified_quantity_ids": [QID],
        "identity_map_status": "INDEPENDENT_ORIGINAL_SOURCE_BINDINGS_REQUIRED",
        "benchmark_accuracy": None, "benchmark_score_granted": False,
        "frozen_v2_reconciliation_complete": False,
    }
    return seal, rows, verified, receipt


def test_producer_source_rows_stay_unmapped_with_one_exact_original_owner():
    a,b,c,d = _inputs()
    output = build_unmapped_inventory(a,b,c,d)
    assert output["verified_quantity_count"] == 1
    assert output["benchmark_accuracy"] is None
    assert output["benchmark_score_granted"] is False
    assert output["object_identity_map_supplied"] is False
    assert output["frozen_v2_reconciliation_complete"] is False
    item, = output["unmapped_produced_items"]
    assert item["quantity_id"] == QID
    assert item["original_physical_object_id"] == PHYSICAL
    assert item["source_quantity_fingerprint"] == "d" * 64
    assert item["frozen_benchmark_object_ref"] is None
    assert item["frozen_match_status"] == "UNRESOLVED"


@pytest.mark.parametrize("damage", [
    "foreign_project", "foreign_sha", "foreign_fingerprint",
    "unverified_readiness", "published_without_identity",
    "duplicate_quantity", "duplicate_physical_object", "duplicate_row",
    "wrong_row_owner", "other_family", "negative_area", "wrong_page",
    "bad_object_ref", "extra_object_ref", "invalid_evidence",
    "tampered_quantity_fingerprint", "abstained", "unproven_lineage",
])
def test_source_binding_damage_never_turns_into_a_benchmark_match(damage):
    seal,rows,verified,receipt = _inputs()
    if damage == "foreign_project":
        seal.project_id = "other"
    elif damage == "foreign_sha":
        seal.source_sha256s = ("f" * 64,)
    elif damage == "foreign_fingerprint":
        receipt["sealed_run_fingerprint"] = "f" * 64
    elif damage == "unverified_readiness":
        receipt["identity_map_status"] = "MAPPED"
    elif damage == "published_without_identity":
        receipt["benchmark_score_granted"] = True
    elif damage == "duplicate_quantity":
        seal.quantities = seal.quantities * 2
    elif damage == "duplicate_physical_object":
        other = deepcopy(seal.quantities[0])
        other.quantity_id = "opening_area_" + "f" * 32
        seal.quantities = (*seal.quantities, other)
        rows.append({**rows[0], "quantity_id": other.quantity_id})
        verified.verified_quantity_ids += (other.quantity_id,)
        verified.valid_quantity_count += 1
        receipt["sealed_quantity_ids"].append(other.quantity_id)
        receipt["customer_verified_quantity_ids"].append(other.quantity_id)
    elif damage == "duplicate_row":
        rows *= 2
    elif damage == "wrong_row_owner":
        rows[0]["canonical_entity_ids"] = ["physical_opening_existence_" + "f" * 32]
    elif damage == "other_family":
        seal.quantities[0].family = "opening_count"
    elif damage == "negative_area":
        seal.quantities[0].value = -2
    elif damage == "wrong_page":
        seal.quantities[0].source_page = "4"
    elif damage == "bad_object_ref":
        seal.quantities[0].object_identity_refs = (None,)
    elif damage == "extra_object_ref":
        seal.quantities[0].object_identity_refs = (PHYSICAL, PHYSICAL)
    elif damage == "invalid_evidence":
        seal.quantities[0].evidence_ids = ()
    elif damage == "tampered_quantity_fingerprint":
        seal.quantities[0].fingerprint = "not-source-fingerprint"
    elif damage == "abstained":
        seal.quantities[0].abstained = True
    else:
        seal.quantities[0].lineage_ok = False
    with pytest.raises(ValueError):
        build_unmapped_inventory(seal,rows,verified,receipt)


def test_unknown_benchmark_values_and_descriptions_are_not_inputs():
    seal,rows,verified,receipt = _inputs()
    rows[0]["element"] = "irrelevant title"
    rows[0]["quantity"] = 10000
    assert build_unmapped_inventory(seal,rows,verified,receipt)[
        "unmapped_produced_items"
    ][0]["frozen_benchmark_object_ref"] is None
