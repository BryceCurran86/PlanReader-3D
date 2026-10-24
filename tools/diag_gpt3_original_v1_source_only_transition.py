"""Compare genuine signed V1 source snapshots when old customer rows are absent.

An independently signed source V1 run is not a customer bijection, physical
SAME witness, original PDF scope issuance or V2 match. This read-only consumer
allows old archived runs lacking a customer export to be audited WITHOUT
forging an old customer file, bypassing the existing customer-verified replay,
or converting equal counts/values into the same physical opening.

Original PDFs remain private. Frozen truth/evaluator/seal protocols unchanged.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any, Mapping

from pb_source_closed_run_export import sealed_source_closed_run_from_dict
from tools.gpt3_signed_v1_replay_drift import (
    _canonical_manifest_for, _compare_historical_quantity,
)
from tools.gpt3_safe_original_report_output import (
    preflight_new_diagnostic, write_new_diagnostic,
)
from tools.report_gpt3_four_project_evidence import FROZEN_ROOT, _json_object


SCHEMA = "gpt3.original_v1_source_only_transition_diagnostic.v1"
_SOURCE_PROJECT = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]*\Z")


def _claim(row: Any) -> dict[str, Any]:
    return {
        "quantity_id": row.quantity_id,
        "semantic_key": row.semantic_key,
        "value": row.value,
        "unit": row.unit,
        "signed_quantity_fingerprint": row.fingerprint,
        "object_identity_refs": list(row.object_identity_refs),
    }


def _diff(
    old_by_id: Mapping[str, Any], new_by_id: Mapping[str, Any],
) -> dict[str, Any]:
    """Only classify already independently verified signed V1 quantities.

    An added/missing quantity is NEVER paired with another by size, semantic
    phrase, source page, object proximity or sorted-list index.
    """
    old_ids = set(old_by_id)
    new_ids = set(new_by_id)
    shared: list[dict[str, Any]] = []
    for qid in sorted(old_ids & new_ids):
        change = _compare_historical_quantity(old_by_id[qid], new_by_id[qid])
        shared.append({
            "quantity_id": qid,
            "historical_quantity_fingerprint": old_by_id[qid].fingerprint,
            "candidate_quantity_fingerprint": new_by_id[qid].fingerprint,
            **change,
        })
    missing = [_claim(old_by_id[qid]) for qid in sorted(old_ids - new_ids)]
    added = [_claim(new_by_id[qid]) for qid in sorted(new_ids - old_ids)]
    counts: dict[str, int] = {}
    for row in shared:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    changed_issuer = any(
        row["status"] != "EXACT_HISTORICAL_V1_PRESERVED" for row in shared
    )
    return {
        "shared_quantity_id_count": len(shared),
        "shared_receipt_status_counts": dict(sorted(counts.items())),
        "shared_quantity_differences": shared,
        "missing_historical_quantities": missing,
        "new_candidate_quantities": added,
        "same_quantity_id_universe": not missing and not added,
        # Zero shared identities provide no byte-level continuity evidence:
        # the Python all([]) vacuity must not describe unrelated source runs
        # as "all shared exact" when every physical identity was replaced.
        "all_shared_fingerprints_byte_exact": bool(shared) and not changed_issuer,
        "historical_to_candidate_quantity_equivalence_proven": False,
    }


def inspect_signed_source_only_v1_transition(
    *, archived_run: Mapping[str, Any], candidate_run: Mapping[str, Any],
) -> dict[str, Any]:
    """Independently validate BOTH complete V1 fingerprints before comparison.

    Unlike customer-bearing GPT3 replay drift, this diagnostic intentionally
    cannot verify the old customer projection when no old customer file exists.
    It always requires separate original producer/customer authority.
    """
    archived = sealed_source_closed_run_from_dict(archived_run)
    candidate = sealed_source_closed_run_from_dict(candidate_run)
    if archived.project_id != candidate.project_id:
        raise ValueError("historical and candidate signed runs have different projects")
    project_id = archived.project_id
    if type(project_id) is not str or not _SOURCE_PROJECT.fullmatch(project_id):
        raise ValueError("original source project scope is malformed")
    manifest = _canonical_manifest_for(project_id)
    original_sha = {row["sha256"] for row in manifest["source_documents"]}
    archived_sha, candidate_sha = (
        set(archived.source_sha256s), set(candidate.source_sha256s)
    )
    if (
        not archived_sha or not candidate_sha
        or not archived_sha <= original_sha or not candidate_sha <= original_sha
    ):
        raise ValueError("signed V1 SHA envelope is not part of frozen original source")
    old_by_id = {row.quantity_id: row for row in archived.quantities}
    new_by_id = {row.quantity_id: row for row in candidate.quantities}
    if (
        not old_by_id or not new_by_id
        or len(old_by_id) != len(archived.quantities)
        or len(new_by_id) != len(candidate.quantities)
    ):
        raise ValueError("original V1 quantity universe empty or identity duplicated")
    diff = _diff(old_by_id, new_by_id)
    if diff["missing_historical_quantities"] or diff["new_candidate_quantities"]:
        first_gate = "historical_quantity_identity_membership_changed"
    elif not diff["all_shared_fingerprints_byte_exact"]:
        first_gate = "original_producer_signed_receipts_rekeyed"
    elif archived_sha != candidate_sha:
        first_gate = "original_source_document_envelope_changed"
    else:
        first_gate = "independent_original_decision_scope_issuer_not_attested"
    return {
        "schema_version": SCHEMA,
        "project_id": project_id,
        "publication_status": "DIAGNOSTIC_UNPUBLISHED",
        "release_status": "SOURCE_ONLY_SNAPSHOT_IDENTITY_HOLD",
        "first_failing_authority_stage": first_gate,
        "historical_run_id": archived.run_id,
        "candidate_run_id": candidate.run_id,
        "historical_run_fingerprint": archived.fingerprint,
        "candidate_run_fingerprint": candidate.fingerprint,
        "signed_v1_fingerprints_verified": True,
        "historical_quantity_count": len(archived.quantities),
        "candidate_quantity_count": len(candidate.quantities),
        "historical_source_sha256s": sorted(archived_sha),
        "candidate_source_sha256s": sorted(candidate_sha),
        "original_source_document_universe_complete_in_both": (
            archived_sha == candidate_sha == original_sha
        ),
        # Signed V1 can legitimately carry ABSTAIN rows with value=None.
        # Preserve these separately instead of sorting None and real metrics,
        # which would crash before reporting the original authority blocker.
        "historical_values": sorted(
            row.value for row in archived.quantities if row.value is not None
        ),
        "candidate_values": sorted(
            row.value for row in candidate.quantities if row.value is not None
        ),
        "historical_unmeasured_quantity_count": sum(
            row.value is None for row in archived.quantities
        ),
        "candidate_unmeasured_quantity_count": sum(
            row.value is None for row in candidate.quantities
        ),
        **diff,
        "archived_customer_bijection_verified": False,
        "candidate_customer_bijection_verified": False,
        "producer_signed_decision_scope_verified": False,
        "cross_snapshot_customer_reuse_authorized": False,
        "new_firm_quantities_authorized": 0,
        "official_four_project_accuracy": None,
        "official_score_publication_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--historical-v1", type=Path, required=True)
    p.add_argument("--candidate-v1", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    roots = (FROZEN_ROOT, args.historical_v1, args.candidate_v1)
    preflight_new_diagnostic(args.output, protected_roots=roots)
    report = inspect_signed_source_only_v1_transition(
        archived_run=_json_object(args.historical_v1),
        candidate_run=_json_object(args.candidate_v1),
    )
    write_new_diagnostic(
        args.output, json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n",
        protected_roots=roots,
    )
    print(json.dumps({
        "status": report["release_status"],
        "shared_quantity_ids": report["shared_quantity_id_count"],
        "missing_historical": len(report["missing_historical_quantities"]),
        "new_candidate": len(report["new_candidate_quantities"]),
        "official_four_project_accuracy": None,
    }, sort_keys=True))
    return 2  # Deliberately never success/published as source/customer evidence.


if __name__ == "__main__":
    raise SystemExit(main())
