"""GPT3 append-only V1 customer/source admission BEFORE independent V2 identity review.

This tool does NOT authenticate a producer's issuer, read benchmark truth,
construct benchmark bindings, or compute accuracy. A READY review receipt is
not permission to sign, commercially publish, or score a construction item.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from pb_customer_output_verification import verify_sealed_customer_output
from pb_source_closed_run_export import (
    SealedSourceClosedRun,
    sealed_source_closed_run_from_dict,
)
from tools.gpt3_signed_v1_physical_drift import compare_signed_v1_physical_runs
from tools.report_gpt3_four_project_evidence import (
    FROZEN_ROOT, _json_customer_rows, _json_object,
)
from tools.gpt3_safe_original_report_output import (
    preflight_new_diagnostic, write_new_diagnostic,
)


def _validated(run: SealedSourceClosedRun) -> SealedSourceClosedRun:
    if type(run) is not SealedSourceClosedRun:
        raise TypeError("batch input must be a signed source-closed V1 run")
    return sealed_source_closed_run_from_dict(run.to_dict())


def _failed(result: dict[str, Any], first_gate: str) -> dict[str, Any]:
    result["admission_status"] = "BLOCKED"
    result["first_failing_gate"] = first_gate
    return result


def assess_append_only_signed_batch(
    baseline: SealedSourceClosedRun,
    candidate: SealedSourceClosedRun,
    *,
    baseline_customers: Sequence[Mapping[str, Any]],
    candidate_customers: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Inspect two fully verified customer epochs, never approve source issuance.

    Existing quantity ID AND all full V1 source/identity/receipt fields are
    immutable. A legitimately independent area and width of the SAME physical
    opening have distinct families; two opening_area claims of that physical
    opening cannot both enter the same candidate run.
    """
    baseline = _validated(baseline)
    candidate = _validated(candidate)
    if baseline.project_id != candidate.project_id:
        raise ValueError("baseline and candidate project identities disagree")

    # Verify BOTH customer epochs: a new signed run never inherits old
    # commercial permissions or accepts an omitted/new duplicate customer row.
    old_verified = verify_sealed_customer_output(baseline, baseline_customers)
    new_verified = verify_sealed_customer_output(candidate, candidate_customers)
    drift = compare_signed_v1_physical_runs(baseline, candidate)
    result: dict[str, Any] = {
        "schema_version": "gpt3_source_append_only_batch_gate.v1",
        "publication_status": "UNPUBLISHED",
        "source_authenticated": False,
        "new_measurement_issued": False,
        "customer_approval_granted": False,
        "independent_benchmark_identity_verified": False,
        "official_v2_accuracy": None,
        "project_id": baseline.project_id,
        "baseline_run_fingerprint": baseline.fingerprint,
        "candidate_run_fingerprint": candidate.fingerprint,
        "source_sha256s": list(baseline.source_sha256s),
        "baseline_quantity_count": len(baseline.quantities),
        "candidate_quantity_count": len(candidate.quantities),
        "baseline_customer_verified_count": old_verified.customer_row_count,
        "candidate_customer_verified_count": new_verified.customer_row_count,
        "retained_quantity_ids": drift["unchanged_quantity_ids"],
        "added_quantity_ids": drift["added_quantity_ids"],
        "removed_quantity_ids": drift["removed_quantity_ids"],
        "altered_physical_quantity_ids": [
            x["quantity_id"] for x in drift["physical_semantic_conflicts"]
        ],
        "altered_receipt_quantity_ids": [
            x["quantity_id"] for x in drift["receipt_changed_quantity_ids"]
        ],
        "admission_status": "BLOCKED",
        "first_failing_gate": None,
    }
    if not baseline.quantities:
        return _failed(result, "BASELINE_SIGNED_SOURCE_UNIVERSE_EMPTY")
    if not baseline.source_sha256s or not drift["source_sha_receipts_equal"]:
        return _failed(result, "ORIGINAL_SOURCE_PACKAGE_CHANGED_OR_UNAVAILABLE")
    if baseline.revision_ids != candidate.revision_ids:
        return _failed(result, "SOURCE_REVISION_EPOCH_CHANGED")
    if drift["removed_quantity_ids"]:
        return _failed(result, "PREVIOUSLY_SIGNED_QUANTITY_REMOVED")
    if drift["physical_semantic_conflicts"]:
        return _failed(result, "PREVIOUSLY_SIGNED_PHYSICAL_QUANTITY_CHANGED")
    if drift["receipt_changed_quantity_ids"]:
        return _failed(result, "PREVIOUSLY_SIGNED_SOURCE_RECEIPT_CHANGED")
    if len(drift["unchanged_quantity_ids"]) != len(baseline.quantities):
        return _failed(result, "PREVIOUS_SIGNED_QUANTITY_RETENTION_INCOMPLETE")
    if not drift["added_quantity_ids"]:
        return _failed(result, "NO_NEW_SIGNED_QUANTITIES")

    prior = {row.quantity_id for row in baseline.quantities}
    # Legacy V1 archives may predate the producer's later duplicate-opening
    # signature gate. A+B and B+C overlap physically even though their
    # complete source-ref tuples differ and their semantic keys can differ.
    # One measured AREA and one independently proven COUNT are separate
    # source families; within each family, an original physical instance
    # must occur at most once across the complete candidate signed universe.
    opening_owners: dict[tuple[str, str], str] = {}
    opening_kinds: dict[str, tuple[str, str]] = {}
    for row in candidate.quantities:
        if row.family not in {"opening_area", "opening_count"} or row.abstained:
            continue
        if not row.object_identity_refs:
            return _failed(result, "OPENING_PHYSICAL_IDENTITY_MISSING")
        prefixes = (
            (("door_area:", "door"), ("window_area:", "window"))
            if row.family == "opening_area" else
            (("door_count:", "door"), ("window_count:", "window"))
        )
        source_kind = next(
            (kind for prefix, kind in prefixes if row.semantic_key.startswith(prefix)),
            None,
        )
        for physical_id in row.object_identity_refs:
            key = (row.family, physical_id)
            if key in opening_owners:
                return _failed(
                    result, (
                        "DUPLICATE_OPENING_AREA_PHYSICAL_IDENTITY"
                        if row.family == "opening_area"
                        else "DUPLICATE_OPENING_COUNT_PHYSICAL_IDENTITY"
                    )
                )
            opening_owners[key] = row.quantity_id
            if source_kind is not None:
                prior_kind = opening_kinds.get(physical_id)
                if prior_kind is not None and prior_kind[0] != source_kind:
                    return _failed(result, "CONFLICTING_ORIGINAL_OPENING_DOOR_WINDOW_KIND")
                opening_kinds[physical_id] = (source_kind, row.quantity_id)
    new = [row for row in candidate.quantities if row.quantity_id not in prior]
    for row in new:
        if (
            row.abstained is not False
            or row.lineage_ok is not True
            or row.status != "corroborated"
            or row.blocking_reasons
            or not row.object_identity_refs
        ):
            return _failed(result, "NEW_QUANTITY_NOT_FIRM_SOURCE_CLOSED")
    result["admission_status"] = "READY_FOR_INDEPENDENT_IDENTITY_REVIEW"
    result["first_failing_gate"] = (
        "ORIGINAL_PRODUCER_AND_FROZEN_IDENTITY_NOT_AUTHENTICATED_BY_THIS_GATE"
    )
    return result


