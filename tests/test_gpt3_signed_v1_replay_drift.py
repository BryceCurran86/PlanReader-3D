"""Independent synthetic negatives and original-V1 positive replay receipts.

The mock mutations exercise a read-only comparison of dataclasses; they do not
create/source-authenticate any quantity or modify a signed V1 fixture.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json

import pytest

from pb_source_closed_run_export import sealed_source_closed_run_from_dict
from pb_customer_output_verification import verify_sealed_customer_output
from tools import gpt3_signed_v1_replay_drift as drift
from tests.symlink_test_support import symlink_or_skip


_ROOT = Path(__file__).resolve().parents[1]
_OLD = _ROOT / "docs/engineering/lot16_original_signed_eight_row_20261015/production"
_NEW = (
    _ROOT / "docs/engineering/four_job_runs/20261016_47c8031a"
    / "au_qld_lot16_power/outputs"
)


def _fixtures():
    old_dict = json.loads((_OLD / "source_sealed_run.json").read_text(encoding="utf-8"))
    new_dict = json.loads((_NEW / "au_qld_lot16_power.json").read_text(encoding="utf-8"))
    customers = json.loads((_OLD / "verified_customer_rows.json").read_text(encoding="utf-8"))
    return old_dict, new_dict, customers


def test_actual_original_v1_replay_never_grants_customer_reuse_or_new_firm_output():
    old, fresh, customers = _fixtures()
    result = drift.inspect_signed_v1_replay(
        archived_run=old, candidate_run=fresh, archived_customer_rows=customers,
    )
    assert result["project_id"] == "au_qld_lot16_power"
    assert result["historical_quantity_count"] == 8
    assert result["candidate_quantity_count"] == 8
    assert result["receipt_status_counts"] == {
        "SNAPSHOT_RECEIPT_REKEY_UNATTESTED": 8
    }
    assert result["archived_customer_verified"] is True
    assert result["candidate_customer_verified"] is False
    assert result["source_issuer_scope_attestation_proven"] is False
    assert result["safe_to_reuse_archived_customers_with_candidate"] is False
    assert result["new_firm_quantities_authorized"] == 0
    assert result["historical_v1_byte_exact"] is False
    assert result["original_source_package_complete_in_both_seals"] is False
    assert result["official_four_project_coverage_accuracy"] is None
    assert all(row["issuer_attestation_required"] for row in result["quantity_differences"])


def test_archived_source_customer_projection_only_verifies_against_its_exact_seal():
    archived, fresh, customer_rows = _fixtures()
    old = sealed_source_closed_run_from_dict(archived)
    newer = sealed_source_closed_run_from_dict(fresh)
    assert verify_sealed_customer_output(old, customer_rows).customer_row_count == 8
    with pytest.raises(Exception):
        verify_sealed_customer_output(newer, customer_rows)


def test_reused_archived_customers_as_new_snapshot_are_rejected_by_real_verifier():
    old, fresh, customers = _fixtures()
    with pytest.raises(Exception):
        drift.inspect_signed_v1_replay(
            archived_run=old, candidate_run=fresh,
            archived_customer_rows=customers, candidate_customer_rows=customers,
        )


def test_exact_same_signed_v1_run_still_not_an_issuer_attestation():
    archived, _, customers = _fixtures()
    result = drift.inspect_signed_v1_replay(
        archived_run=archived, candidate_run=archived,
        archived_customer_rows=customers, candidate_customer_rows=customers,
    )
    assert result["receipt_status_counts"] == {"EXACT_HISTORICAL_V1_PRESERVED": 8}
    assert result["historical_v1_byte_exact"] is True
    assert result["candidate_customer_verified"] is True
    assert result["safe_to_reuse_archived_customers_with_candidate"] is False
    assert result["source_issuer_scope_attestation_proven"] is False
    assert result["new_firm_quantities_authorized"] == 0


def _different_of_same_type(value):
    if type(value) is bool:
        return not value
    if type(value) in (int, float):
        return value + 1
    if type(value) is str:
        return value + "-different"
    if type(value) is list:
        return value + ["synthetic-conflicting-source-identity"]
    raise TypeError(type(value))


@pytest.mark.parametrize("field", drift.IMMUTABLE_V1_FIELDS)
def test_each_of_21_signed_proposition_fields_independently_blocks_drift(field):
    archived, _, _ = _fixtures()
    source = sealed_source_closed_run_from_dict(archived).quantities[0]
    changed_payload = source.payload()
    changed_payload[field] = _different_of_same_type(changed_payload[field])
    altered = replace(source, **{
        field: tuple(changed_payload[field])
        if type(changed_payload[field]) is list else changed_payload[field]
    })
    got = drift._compare_historical_quantity(source, altered)
    assert got["status"] == "HISTORICAL_PROPOSITION_CONFLICT"
    assert got["changed_fields"] == [field]
    assert got["issuer_attestation_required"] is True


@pytest.mark.parametrize("kind", ["source-observation-added", "evidence-removed", "duplicate-host"])
def test_host_frame_whitelist_cannot_hide_nonissuer_evidence_edits(kind):
    archived, newer, _ = _fixtures()
    old = sealed_source_closed_run_from_dict(archived).quantities[0]
    new_by_id = {
        item.quantity_id: item
        for item in sealed_source_closed_run_from_dict(newer).quantities
    }
    real = new_by_id[old.quantity_id]
    ids = list(real.evidence_ids)
    if kind == "source-observation-added":
        ids.append("source_observation_synthetic_nonissuer_receipt")
    elif kind == "evidence-removed":
        ids = [x for x in ids if not x.startswith("source_observation_")]
    else:
        ids.append("opening_host_binding_v3_deadbeefdeadbeefdeadbeefdeadbeef")
    variant = replace(real, evidence_ids=tuple(ids))
    got = drift._compare_historical_quantity(old, variant)
    assert got["status"] == "UNSUPPORTED_SOURCE_RECEIPT_DRIFT"


def test_unsealed_original_row_mutation_is_rejected_before_replay_comparison():
    archived, fresh, customers = _fixtures()
    fresh["quantities"][0]["value"] += 1
    with pytest.raises(Exception):
        drift.inspect_signed_v1_replay(
            archived_run=archived, candidate_run=fresh,
            archived_customer_rows=customers,
        )


def test_changed_source_sha_in_unsigned_envelope_is_rejected():
    archived, fresh, customers = _fixtures()
    fresh["source_sha256s"][0] = "0" * 64
    with pytest.raises(Exception):
        drift.inspect_signed_v1_replay(
            archived_run=archived, candidate_run=fresh,
            archived_customer_rows=customers,
        )


def test_untrusted_foreign_or_malformed_archived_customer_is_rejected():
    archived, fresh, customers = _fixtures()
    customers[0]["quantity_id"] = "not-a-real-archived-id"
    with pytest.raises(Exception):
        drift.inspect_signed_v1_replay(
            archived_run=archived, candidate_run=fresh,
            archived_customer_rows=customers,
        )


def test_cli_does_not_overwrite_historical_run_and_never_exits_as_published(tmp_path):
    outfile = tmp_path / "v1-replay.json"
    rc = drift.main([
        "--archived-v1", str(_OLD / "source_sealed_run.json"),
        "--candidate-v1", str(_NEW / "au_qld_lot16_power.json"),
        "--archived-customers", str(_OLD / "verified_customer_rows.json"),
        "--output", str(outfile),
    ])
    assert rc == 2
    content = json.loads(outfile.read_text(encoding="utf-8"))
    assert content["publication_status"] == "DIAGNOSTIC_UNPUBLISHED"
    assert content["receipt_status_counts"]["SNAPSHOT_RECEIPT_REKEY_UNATTESTED"] == 8
    with pytest.raises(ValueError, match="may not overwrite"):
        drift.main([
            "--archived-v1", str(_OLD / "source_sealed_run.json"),
            "--candidate-v1", str(_NEW / "au_qld_lot16_power.json"),
            "--archived-customers", str(_OLD / "verified_customer_rows.json"),
            "--output", str(_OLD / "source_sealed_run.json"),
        ])


def _historical_cli_args(output):
    return [
        "--archived-v1", str(_OLD / "source_sealed_run.json"),
        "--candidate-v1", str(_NEW / "au_qld_lot16_power.json"),
        "--archived-customers", str(_OLD / "verified_customer_rows.json"),
        "--output", str(output),
    ]


def test_v1_replay_cli_permits_own_output_beside_archived_inputs(tmp_path, monkeypatch):
    # Keep the real archive intact while exercising same-parent behaviour.
    original = tmp_path / "archived.json"
    candidate = tmp_path / "candidate.json"
    customers = tmp_path / "customers.json"
    original.write_bytes((_OLD / "source_sealed_run.json").read_bytes())
    candidate.write_bytes((_NEW / "au_qld_lot16_power.json").read_bytes())
    customers.write_bytes((_OLD / "verified_customer_rows.json").read_bytes())
    args = [
        "--archived-v1", str(original),
        "--candidate-v1", str(candidate),
        "--archived-customers", str(customers),
        "--output", str(tmp_path / "audit.json"),
    ]
    assert drift.main(args) == 2
    first = (tmp_path / "audit.json").read_bytes()
    assert drift.main(args) == 2
    assert (tmp_path / "audit.json").read_bytes() == first
    assert original.read_bytes() == (_OLD / "source_sealed_run.json").read_bytes()


def test_v1_replay_cli_rejects_unrelated_json_binary_and_output_symlink(tmp_path):
    for filename, before in (
        ("customer.json", b'{"quantity_id":"preserve"}\n'),
        ("signed.bin", b"source-v1-signed-evidence"),
    ):
        path = tmp_path / filename
        path.write_bytes(before)
        with pytest.raises(ValueError, match="cannot overwrite unrelated evidence"):
            drift.main(_historical_cli_args(path))
        assert path.read_bytes() == before
    original = tmp_path / "source.json"
    original.write_text("DO NOT MUTATE", encoding="utf-8")
    alias = tmp_path / "alias.json"
    symlink_or_skip(alias, original)
    with pytest.raises(ValueError, match="cannot follow an output symlink"):
        drift.main(_historical_cli_args(alias))
    assert original.read_text(encoding="utf-8") == "DO NOT MUTATE"
