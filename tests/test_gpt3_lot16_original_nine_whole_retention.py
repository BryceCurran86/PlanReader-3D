"""Owner-original Lot16 source replay acceptance; NOT a benchmark predictor.

The frozen 8-row evidence is read ONLY after independently executing the
producer twice against the SHA-attested original PDF. Public CI without that
private PDF SKIPS rather than pretending that original validation passed.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from pb_customer_output_verification import verify_sealed_customer_output
from pb_source_closed_run_export import sealed_source_closed_run_from_dict
from tools.run_gpt3_lot16_original_sealed_score_input import (
    _verify_original_source, run_original_lot16_sealed_handoff, MANIFEST,
)

SOURCE = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
ARCHIVE = Path("docs/engineering/lot16_original_signed_eight_row_20261015/production")


def _object(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _unique_quantity_rows(records):
    assert type(records) is list and all(type(row) is dict for row in records)
    identities = [row["quantity_id"] for row in records]
    assert len(identities) == len(set(identities))
    return {row["quantity_id"]: row for row in records}


def _verified_production(directory: Path, source_sha: str):
    raw_seal = _object(directory / "source_sealed_run.json")
    rows = _object(directory / "verified_customer_rows.json")
    sealed = sealed_source_closed_run_from_dict(raw_seal)
    verified = verify_sealed_customer_output(sealed, rows)
    assert sealed.project_id == "au_qld_lot16_power"
    assert list(sealed.source_sha256s) == [source_sha]
    assert verified.valid_quantity_count == len(sealed.quantities) == len(rows)
    return _unique_quantity_rows(raw_seal["quantities"]), _unique_quantity_rows(rows)


def test_owner_original_lot16_nine_seals_and_preserves_eight_whole_customer_bodies(tmp_path):
    if not SOURCE.is_file():
        pytest.skip("PRIVATE ORIGINAL LOT16 PDF NOT PROVISIONED: nine-row source-positive release remains UNVERIFIED")
    original_sha = _verify_original_source(SOURCE, MANIFEST)
    source_digest_before = sha256(SOURCE.read_bytes()).hexdigest()
    assert source_digest_before == original_sha

    # IMPORTANT: historical archive is deliberately NOT an input to the producer
    # and is not opened until BOTH original-source production runs finish.
    old_dir = tmp_path / "original-default-eight"
    new_dir = tmp_path / "original-source-reproved-nine"
    old_receipt = run_original_lot16_sealed_handoff(SOURCE, old_dir)
    new_receipt = run_original_lot16_sealed_handoff(
        SOURCE, new_dir, recover_additional_opening_areas=True,
    )
    assert sha256(SOURCE.read_bytes()).hexdigest() == source_digest_before

    old_signed, old_customer = _verified_production(old_dir, original_sha)
    new_signed, new_customer = _verified_production(new_dir, original_sha)
    # These quantities are a RELEASE-ACCEPTANCE expectation of already produced
    # evidence, not a target passed to any detector, measurement, or producer.
    assert old_receipt["quantity_count"] == len(old_signed) == len(old_customer) == 8
    assert new_receipt["quantity_count"] == len(new_signed) == len(new_customer) == 9

    # Read-only original producer fixture is compared strictly POST production.
    # Authenticate archived producer receipts against the immutable, checked-in
    # SHA256SUMS before using them as a POST-production retention oracle.
    digest_lines = (ARCHIVE.parent / "SHA256SUMS").read_text(encoding="ascii").splitlines()
    digest_map = {}
    for line in digest_lines:
        digest, relative = line.split(" *", 1)
        assert relative not in digest_map and len(digest) == 64
        digest_map[relative] = digest
    for relative in ("production/source_sealed_run.json",
                     "production/verified_customer_rows.json"):
        assert sha256((ARCHIVE.parent / relative).read_bytes()).hexdigest() == digest_map[relative]
    baseline_signed = _unique_quantity_rows(_object(ARCHIVE / "source_sealed_run.json")["quantities"])
    baseline_customer = _unique_quantity_rows(_object(ARCHIVE / "verified_customer_rows.json"))
    assert len(baseline_signed) == len(baseline_customer) == 8
    assert old_signed == baseline_signed
    assert old_customer == baseline_customer
    for identity in baseline_signed:
        assert new_signed[identity] == baseline_signed[identity]
        assert new_customer[identity] == baseline_customer[identity]

    additional_ids = set(new_signed) - set(baseline_signed)
    assert len(additional_ids) == 1
    assert set(new_customer) == set(new_signed)
    new_record = new_signed[next(iter(additional_ids))]
    assert new_record["family"] == "opening_area"
    assert new_record["lineage_ok"] is True and new_record["abstained"] is False

    # No old/new alias is allowed to reissue a physical opening under a fresh ID.
    physical_keys = [
        (record["family"], tuple(sorted(record["object_identity_refs"])))
        for record in new_signed.values()
    ]
    assert len(set(physical_keys)) == 9
    assert all(key[1] for key in physical_keys)

    # The two producer scopes remain separate in the original source witness;
    # the signed V1 envelopes never invent or relabel source snapshots.
    physical_sources = _object(new_dir / "source_production_openings.json")
    physical_by_id = {
        opening["physical_opening_id"]: opening
        for opening in physical_sources
        if opening.get("physical_opening_id")
    }
    signed_physical = {
        row["object_identity_refs"][0]: row
        for row in new_signed.values()
    }
    assert set(signed_physical) <= set(physical_by_id)
    old_scopes = {
        physical_by_id[baseline_signed[qid]["object_identity_refs"][0]]["snapshot_id"]
        for qid in baseline_signed
    }
    new_scope = physical_by_id[new_record["object_identity_refs"][0]]["snapshot_id"]
    assert len(old_scopes) == 1 and new_scope not in old_scopes

    # A verified production receipt is not itself a frozen V2 scoring grant.
    for receipt in (old_receipt, new_receipt):
        assert receipt["signed_run_and_customer_parity"] is True
        assert receipt["benchmark_score_granted"] is False
        assert receipt["benchmark_accuracy"] is None
