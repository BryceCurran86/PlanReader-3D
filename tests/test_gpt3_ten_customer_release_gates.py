"""Ten GPT3 read-only source/customer publication readiness gates.

No Full Plan V2 gold, actual original PDF, geometry or production publisher
is consumed by this test. The archived Lot16 V1 and customer rows are
immutable regression receipts; their provisional status must stay explicit.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from pb_source_closed_run_export import seal_source_closed_run
from test_source_closed_run_export import quantity, trace
from tools.diag_gpt3_ten_customer_release_gates import (
    inspect_ten_customer_release_gates,
)


ROOT = Path(__file__).resolve().parents[1]
ARCHIVED = ROOT / "docs/engineering/lot16_original_signed_eight_row_20261015/production"
OWNER = (ROOT / "docs/engineering/four_job_runs/20261016_47c8031a"
         / "au_qld_lot16_power/outputs/au_qld_lot16_power.json")


def _source_and_customers():
    return (
        json.loads((ARCHIVED / "source_sealed_run.json").read_text(encoding="utf-8")),
        json.loads((ARCHIVED / "verified_customer_rows.json").read_text(encoding="utf-8")),
    )


def _inspect(source, customers, *, expected=None,
             project="au_qld_lot16_power", status="COMPLETED"):
    return inspect_ten_customer_release_gates(
        source, customers, expected_project_id=project,
        expected_source_sha256s=source["source_sha256s"] if expected is None else expected,
        original_producer_status=status,
    )


def _pair(name, key, *, physical="physical-a", status="firm", traced=True):
    data = quantity(
        quantity_id=name,
        family="opening_area",
        semantic_key=key,
        input_entity_ids=(physical,),
        evidence_ids=("original-observation-" + name,),
        value=2.0,
        unit="m2",
        status=status,
    )
    authority = trace(
        evidence_ids=("original-observation-" + name,) if traced else (),
        canonical_entity_ids=(physical,) if traced else (),
    )
    return data, authority


def _synthetic(*pairs):
    return seal_source_closed_run(
        [row for row, _ in pairs],
        project_id="project-a",
        traces_by_quantity_id={row.quantity_id: source for row, source in pairs},
    ).to_dict()


def test_g01_original_eight_row_source_envelope_integrity_and_tamper():
    old, customers = _source_and_customers()
    original = _inspect(old, customers)
    assert original["gates"]["G01_v1_envelope_integrity"]["passed"]
    tampered = deepcopy(old)
    tampered["quantities"][0]["value"] += 0.01
    got = _inspect(tampered, customers)
    assert not got["gates"]["G01_v1_envelope_integrity"]["passed"]
    assert got["first_failing_gate"] == "G01_v1_envelope_integrity"
    assert got["source_run_fingerprint"] is None


def test_g02_source_project_cannot_be_reassigned_by_display_name():
    old, customers = _source_and_customers()
    good = _inspect(old, customers)
    bad = _inspect(old, customers, project="other-actual-project")
    assert good["gates"]["G02_exact_project_identity"]["passed"]
    assert not bad["gates"]["G02_exact_project_identity"]["passed"]


@pytest.mark.parametrize("missing_source", [
    [],
    ["c" * 64],
    ["a" * 64, "b" * 64],
    ["bad_sha"],
    ["a" * 64, "a" * 64],
])
def test_g03_expected_original_source_package_must_match_exactly(missing_source):
    old, customers = _source_and_customers()
    assert not _inspect(old, customers, expected=missing_source)[
        "gates"]["G03_exact_source_package"]["passed"]
    assert _inspect(old, customers)["gates"]["G03_exact_source_package"]["passed"]


def test_g04_source_scope_trace_and_identity_missing_are_not_firm():
    raw = _synthetic(_pair("one", "opening_area:p-one", traced=False))
    got = inspect_ten_customer_release_gates(
        raw, [], expected_project_id="project-a",
        expected_source_sha256s=["a" * 64], original_producer_status="COMPLETED",
    )
    assert got["gates"]["G01_v1_envelope_integrity"]["passed"]
    assert not got["gates"]["G04_provenance_scope_and_identity"]["passed"]


@pytest.mark.parametrize("status", ["review_required", "conflict", "candidate", "provisional"])
def test_g05_nonfirm_status_remains_blocked_even_when_source_digests_are_valid(status):
    raw = _synthetic(_pair("one", "opening_area:p-one", status=status))
    got = inspect_ten_customer_release_gates(
        raw, [], expected_project_id="project-a",
        expected_source_sha256s=["a" * 64], original_producer_status="COMPLETED",
    )
    assert got["gates"]["G01_v1_envelope_integrity"]["passed"]
    assert not got["gates"]["G05_publishable_finite_metric"]["passed"]


def test_g06_two_alternative_semantic_claims_on_same_physical_opening_hold():
    raw = _synthetic(
        _pair("one", "door_area:physical-a"),
        _pair("two", "window_area:physical-a"),
    )
    got = inspect_ten_customer_release_gates(
        raw, [], expected_project_id="project-a",
        expected_source_sha256s=["a" * 64], original_producer_status="COMPLETED",
    )
    assert got["cross_semantic_physical_review_count"] == 1
    assert not got["gates"]["G06_cross_semantic_physical_review"]["passed"]
    assert got["customer_release_approved"] is False


@pytest.mark.parametrize("damage", ["missing", "duplicate", "foreign", "identity_stripped"])
def test_g07_customer_quantity_id_universe_fails_closed(damage):
    old, customers = _source_and_customers()
    modified = deepcopy(customers)
    if damage == "missing":
        modified.pop()
    elif damage == "duplicate":
        modified.append(deepcopy(modified[0]))
    elif damage == "foreign":
        modified[0]["quantity_id"] = "source_foreign"
    elif damage == "identity_stripped":
        # The real V1 verifier permits identity recovered from authenticated
        # direct or persisted provenance. Strip ALL three carriers to prove
        # only an original machine source reference survives, which must be
        # rejected as a missing automated identity.
        del modified[0]["quantity_id"]
        del modified[0]["commercial_projection_provenance"]
        del modified[0]["notes"]
    got = _inspect(old, modified)
    assert not got["gates"]["G07_customer_identity_bijection"]["passed"]
    assert got["gates"]["G08_customer_provenance_exact_v1"]["passed"] is False


def test_g08_original_customer_works_only_against_original_matching_v1():
    original, customers = _source_and_customers()
    new = json.loads(OWNER.read_text(encoding="utf-8"))
    old_report = _inspect(original, customers)
    newer_report = _inspect(new, customers)
    assert old_report["gates"]["G08_customer_provenance_exact_v1"]["passed"]
    assert newer_report["gates"]["G07_customer_identity_bijection"]["passed"]
    assert not newer_report["gates"]["G08_customer_provenance_exact_v1"]["passed"]
    assert newer_report["source_run_fingerprint"] != old_report["source_run_fingerprint"]


def test_g08_mutating_embedded_trace_or_customer_receipt_does_not_pass():
    original, customers = _source_and_customers()
    forged = deepcopy(customers)
    forged[0]["commercial_projection_provenance"]["source_trace"]["evidence_ids"][0] += "_foreign"
    got = _inspect(original, forged)
    assert got["gates"]["G07_customer_identity_bijection"]["passed"]
    assert not got["gates"]["G08_customer_provenance_exact_v1"]["passed"]


@pytest.mark.parametrize("run_status", ["MEMORY_LIMIT", "SOURCE_COMPLEXITY_BLOCKED", "UNEXECUTED"])
def test_g09_original_producer_did_not_complete_is_never_zero_accuracy(run_status):
    source, customers = _source_and_customers()
    got = _inspect(source, customers, status=run_status)
    assert not got["gates"]["G09_producer_execution_and_customer_inclusion"]["passed"]
    assert got["official_four_project_coverage_accuracy"] is None
    assert got["benchmark_score_granted"] is False


def test_g09_historical_original_customer_is_provisional_not_commercially_approved():
    source, customers = _source_and_customers()
    report = _inspect(source, customers)
    assert report["gates"]["G08_customer_provenance_exact_v1"]["passed"]
    assert report["gates"]["G09_producer_execution_and_customer_inclusion"]["passed"] is False
    assert all(row["inclusion_status"] == "PROVISIONAL" for row in customers)


def test_g10_source_issuer_attestation_never_inferred_from_matching_values():
    source, customers = _source_and_customers()
    report = _inspect(source, customers)
    assert len(report["gates"]) == 10
    assert report["gates"]["G10_source_issuer_scope_attestation"] == {
        "passed": False,
        "failure": "PRODUCER_AUTHENTICATED_SNAPSHOT_DECISION_SCOPE_ATTESTATION_NOT_ISSUED",
    }
    assert report["source_issuer_authenticated"] is False
    assert report["customer_release_approved"] is False
    assert report["official_four_project_coverage_accuracy"] is None
    assert report["official_four_project_precision_adjusted_accuracy"] is None
    assert report["benchmark_score_granted"] is False


def test_all_ten_gates_are_read_only_and_order_independent():
    source, customers = _source_and_customers()
    before_source = deepcopy(source)
    before_customers = deepcopy(customers)
    report = _inspect(source, customers)
    reversed_report = _inspect(source, list(reversed(customers)))
    assert report == reversed_report
    assert source == before_source
    assert customers == before_customers
    assert report["passed_gate_count"] == 8
    assert report["first_failing_gate"] == "G09_producer_execution_and_customer_inclusion"
