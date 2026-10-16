"""The committed ORIGINAL eight-row Lot16 signed output must stay byte-exact, cryptographically valid and bijective.

The fixture under ``docs/engineering/lot16_original_signed_eight_row_20261015`` is the signed output of the source-positive
GitHub run 38636511093 (producer head ``4e5aedf0``).  It is production output of the original PDF, not benchmark truth; the
identity map beside it is the benchmark-side binding produced by GPT3 and is only read by the development checkpoint.
These tests guard against signed-customer output drift, a re-keyed or re-signed eighth quantity, and a silently edited fixture.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from pb_customer_output_verification import CustomerOutputVerificationError, verify_sealed_customer_output
from pb_source_closed_run_export import sealed_source_closed_run_from_dict

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "docs" / "engineering" / "lot16_original_signed_eight_row_20261015"
FINGERPRINT = "ef58f8ae1a963a5b985edfa6dda752f3f338d9d5c42d56969b0e86f538aadfeb"
PRODUCER_HEAD = "4e5aedf085cf63f92dac0935132b1e1c1dbaa178"
SIGNED_AREAS_M2 = (0.54, 0.9, 1.26, 1.8, 1.8, 2.16, 2.16, 10.08)


def _load(name: str):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


def _sealed():
    return sealed_source_closed_run_from_dict(_load("production/source_sealed_run.json"))


def test_every_fixture_file_matches_its_pinned_sha256():
    lines = [line for line in (FIXTURE / "SHA256SUMS").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 5
    for line in lines:
        digest, _, name = line.partition(" *")
        data = (FIXTURE / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest, name


def test_producer_head_is_the_documented_source_positive_run():
    assert (FIXTURE / "producer_head_sha.txt").read_text(encoding="utf-8").strip() == PRODUCER_HEAD


def test_sealed_run_fingerprint_and_quantity_count_are_the_signed_eight():
    sealed = _sealed()
    assert sealed.fingerprint == FINGERPRINT
    assert sealed.project_id == "au_qld_lot16_power"
    assert len(sealed.quantities) == 8
    assert sorted(round(float(q.value), 2) for q in sealed.quantities) == sorted(SIGNED_AREAS_M2)


def test_customer_rows_verify_against_the_seal_one_to_one():
    sealed = _sealed()
    customers = _load("production/verified_customer_rows.json")
    verification = verify_sealed_customer_output(sealed, customers)
    assert len(customers) == len(sealed.quantities) == verification.valid_quantity_count == 8
    assert len(verification.verified_quantity_ids) == 8
    assert sorted(verification.verified_quantity_ids) == sorted(q.quantity_id for q in sealed.quantities)


def test_an_edited_number_in_one_customer_row_is_rejected():
    sealed = _sealed()
    customers = _load("production/verified_customer_rows.json")
    text = json.dumps(customers)
    assert "10.08" in text  # the largest signed opening area
    edited = json.loads(text.replace("10.08", "10.09", 1))
    assert edited != customers
    with pytest.raises(CustomerOutputVerificationError, match="mismatch"):
        verify_sealed_customer_output(sealed, edited)


def test_a_missing_customer_row_is_rejected():
    sealed = _sealed()
    customers = _load("production/verified_customer_rows.json")
    with pytest.raises(CustomerOutputVerificationError, match="missing customer rows"):
        verify_sealed_customer_output(sealed, customers[:-1])


def test_identity_map_and_report_bind_exactly_the_same_eight():
    sealed = _sealed()
    identity = _load("identity_map_with_1215.json")
    report = _load("exact_project_report.json")
    assert len(identity["bindings"]) == 8
    assert sealed.project_id == identity["project_id"] == report["project_id"] == "au_qld_lot16_power"
    assert report["sealed_run_fingerprint"] == sealed.fingerprint
    assert report["source_sha_verified"] and report["reconciliation_complete"]
    assert report["denominator"] == 27 and report["matched_within_tolerance"] == 8
    assert report["lineage_conflicts"] == report["unsupported_extra"] == 0

def test_identity_bindings_cover_every_signed_physical_object_exactly_once():
    """Prevent an eight-row benchmark map with a reused or omitted physical source."""
    sealed = _sealed()
    identity = _load("identity_map_with_1215.json")
    bindings = identity["bindings"]
    signed_keys = {
        (row.family, tuple(row.object_identity_refs))
        for row in sealed.quantities
    }
    binding_keys = [
        (row["production_family"], tuple(row["production_object_identity_refs"]))
        for row in bindings
    ]
    assert len(signed_keys) == len(binding_keys) == 8
    assert len(set(binding_keys)) == 8
    assert set(binding_keys) == signed_keys
    assert len({row["benchmark_item_id"] for row in bindings}) == 8
    report = _load("exact_project_report.json")
    produced = report["produced_items"]
    assert len(produced) == 8
    assert {row["quantity_id"] for row in produced} == {
        row.quantity_id for row in sealed.quantities
    }


def test_customer_projection_retains_source_roots_and_review_only_status():
    """Signed source evidence may be verified without becoming commercial approval."""
    sealed = _sealed()
    customers = _load("production/verified_customer_rows.json")
    by_id = {row.quantity_id: row for row in sealed.quantities}
    assert len(by_id) == len(customers) == 8
    for customer in customers:
        original = by_id[customer["quantity_id"]]
        assert customer["quantity"] == original.value
        assert customer["unit"] == original.unit
        assert customer["canonical_entity_ids"] == list(original.object_identity_refs)
        assert customer["source_sha256"] == original.source_sha256
        assert customer["revision_id"] == original.revision_id
        assert customer["document_id"] == original.document_id
        assert customer["viewport_id"] == original.viewport_id
        assert customer["source_page"] == original.source_page
        assert customer["project_id"] == original.project_id
        assert customer["inclusion_status"] == "PROVISIONAL"
        assert customer["quantity_status"] == "To review"