def _sha(path: Path) -> str:
    h = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_append_only_report(
    *,
    baseline_sealed: Path, candidate_sealed: Path,
    baseline_customer: Path, candidate_customer: Path,
) -> dict[str, Any]:
    paths = (baseline_sealed, candidate_sealed,
             baseline_customer, candidate_customer)
    before = tuple(_sha(path) for path in paths)
    old = sealed_source_closed_run_from_dict(_json_object(baseline_sealed))
    new = sealed_source_closed_run_from_dict(_json_object(candidate_sealed))
    old_rows = _json_customer_rows(baseline_customer, allow_manual=True)
    new_rows = _json_customer_rows(candidate_customer, allow_manual=True)
    result = assess_append_only_signed_batch(
        old, new, baseline_customers=old_rows, candidate_customers=new_rows,
    )
    after = tuple(_sha(path) for path in paths)
    if before != after:
        raise ValueError("signed source or customer receipt changed during batch gate")
    result["input_file_sha256s"] = dict(zip(
        ("baseline_sealed", "candidate_sealed",
         "baseline_customer", "candidate_customer"), before,
    ))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("baseline-sealed", "candidate-sealed",
                "baseline-customer", "candidate-customer", "output"):
        parser.add_argument("--" + arg, required=True, type=Path)
    args = parser.parse_args(argv)
    protected = (FROZEN_ROOT, args.baseline_sealed, args.candidate_sealed,
                 args.baseline_customer, args.candidate_customer)
    preflight_new_diagnostic(args.output, protected_roots=protected)
    result = build_append_only_report(
        baseline_sealed=args.baseline_sealed,
        candidate_sealed=args.candidate_sealed,
        baseline_customer=args.baseline_customer,
        candidate_customer=args.candidate_customer,
    )
    write_new_diagnostic(
        args.output,
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        protected_roots=protected,
    )
    print(json.dumps({
        "admission_status": result["admission_status"],
        "first_failing_gate": result["first_failing_gate"],
        "added": len(result["added_quantity_ids"]),
        "official_v2_accuracy": None,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
