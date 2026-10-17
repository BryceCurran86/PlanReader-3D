"""Independent V1 replay/issuer drift audit. REPORTING ONLY, never a seal or score.

A matching physical quantity ID/value across producer snapshots does NOT prove
that reissued host/frame records bind the same structural source. Preserve old
V1 fingerprints and require real producer issuer/scope evidence before reuse.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from pb_source_closed_run_export import sealed_source_closed_run_from_dict
from pb_customer_output_verification import _customer_quantity_id, verify_sealed_customer_output
from tools.report_gpt3_four_project_evidence import (
    FROZEN_ROOT, _json_object, _json_customer_rows,
)
from tools.source_report_scoped_equality import evidence_swap_matches
from scripts.report_full_plan_v2_readiness import _write_readiness_report


# Compare separately: no text similarity, value similarity or "same room" guess.
# Every property is part of the source-owned original V1 signed proposition.
IMMUTABLE_V1_FIELDS = (
    "schema_version",
    "project_id",
    "quantity_id",
    "family",
    "semantic_key",
    "value",
    "unit",
    "status",
    "authority",
    "confidence",
    "abstained",
    "document_id",
    "source_sha256",
    "source_page",
    "viewport_id",
    "revision_id",
    "object_identity_refs",
    "trace_canonical_entity_ids",
    "blocking_reasons",
    "reason_codes",
    "lineage_ok",
    "lineage_reason_codes",
)
RECEIPT_FIELDS = ("evidence_ids", "trace_evidence_ids")


def _compare_historical_quantity(old: Any, fresh: Any) -> dict[str, Any]:
    old_payload = old.payload()
    new_payload = fresh.payload()
    changed = [
        name for name in IMMUTABLE_V1_FIELDS
        if old_payload.get(name) != new_payload.get(name)
    ]
    if changed:
        return {
            "status": "HISTORICAL_PROPOSITION_CONFLICT",
            "changed_fields": changed,
            "issuer_attestation_required": True,
        }
    if old.fingerprint == fresh.fingerprint and old_payload == new_payload:
        return {
            "status": "EXACT_HISTORICAL_V1_PRESERVED",
            "changed_fields": [],
            "issuer_attestation_required": False,
        }
    swapped = all(
        evidence_swap_matches(old_payload[name], new_payload[name])
        for name in RECEIPT_FIELDS
    )
    changed_receipts = [
        name for name in RECEIPT_FIELDS
        if old_payload[name] != new_payload[name]
    ]
    if swapped and changed_receipts:
        return {
            "status": "SNAPSHOT_RECEIPT_REKEY_UNATTESTED",
            "changed_fields": changed_receipts,
            # MUST NOT equate a masked host ID or equal value to real issuer proof.
            "issuer_attestation_required": True,
        }
    return {
        "status": "UNSUPPORTED_SOURCE_RECEIPT_DRIFT",
        "changed_fields": changed_receipts or ["fingerprint"],
        "issuer_attestation_required": True,
    }


def _canonical_manifest_for(project_id: str) -> dict[str, Any]:
    path = FROZEN_ROOT / "projects" / project_id / "source_manifest.json"
    manifest = _json_object(path)
    if manifest.get("project_id") != project_id:
        raise ValueError("canonical frozen original source project mismatch")
    documents = manifest.get("source_documents")
    if type(documents) is not list or not documents:
        raise ValueError("missing canonical original source documents")
    sha = [doc.get("sha256") if type(doc) is dict else None for doc in documents]
    if any(type(x) is not str or len(x) != 64 for x in sha) or len(set(sha)) != len(sha):
        raise ValueError("malformed or duplicate original source digest")
    return manifest


def inspect_signed_v1_replay(
    *,
    archived_run: Mapping[str, Any],
    candidate_run: Mapping[str, Any],
    archived_customer_rows: list[dict[str, Any]],
    candidate_customer_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compare independently seal-verified V1 receipts; never promote authority."""
    old = sealed_source_closed_run_from_dict(archived_run)
    fresh = sealed_source_closed_run_from_dict(candidate_run)
    if old.project_id != fresh.project_id:
        raise ValueError("different source projects cannot share a V1 history")
    manifest = _canonical_manifest_for(old.project_id)
    allowed_sha = {doc["sha256"] for doc in manifest["source_documents"]}
    old_sha = set(old.source_sha256s)
    new_sha = set(fresh.source_sha256s)
    if not old_sha or not new_sha or not old_sha <= allowed_sha or not new_sha <= allowed_sha:
        raise ValueError("sealed V1 source SHA not part of original project manifest")
    # This real verifier validates each archived quantity/customer row, not just
    # their shared top-level quantity IDs.
    old_verified = verify_sealed_customer_output(old, archived_customer_rows)
    if (
        old_verified.customer_row_count != sum(
            bool(_customer_quantity_id(row)) for row in archived_customer_rows
        )
        or old_verified.valid_quantity_count != len(old.quantities)
        or old_verified.abstained_quantity_count != 0
    ):
        raise ValueError("archived V1 customer projection is not the full signed set")
    old_ids = [q.quantity_id for q in old.quantities]
    new_ids = [q.quantity_id for q in fresh.quantities]
    if len(set(old_ids)) != len(old_ids) or len(set(new_ids)) != len(new_ids):
        raise ValueError("duplicate V1 quantity ID")
    old_by_id = {row.quantity_id: row for row in old.quantities}
    new_by_id = {row.quantity_id: row for row in fresh.quantities}
    comparisons = []
    for qid in sorted(old_by_id):
        if qid not in new_by_id:
            comparisons.append({
                "quantity_id": qid,
                "status": "HISTORICAL_QUANTITY_MISSING",
                "changed_fields": ["quantity_id"],
                "issuer_attestation_required": True,
            })
        else:
            comparisons.append({
                "quantity_id": qid,
                **_compare_historical_quantity(old_by_id[qid], new_by_id[qid]),
            })
    for qid in sorted(new_by_id.keys() - old_by_id.keys()):
        comparisons.append({
            "quantity_id": qid,
            "status": "NEW_QUANTITY_REQUIRES_INDEPENDENT_SOURCE_AND_V2_MATCH",
            "changed_fields": [],
            "issuer_attestation_required": True,
        })
    fresh_customer_verified = False
    if candidate_customer_rows is not None:
        actual_verified = verify_sealed_customer_output(fresh, candidate_customer_rows)
        if (
            actual_verified.customer_row_count != sum(
                bool(_customer_quantity_id(row)) for row in candidate_customer_rows
            )
            or actual_verified.valid_quantity_count != sum(not q.abstained for q in fresh.quantities)
        ):
            raise ValueError("candidate V1 customer bijection incomplete")
        fresh_customer_verified = True
    summary: dict[str, int] = {}
    for row in comparisons:
        summary[row["status"]] = summary.get(row["status"], 0) + 1
    source_scope_complete = old_sha == new_sha == allowed_sha
    historical_exact = (
        len(old_by_id) == len(new_by_id)
        and all(row["status"] == "EXACT_HISTORICAL_V1_PRESERVED" for row in comparisons)
    )
    # Commercial score and authorization are ALWAYS out of scope even when
    # the historical V1 bodies are byte-exact and fresh customer rows verify.
    return {
        "schema_version": "gpt3-v1-replay-drift-v1",
        "project_id": old.project_id,
        "publication_status": "DIAGNOSTIC_UNPUBLISHED",
        "official_four_project_coverage_accuracy": None,
        "archived_run_id": old.run_id,
        "candidate_run_id": fresh.run_id,
        "archived_run_fingerprint": old.fingerprint,
        "candidate_run_fingerprint": fresh.fingerprint,
        "historical_quantity_count": len(old_by_id),
        "candidate_quantity_count": len(new_by_id),
        "archived_customer_verified": True,
        "candidate_customer_verified": fresh_customer_verified,
        "original_source_package_complete_in_both_seals": source_scope_complete,
        "historical_v1_byte_exact": historical_exact,
        # An exact V1 comparison is insufficient to authenticate a NEW source
        # issuer/snapshot or complete original package; never grant reuse here.
        "safe_to_reuse_archived_customers_with_candidate": False,
        "source_issuer_scope_attestation_proven": False,
        "new_firm_quantities_authorized": 0,
        "receipt_status_counts": dict(sorted(summary.items())),
        "quantity_differences": comparisons,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archived-v1", type=Path, required=True)
    parser.add_argument("--candidate-v1", type=Path, required=True)
    parser.add_argument("--archived-customers", type=Path, required=True)
    parser.add_argument("--candidate-customers", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    source_paths = [
        args.archived_v1, args.candidate_v1,
        args.archived_customers, args.candidate_customers,
    ]
    output = args.output.resolve()
    if output.is_relative_to(FROZEN_ROOT.resolve()) or any(
        source is not None and output == source.resolve() for source in source_paths
    ):
        raise ValueError("diagnostic may not overwrite original evidence")
    report = inspect_signed_v1_replay(
        archived_run=_json_object(args.archived_v1),
        candidate_run=_json_object(args.candidate_v1),
        archived_customer_rows=_json_customer_rows(args.archived_customers),
        candidate_customer_rows=(
            _json_customer_rows(args.candidate_customers)
            if args.candidate_customers else None
        ),
    )
    _write_readiness_report(
        args.output,
        json.dumps(report, sort_keys=True, indent=2) + "\n",
        protected_roots=(FROZEN_ROOT, *(path.parent for path in source_paths if path is not None)),
    )
    print(json.dumps({
        "publication_status": report["publication_status"],
        "historical_quantity_count": report["historical_quantity_count"],
        "receipt_status_counts": report["receipt_status_counts"],
        "candidate_customer_verified": report["candidate_customer_verified"],
    }, sort_keys=True))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
