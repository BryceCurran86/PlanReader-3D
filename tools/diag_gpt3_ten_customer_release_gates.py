"""Ten independently inspectable source/customer release gates; shadow only.

This reader does NOT publish a quantity, sign source scope, mutate customer
output, deduplicate producer claims or invoke the frozen Full Plan V2 scorer.
It uses the existing V1 loader and customer verifier without replacing them.
Original source-file/expected-source authority belongs to the source owner.
Even if nine gates pass, G10 cannot pass without an independently reviewed,
producer-authenticated snapshot/decision-scope issuer contract (not present
in V1). Never mistake an unkeyed SHA-256 integrity fingerprint for a signature.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from pb_customer_output_verification import (
    CustomerOutputVerificationError,
    _customer_quantity_id,
    _has_machine_quantity_receipt,
    _strict_customer_notes,
    verify_sealed_customer_output,
)
from pb_source_closed_run_export import (
    SourceClosedRunExportError,
    sealed_source_closed_run_from_dict,
)

SCHEMA = "gpt3.ten_customer_release_gates.shadow.v1"
SHA_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
PUBLISHABLE_STATUSES = frozenset({"firm", "corroborated"})


def _gate(ok: bool, failure: str) -> dict[str, Any]:
    return {"passed": bool(ok), "failure": None if ok else failure}


def _good_id(value: Any) -> bool:
    return type(value) is str and bool(value) and value == value.strip()


def _positive_finite_metric(value: Any) -> bool:
    if type(value) not in (int, float, Decimal):
        return False
    try:
        n = Decimal(str(value))
    except (InvalidOperation, ValueError, OverflowError):
        return False
    return n.is_finite() and n > 0


def _automated_customer_rows(
    customer_rows: Any,
) -> tuple[list[tuple[str, Mapping[str, Any]]], bool]:
    """Use the *existing* V1 customer's canonical machine-ID contract.

    The customer verifier permits a machine quantity ID in direct provenance
    or persisted commercial_takeoff notes when the display column was
    omitted. A manual estimator can write "quantity" in ordinary notes.
    This shadow check must preserve both cases, while rejecting malformed
    machine receipts and duplicate structured notes instead of making the
    earlier G07 stage appear green by skipping such a row.
    """
    if not isinstance(customer_rows, Sequence) or isinstance(
        customer_rows, (str, bytes, bytearray)
    ):
        return [], False
    rows: list[tuple[str, Mapping[str, Any]]] = []
    for row in customer_rows:
        if not isinstance(row, Mapping):
            return [], False
        try:
            quantity_id = _customer_quantity_id(row)
        except CustomerOutputVerificationError:
            return [], False
        if not quantity_id:
            if (
                row.get("commercial_projection_provenance") is not None
                or _has_machine_quantity_receipt(row.get("source_reference"))
            ):
                return [], False
            notes = row.get("notes")
            if isinstance(notes, str) and notes.strip():
                try:
                    notes_receipt = _strict_customer_notes(notes)
                except CustomerOutputVerificationError as exc:
                    # The production verifier treats malformed human notes as
                    # manual, except for duplicate projection-provenance keys.
                    if "duplicate provenance key" in str(exc):
                        return [], False
                    continue
                if str(notes_receipt.get("adapter", "")).strip() == "commercial_takeoff":
                    return [], False
            continue
        rows.append((quantity_id, row))
    return rows, True

def _cross_semantic_claim_count(run: Any) -> int:
    indexed: dict[tuple[str, str], set[str]] = defaultdict(set)
    for item in run.quantities:
        if item.abstained or not item.lineage_ok:
            continue
        if item.status.strip().lower() not in PUBLISHABLE_STATUSES:
            continue
        for physical_id in item.object_identity_refs:
            indexed[(item.family, physical_id)].add(item.semantic_key)
    return sum(len(keys) > 1 for keys in indexed.values())


def inspect_ten_customer_release_gates(
    sealed_run_payload: Mapping[str, Any],
    customer_rows: Sequence[Mapping[str, Any]],
    *,
    expected_project_id: str,
    expected_source_sha256s: Sequence[str],
    original_producer_status: str,
) -> dict[str, Any]:
    """Report first failing stages without source/commercial/evaluator grants.

    The caller must obtain `expected_source_sha256s` from the independent
    original source-package manifest; this function CANNOT authenticate that
    manifest. The computed digest validates content integrity against the
    supplied run's digest, not who generated or approved the producer record.
    """
    gates: dict[str, dict[str, Any]] = {}
    try:
        run = sealed_source_closed_run_from_dict(sealed_run_payload)
    except (SourceClosedRunExportError, TypeError, ValueError, AttributeError):
        run = None
    gates["G01_v1_envelope_integrity"] = _gate(
        run is not None, "SEALED_RUN_DIGEST_OR_STRUCTURE_INVALID"
    )

    exact_project = (
        run is not None and _good_id(expected_project_id)
        and run.project_id == expected_project_id
    )
    gates["G02_exact_project_identity"] = _gate(
        exact_project, "ORIGINAL_PROJECT_IDENTITY_MISMATCH"
    )

    expected = (
        tuple(expected_source_sha256s)
        if isinstance(expected_source_sha256s, (tuple, list)) else ()
    )
    expected_ok = (
        bool(expected) and all(
            type(value) is str and SHA_PATTERN.fullmatch(value) for value in expected
        ) and len(set(expected)) == len(expected)
    )
    sources_match = (
        run is not None and expected_ok
        and set(expected) == set(run.source_sha256s)
        and len(expected) == len(run.source_sha256s)
    )
    gates["G03_exact_source_package"] = _gate(
        sources_match, "SOURCE_PACKAGE_INCOMPLETE_OR_MANIFEST_UNVERIFIED"
    )

    rows = run.quantities if run is not None else ()
    usable = [row for row in rows if not row.abstained]
    lineage_ok = (
        bool(usable) and all(
            item.lineage_ok and not item.lineage_reason_codes
            and _good_id(item.document_id) and _good_id(item.source_page)
            and _good_id(item.viewport_id) and _good_id(item.revision_id)
            and _good_id(item.quantity_id) and item.source_sha256 in run.source_sha256s
            and bool(item.object_identity_refs)
            and set(item.object_identity_refs) <= set(item.trace_canonical_entity_ids)
            and bool(item.evidence_ids)
            and set(item.evidence_ids) <= set(item.trace_evidence_ids)
            and not item.blocking_reasons
            for item in usable
        )
    )
    gates["G04_provenance_scope_and_identity"] = _gate(
        lineage_ok, "SOURCE_QUANTITY_PROVENANCE_INCOMPLETE"
    )

    metric_ok = (
        bool(usable) and all(
            item.status.strip().lower() in PUBLISHABLE_STATUSES
            and _positive_finite_metric(item.value)
            and _good_id(item.unit)
            for item in usable
        )
    )
    gates["G05_publishable_finite_metric"] = _gate(
        metric_ok, "QUANTITY_NOT_FIRM_FINITE_OR_MEASURABLE"
    )

    collision_count = _cross_semantic_claim_count(run) if run is not None else 0
    gates["G06_cross_semantic_physical_review"] = _gate(
        run is not None and collision_count == 0,
        "EXACT_PHYSICAL_CLAIM_CROSS_SEMANTIC_REVIEW_REQUIRED",
    )

    automated, customer_well_formed = _automated_customer_rows(customer_rows)
    auto_ids = [quantity_id for quantity_id, _ in automated] if customer_well_formed else []
    expected_ids = {row.quantity_id for row in usable}
    customer_universe_ok = (
        run is not None and customer_well_formed
        and len(set(auto_ids)) == len(auto_ids)
        and set(auto_ids) == expected_ids
    )
    gates["G07_customer_identity_bijection"] = _gate(
        customer_universe_ok, "CUSTOMER_MISSING_DUPLICATED_OR_FOREIGN_QUANTITY"
    )

    verified = None
    if run is not None and customer_universe_ok:
        try:
            verified = verify_sealed_customer_output(run, customer_rows)
        except (CustomerOutputVerificationError, TypeError, ValueError):
            pass
    gates["G08_customer_provenance_exact_v1"] = _gate(
        verified is not None, "CUSTOMER_NOT_VERIFIED_AGAINST_THIS_V1_RUN"
    )

    production_complete = original_producer_status == "COMPLETED"
    # A string status from a customer sheet is NOT standalone authorisation.
    # At most this diagnostic can show inclusion review is not outstanding;
    # G10 still blocks source-scope commercial/benchmark promotion.
    inclusion_review_complete = (
        verified is not None and bool(automated) and all(
            row.get("inclusion_status") == "APPROVED"
            and str(row.get("status", "")).strip().lower() != "to review"
            for _, row in automated
        )
    )
    gates["G09_producer_execution_and_customer_inclusion"] = _gate(
        production_complete and inclusion_review_complete,
        "UNEXECUTED_PRODUCER_OR_CUSTOMER_STILL_PROVISIONAL",
    )

    # No valid issuer-scope verifier for snapshot_id and decision_scope_id
    # exists in the historical signed V1 contract. A caller-supplied Boolean,
    # equal number, comparable source shape or hash MUST NOT open this gate.
    gates["G10_source_issuer_scope_attestation"] = _gate(
        False, "PRODUCER_AUTHENTICATED_SNAPSHOT_DECISION_SCOPE_ATTESTATION_NOT_ISSUED"
    )

    failures = [key for key, val in gates.items() if not val["passed"]]
    return {
        "schema_version": SCHEMA,
        "status": "DIAGNOSTIC_UNPUBLISHED",
        "requested_project_id": expected_project_id,
        "source_run_fingerprint": run.fingerprint if run is not None else None,
        "original_producer_status": original_producer_status,
        "sealed_quantities": len(rows),
        "nonabstained_quantity_count": len(usable),
        "automated_customer_quantity_count": len(automated),
        "cross_semantic_physical_review_count": collision_count,
        "gates": gates,
        "passed_gate_count": len(gates) - len(failures),
        "first_failing_gate": failures[0] if failures else None,
        "source_issuer_authenticated": False,
        "customer_release_approved": False,
        "official_four_project_coverage_accuracy": None,
        "official_four_project_precision_adjusted_accuracy": None,
        "benchmark_score_granted": False,
    }
