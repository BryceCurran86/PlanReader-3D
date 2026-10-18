"""Original V1 source-only snapshot comparison is a reporting hold, never a score."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from pb_source_closed_run_export import sealed_source_closed_run_from_dict
from tools import diag_gpt3_original_v1_source_only_transition as diag


ROOT = Path(__file__).resolve().parents[1]
HIST = ROOT / "docs/engineering/lot16_original_signed_eight_row_20261015/production/source_sealed_run.json"
FRESH = ROOT / "docs/engineering/four_job_runs/20261016_47c8031a/au_qld_lot16_power/outputs/au_qld_lot16_power.json"


def _runs():
    return json.loads(HIST.read_text()), json.loads(FRESH.read_text())


def test_real_signed_lot16_original_snapshots_rekey_all_eight_without_source_attestation():
    historical, candidate = _runs()
    old = sealed_source_closed_run_from_dict(historical)
    fresh = sealed_source_closed_run_from_dict(candidate)
    report = diag.inspect_signed_source_only_v1_transition(
        archived_run=historical, candidate_run=candidate,
    )
    assert report["historical_run_fingerprint"] == old.fingerprint
    assert report["candidate_run_fingerprint"] == fresh.fingerprint
    assert report["signed_v1_fingerprints_verified"] is True
    assert report["project_id"] == "au_qld_lot16_power"
    assert report["historical_quantity_count"] == report["candidate_quantity_count"] == 8
    assert report["shared_quantity_id_count"] == 8
    assert report["same_quantity_id_universe"] is True
    assert report["shared_receipt_status_counts"] == {
        "SNAPSHOT_RECEIPT_REKEY_UNATTESTED": 8
    }
    assert report["all_shared_fingerprints_byte_exact"] is False
    assert report["first_failing_authority_stage"] == "original_producer_signed_receipts_rekeyed"
    assert report["historical_values"] == report["candidate_values"]
    assert report["official_four_project_accuracy"] is None
    assert report["producer_signed_decision_scope_verified"] is False
    assert report["cross_snapshot_customer_reuse_authorized"] is False
    assert report["official_score_publication_authorized"] is False
    assert report["new_firm_quantities_authorized"] == 0


def test_same_original_v1_run_still_cannot_certify_future_snapshot_or_customer_scope():
    original, _ = _runs()
    report = diag.inspect_signed_source_only_v1_transition(
        archived_run=original, candidate_run=original,
    )
    assert report["all_shared_fingerprints_byte_exact"] is True
    assert report["first_failing_authority_stage"] == "independent_original_decision_scope_issuer_not_attested"
    assert report["archived_customer_bijection_verified"] is False
    assert report["candidate_customer_bijection_verified"] is False
    assert report["official_score_publication_authorized"] is False


def test_equal_measured_value_with_different_physical_id_is_missing_plus_new_never_same():
    original, _ = _runs()
    source = sealed_source_closed_run_from_dict(original)
    a = source.quantities[0]
    b = replace(a, quantity_id="another-physical-source-id")
    # Internal classifier receives verified records in production. Here a
    # synthetic rekey tests identity rules without creating a V1 seal.
    result = diag._diff({a.quantity_id: a}, {b.quantity_id: b})
    assert result["shared_quantity_id_count"] == 0
    assert [x["quantity_id"] for x in result["missing_historical_quantities"]] == [a.quantity_id]
    assert [x["quantity_id"] for x in result["new_candidate_quantities"]] == [b.quantity_id]
    assert result["missing_historical_quantities"][0]["value"] == result["new_candidate_quantities"][0]["value"]
    assert result["historical_to_candidate_quantity_equivalence_proven"] is False


def test_same_id_changed_physical_semantic_identity_is_proposition_conflict():
    original, _ = _runs()
    a = sealed_source_closed_run_from_dict(original).quantities[0]
    b = replace(a, semantic_key="door_area:different_source_identity")
    result = diag._diff({a.quantity_id: a}, {b.quantity_id: b})
    assert result["shared_receipt_status_counts"] == {"HISTORICAL_PROPOSITION_CONFLICT": 1}
    assert result["shared_quantity_differences"][0]["issuer_attestation_required"]


def test_mutated_archived_v1_signed_quantity_fingerprint_rejected_before_drift():
    historical, candidate = _runs()
    historical["quantities"][0]["value"] += 0.01
    with pytest.raises(Exception):
        diag.inspect_signed_source_only_v1_transition(
            archived_run=historical, candidate_run=candidate,
        )


def test_source_only_cli_exits_unpublished_and_output_is_nonreplaceable(tmp_path):
    destination = tmp_path / "new-diagnostic.json"
    args = [
        "--historical-v1", str(HIST), "--candidate-v1", str(FRESH),
        "--output", str(destination),
    ]
    assert diag.main(args) == 2
    report = json.loads(destination.read_text())
    assert report["release_status"] == "SOURCE_ONLY_SNAPSHOT_IDENTITY_HOLD"
    assert report["signed_v1_fingerprints_verified"]
    assert report["historical_to_candidate_quantity_equivalence_proven"] is False
    assert report["official_four_project_accuracy"] is None
    before = destination.read_bytes()
    with pytest.raises(FileExistsError, match="new path"):
        diag.main(args)
    assert destination.read_bytes() == before


def test_source_only_cli_refuses_source_alias_and_existing_customer_file_before_io(
    tmp_path, monkeypatch,
):
    path = tmp_path / "customer.json"
    path.write_text('{"customer":"immutable"}')
    monkeypatch.setattr(
        diag, "_json_object",
        lambda _: (_ for _ in ()).throw(AssertionError("private signed run must not be read")),
    )
    with pytest.raises(FileExistsError, match="new path"):
        diag.main([
            "--historical-v1", str(HIST),
            "--candidate-v1", str(FRESH),
            "--output", str(path),
        ])
    assert path.read_text() == '{"customer":"immutable"}'
    with pytest.raises(ValueError, match="protected evidence"):
        diag.main([
            "--historical-v1", str(HIST),
            "--candidate-v1", str(FRESH),
            "--output", str(HIST),
        ])


def test_source_only_real_signed_abstention_does_not_raise_or_become_zero(monkeypatch):
    from pb_source_closed_run_export import seal_source_closed_run
    from test_source_closed_run_export import quantity, trace

    abstained = quantity(
        quantity_id="qty-abstained", value=None,
        input_entity_ids=(), evidence_ids=(),
        abstained=True, blocking_reasons=("source_geometry_open",),
        status="abstained",
    )
    firm = quantity(quantity_id="qty-firm")
    run = seal_source_closed_run(
        [abstained, firm], project_id="project-a",
        traces_by_quantity_id={
            "qty-abstained": trace(evidence_ids=(), canonical_entity_ids=()),
            "qty-firm": trace(),
        },
    )
    monkeypatch.setattr(diag, "_canonical_manifest_for", lambda _: {
        "source_documents": [{"sha256": "a" * 64}],
    })
    report = diag.inspect_signed_source_only_v1_transition(
        archived_run=run.to_dict(), candidate_run=run.to_dict(),
    )
    assert report["historical_quantity_count"] == 2
    assert report["historical_unmeasured_quantity_count"] == 1
    assert report["candidate_unmeasured_quantity_count"] == 1
    assert report["historical_values"] == [13.270425]
    assert report["candidate_values"] == [13.270425]
    assert report["new_firm_quantities_authorized"] == 0
    assert report["official_four_project_accuracy"] is None
