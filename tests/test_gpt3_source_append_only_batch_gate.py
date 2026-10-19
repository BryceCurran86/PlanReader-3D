"""GPT3 append-only signed V1/customer admission is not a benchmark score."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from pb_customer_output_verification import CustomerOutputVerificationError
from pb_quantity_takeoff_adapter import quantities_to_takeoff_output_rows
from pb_source_closed_run_export import (
    seal_source_closed_run, sealed_source_closed_run_from_dict,
)
from test_customer_output_verification import quantity, trace, authority
from tools import gpt3_source_append_only_batch_gate as gate


def _fixture(*, extra=True, change=None, duplicate_area=False,
             new_abstained=False, revision_changed=False):
    first = quantity("original", "physical-room-1")
    added = quantity(
        "new", "physical-room-2",
        value=None if new_abstained else 7.5, abstained=new_abstained,
    )
    if change == "amount":
        first_new = replace(first, value=99.0)
    elif change == "evidence":
        first_new = replace(first, evidence_ids=("replacement-evidence",))
    else:
        first_new = first
    if revision_changed:
        added = replace(added, metadata={
            **added.metadata, "revision_id": "rev-next",
        })
    if duplicate_area:
        a = replace(added, family="opening_area", semantic_key="door_area:first",
                    input_entity_ids=("shared-opening",))
        b = replace(
            added, quantity_id="another-area", evidence_ids=("ev-another-area",),
            family="opening_area", semantic_key="window_area:second",
            input_entity_ids=("shared-opening",),
        )
        added_rows = (a, b)
    else:
        added_rows = (added,) if extra else ()
    old_run = _sealed(first)
    newer = (first_new, *added_rows)
    new_run = _sealed(*newer)
    return (
        old_run, new_run,
        _customers(first),
        _customers(*newer),
    )


def _sealed(*quantities):
    traces = {q.quantity_id: trace(q) for q in quantities}
    return seal_source_closed_run(
        quantities, project_id="project-7",
        traces_by_quantity_id=traces,
    )


def _customers(*quantities):
    traces = {q.quantity_id: trace(q) for q in quantities}
    return quantities_to_takeoff_output_rows(
        quantities,
        traces_by_quantity_id=traces,
        authorities_by_quantity_id={
            q.quantity_id: authority() for q in quantities if not q.abstained
        },
    )


def _check(batch):
    old, new, old_rows, new_rows = batch
    return gate.assess_append_only_signed_batch(
        old, new, baseline_customers=old_rows, candidate_customers=new_rows,
    )


def test_new_genuine_signed_customer_batch_only_allows_independent_review():
    result = _check(_fixture())
    assert result["admission_status"] == "READY_FOR_INDEPENDENT_IDENTITY_REVIEW"
    assert result["retained_quantity_ids"] == ["original"]
    assert result["added_quantity_ids"] == ["new"]
    assert result["baseline_customer_verified_count"] == 1
    assert result["candidate_customer_verified_count"] == 2
    assert result["source_authenticated"] is False
    assert result["independent_benchmark_identity_verified"] is False
    assert result["official_v2_accuracy"] is None
    assert not result["customer_approval_granted"]


@pytest.mark.parametrize(("change", "gate_name"), [
    ("amount", "PREVIOUSLY_SIGNED_PHYSICAL_QUANTITY_CHANGED"),
    ("evidence", "PREVIOUSLY_SIGNED_SOURCE_RECEIPT_CHANGED"),
])
def test_predecessor_quantity_id_does_not_hide_changed_body(change, gate_name):
    report = _check(_fixture(change=change))
    assert report["first_failing_gate"] == gate_name
    assert report["admission_status"] == "BLOCKED"
    assert report["retained_quantity_ids"] == []


def test_zero_append_is_not_reported_as_score_gain():
    r = _check(_fixture(extra=False))
    assert r["first_failing_gate"] == "NO_NEW_SIGNED_QUANTITIES"
    assert r["added_quantity_ids"] == []
    assert r["retained_quantity_ids"] == ["original"]


def test_deleted_predecessor_cannot_be_replaced_by_same_quantity_value():
    original = quantity("original", "physical-room-1")
    replacement = quantity("replacement", "physical-room-1")
    report = _check((
        _sealed(original), _sealed(replacement),
        _customers(original), _customers(replacement),
    ))
    assert report["first_failing_gate"] == "PREVIOUSLY_SIGNED_QUANTITY_REMOVED"
    assert report["removed_quantity_ids"] == ["original"]


def test_same_family_claiming_same_opening_twice_cannot_append():
    report = _check(_fixture(duplicate_area=True))
    assert report["first_failing_gate"] == "DUPLICATE_OPENING_AREA_PHYSICAL_IDENTITY"


def test_abstention_is_not_a_new_firm_customer_approved_quantity():
    report = _check(_fixture(new_abstained=True))
    assert report["first_failing_gate"] == "NEW_QUANTITY_NOT_FIRM_SOURCE_CLOSED"
    assert report["candidate_customer_verified_count"] == 1


def test_new_source_revision_requires_new_epoch_review():
    report = _check(_fixture(revision_changed=True))
    assert report["first_failing_gate"] == "SOURCE_REVISION_EPOCH_CHANGED"


def test_unverified_new_customer_receipt_is_not_approved():
    old, new, old_rows, new_rows = _fixture()
    with pytest.raises(CustomerOutputVerificationError, match="missing customer"):
        gate.assess_append_only_signed_batch(
            old, new, baseline_customers=old_rows,
            candidate_customers=new_rows[:-1],
        )


def test_duplicated_customer_rows_cannot_be_accepted_as_manual_or_new():
    old, new, old_rows, new_rows = _fixture()
    with pytest.raises(CustomerOutputVerificationError, match="duplicate customer"):
        gate.assess_append_only_signed_batch(
            old, new, baseline_customers=old_rows,
            candidate_customers=[*new_rows, new_rows[1]],
        )


def test_public_original_eight_is_verified_but_not_ninth():
    root = Path(__file__).resolve().parents[1]
    base = root / "docs/engineering/lot16_original_signed_eight_row_20261015/production"
    sealed = sealed_source_closed_run_from_dict(
        json.loads((base / "source_sealed_run.json").read_text(encoding="utf-8"))
    )
    customers = json.loads(
        (base / "verified_customer_rows.json").read_text(encoding="utf-8")
    )
    report = gate.assess_append_only_signed_batch(
        sealed, sealed, baseline_customers=customers,
        candidate_customers=customers,
    )
    assert report["baseline_quantity_count"] == 8
    assert report["retained_quantity_ids"] and len(report["retained_quantity_ids"]) == 8
    assert report["first_failing_gate"] == "NO_NEW_SIGNED_QUANTITIES"
    assert report["admission_status"] == "BLOCKED"


def test_source_customer_cli_is_create_only_and_reports_unpublished(tmp_path):
    old, new, old_rows, new_rows = _fixture()
    paths = [tmp_path / name for name in (
        "baseline.json", "candidate.json", "old_customer.json",
        "new_customer.json",
    )]
    for path, value in zip(
        paths, (old.to_dict(), new.to_dict(), old_rows, new_rows),
    ):
        path.write_text(json.dumps(value), encoding="utf-8")
    target = tmp_path / "admission.json"
    args = [
        "--baseline-sealed", str(paths[0]),
        "--candidate-sealed", str(paths[1]),
        "--baseline-customer", str(paths[2]),
        "--candidate-customer", str(paths[3]),
        "--output", str(target),
    ]
    assert gate.main(args) == 0
    report = json.loads(target.read_text(encoding="utf-8"))
    assert report["publication_status"] == "UNPUBLISHED"
    assert report["admission_status"] == "READY_FOR_INDEPENDENT_IDENTITY_REVIEW"
    assert report["official_v2_accuracy"] is None
    with pytest.raises(FileExistsError):
        gate.main(args)
    for protected in paths:
        args[-1] = str(protected)
        with pytest.raises(ValueError, match="protected evidence"):
            gate.main(args)


def test_changing_source_customer_files_during_read_blocks_receipt(
    tmp_path, monkeypatch,
):
    old, new, old_rows, new_rows = _fixture()
    paths = [tmp_path / name for name in ("old.json", "new.json", "c1.json", "c2.json")]
    for path, value in zip(paths, (old.to_dict(), new.to_dict(), old_rows, new_rows)):
        path.write_text(json.dumps(value), encoding="utf-8")
    original = gate.assess_append_only_signed_batch

    def changed_source(*args, **kwargs):
        result = original(*args, **kwargs)
        paths[1].write_text('{"tampered":true}', encoding="utf-8")
        return result

    monkeypatch.setattr(gate, "assess_append_only_signed_batch", changed_source)
    with pytest.raises(ValueError, match="changed during batch gate"):
        gate.build_append_only_report(
            baseline_sealed=paths[0], candidate_sealed=paths[1],
            baseline_customer=paths[2], candidate_customer=paths[3],
        )
