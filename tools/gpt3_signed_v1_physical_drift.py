"""Compare exact V1 signed construction quantities without numeric/label re-keying.

V1 SHA digests authenticate the *content* of both run receipts, not PDF issuer
authority. Even equal amounts and counts cannot make added/removed physical IDs
equivalent, and an old customer approval cannot follow a new sealed fingerprint.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from pb_customer_output_verification import verify_sealed_customer_output
from pb_source_closed_run_export import (
    SealedSourceClosedRun, sealed_source_closed_run_from_dict,
)
from tools.gpt3_safe_original_report_output import (
    preflight_new_diagnostic, write_new_diagnostic,
)
from tools.report_gpt3_four_project_evidence import FROZEN_ROOT, _json_object, _json_customer_rows


_IDENTITY_FIELDS = (
    "family", "semantic_key", "unit", "value", "abstained", "status",
    "authority", "document_id", "source_sha256", "source_page",
    "viewport_id", "revision_id", "object_identity_refs",
    "trace_canonical_entity_ids",
)
_RECEIPT_FIELDS = (
    "evidence_ids", "trace_evidence_ids", "blocking_reasons",
    "reason_codes", "lineage_ok", "lineage_reason_codes", "confidence",
)


def compare_signed_v1_physical_runs(
    baseline: SealedSourceClosedRun,
    candidate: SealedSourceClosedRun,
) -> dict:
    """Return a deterministic, *unpublished* physical ID/source receipt diff."""
    baseline = sealed_source_closed_run_from_dict(baseline.to_dict())
    candidate = sealed_source_closed_run_from_dict(candidate.to_dict())
    if baseline.project_id != candidate.project_id:
        raise ValueError("cannot compare signed runs from different projects")
    source_equal = baseline.source_sha256s == candidate.source_sha256s
    result = {
        "schema_version": "gpt3_signed_v1_physical_drift.v1",
        "publication_status": "UNPUBLISHED",
        "source_authenticated": False,
        "official_v2_accuracy": None,
        "project_id": baseline.project_id,
        "baseline_run_fingerprint": baseline.fingerprint,
        "candidate_run_fingerprint": candidate.fingerprint,
        "source_sha_receipts_equal": source_equal,
        "baseline_quantity_count": len(baseline.quantities),
        "candidate_quantity_count": len(candidate.quantities),
        "unchanged_quantity_ids": [],
        "receipt_changed_quantity_ids": [],
        "physical_semantic_conflicts": [],
        "removed_quantity_ids": [],
        "added_quantity_ids": [],
        "quantity_ids_alias_inferred": False,
    }
    if (
        not baseline.quantities or not candidate.quantities
        or not baseline.source_sha256s or not candidate.source_sha256s
    ):
        # A hash-consistent empty V1 envelope is not an executed original
        # source universe. Never count an empty=empty comparison as success,
        # and never re-key a prior physical quantity into an empty run.
        # Inventory-only deltas: exact signed IDs, not source equivalence.
        if baseline.quantities and not candidate.quantities:
            result["removed_quantity_ids"] = sorted(
                quantity.quantity_id for quantity in baseline.quantities
            )
        elif candidate.quantities and not baseline.quantities:
            result["added_quantity_ids"] = sorted(
                quantity.quantity_id for quantity in candidate.quantities
            )
        result["comparison_status"] = "NO_SIGNED_SOURCE_QUANTITY_UNIVERSE"
        return result
    if not source_equal:
        # A shared quantity ID from a different source package is not proof
        # that either document, wall or floor represents the same object.
        result["comparison_status"] = "SOURCE_PACKAGE_NOT_COMPARABLE"
        return result
    old = {item.quantity_id: item for item in baseline.quantities}
    new = {item.quantity_id: item for item in candidate.quantities}
    for quantity_id in sorted(set(old) - set(new)):
        result["removed_quantity_ids"].append(quantity_id)
    for quantity_id in sorted(set(new) - set(old)):
        result["added_quantity_ids"].append(quantity_id)
    for quantity_id in sorted(set(old) & set(new)):
        previous = old[quantity_id]
        current = new[quantity_id]
        if previous.fingerprint == current.fingerprint:
            result["unchanged_quantity_ids"].append(quantity_id)
            continue
        changed_identity = [
            key for key in _IDENTITY_FIELDS
            if getattr(previous, key) != getattr(current, key)
        ]
        changed_receipt = [
            key for key in _RECEIPT_FIELDS
            if getattr(previous, key) != getattr(current, key)
        ]
        # Any unexpected V1 payload drift must still remain visible rather
        # than being silently called unchanged by the selected field lists.
        known = set(_IDENTITY_FIELDS) | set(_RECEIPT_FIELDS)
        unknown_changes = sorted(
            key for key in previous.payload()
            if key not in known and key != "quantity_id"
            and previous.payload()[key] != current.payload().get(key)
        )
        if changed_identity or unknown_changes:
            result["physical_semantic_conflicts"].append({
                "quantity_id": quantity_id,
                "changed_fields": sorted(changed_identity + unknown_changes),
                "old_fingerprint": previous.fingerprint,
                "new_fingerprint": current.fingerprint,
            })
        else:
            result["receipt_changed_quantity_ids"].append({
                "quantity_id": quantity_id,
                "changed_receipt_fields": sorted(changed_receipt),
                "old_fingerprint": previous.fingerprint,
                "new_fingerprint": current.fingerprint,
            })
    has_changes = (
        result["physical_semantic_conflicts"]
        or result["receipt_changed_quantity_ids"]
        or result["removed_quantity_ids"]
        or result["added_quantity_ids"]
        or baseline.fingerprint != candidate.fingerprint
    )
    result["comparison_status"] = (
        "DIAGNOSTIC_DRIFT" if has_changes else "BYTE_IDENTICAL_SIGNED_RECEIPTS"
    )
    return result


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def build_signed_v1_physical_drift_report(
    *, baseline_path: Path, candidate_path: Path,
    baseline_customer_path: Path | None = None,
    candidate_customer_path: Path | None = None,
) -> dict:
    if (baseline_customer_path is None) != (candidate_customer_path is None):
        raise ValueError("both source-closed customer snapshots must be provided together")
    paths = (baseline_path, candidate_path)
    if baseline_customer_path is not None and candidate_customer_path is not None:
        paths += (baseline_customer_path, candidate_customer_path)
    hashes_before = tuple(_digest(path) for path in paths)
    baseline = sealed_source_closed_run_from_dict(_json_object(baseline_path))
    candidate = sealed_source_closed_run_from_dict(_json_object(candidate_path))
    if baseline_customer_path is not None and candidate_customer_path is not None:
        baseline_rows = _json_customer_rows(baseline_customer_path, allow_manual=True)
        candidate_rows = _json_customer_rows(candidate_customer_path, allow_manual=True)
        baseline_verified = verify_sealed_customer_output(baseline, baseline_rows)
        candidate_verified = verify_sealed_customer_output(candidate, candidate_rows)
    result = compare_signed_v1_physical_runs(baseline, candidate)
    if baseline_customer_path is not None and candidate_customer_path is not None:
        result["customer_epoch_bijection"] = "BOTH_INDEPENDENTLY_VERIFIED"
        result["baseline_verified_customer_count"] = baseline_verified.customer_row_count
        result["candidate_verified_customer_count"] = candidate_verified.customer_row_count
    else:
        result["customer_epoch_bijection"] = "NOT_PROVIDED_NOT_VERIFIED"
    hashes_after = tuple(_digest(path) for path in paths)
    if hashes_before != hashes_after:
        raise ValueError("signed source/customer artifact changed during drift comparison")
    result["source_receipt_file_sha256s"] = {
        "baseline": hashes_before[0],
        "candidate": hashes_before[1],
    }
    if len(hashes_before) == 4:
        result["customer_receipt_file_sha256s"] = {
            "baseline": hashes_before[2],
            "candidate": hashes_before[3],
        }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-sealed", type=Path, required=True)
    parser.add_argument("--candidate-sealed", type=Path, required=True)
    parser.add_argument("--baseline-customer", type=Path)
    parser.add_argument("--candidate-customer", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if (args.baseline_customer is None) != (args.candidate_customer is None):
        parser.error("both customer epochs must be provided together")
    protected = (
        FROZEN_ROOT, args.baseline_sealed, args.candidate_sealed,
        args.baseline_customer, args.candidate_customer,
    )
    preflight_new_diagnostic(args.output, protected_roots=protected)
    report = build_signed_v1_physical_drift_report(
        baseline_path=args.baseline_sealed, candidate_path=args.candidate_sealed,
        baseline_customer_path=args.baseline_customer,
        candidate_customer_path=args.candidate_customer,
    )
    write_new_diagnostic(
        args.output,
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        protected_roots=protected,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
