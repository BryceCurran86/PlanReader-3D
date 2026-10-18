"""Fail-closed four-project Full Plan V2 signed-source execution ledger.

This runner does not extract plans or create benchmark identities. Inputs must
already be original PDFs plus sealed production, independent identity mapping,
and the corresponding complete customer projection. Missing private packages,
partial runs and incomplete frozen manifests NEVER become zero-scored projects.
Only the existing immutable V2 evaluator may publish a full-suite percentage.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

import importlib
import importlib.util
import sys

from scripts.report_full_plan_v2_readiness import _parse_evidence_json
from tools.gpt3_safe_original_report_output import (
    preflight_new_diagnostic, write_new_diagnostic,
)
from pb_customer_output_verification import (
    _customer_quantity_id,
    verify_sealed_customer_output,
)
from tools.gpt3_signed_v2_family_trade_integrity import (
    require_signed_v2_family_trade_integrity,
)
from pb_source_closed_run_export import sealed_source_closed_run_from_dict
from tools.run_gpt3_original_byte_gated_exact_project import (
    FROZEN_ROOT,
    _original_sha_gate,
    _unchanged_frozen_exact_report,
    _sha256,
)



def _load_unchanged_frozen_modules():
    """Use a private package alias: tests/benchmarks may shadow benchmarks."""
    package_name = "_gpt3_four_project_frozen_v2"
    if package_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            package_name, FROZEN_ROOT / "__init__.py",
            submodule_search_locations=[str(FROZEN_ROOT)],
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("frozen Full Plan V2 package is unavailable")
        package = importlib.util.module_from_spec(spec)
        sys.modules[package_name] = package
        spec.loader.exec_module(package)
    evaluator = importlib.import_module(f"{package_name}.evaluator")
    manifest_io = importlib.import_module(f"{package_name}.manifest_io")
    reconciliation = importlib.import_module(f"{package_name}.sealed_reconciliation")
    return (
        evaluator.evaluate_suite_v2,
        manifest_io.load_suite_manifests,
        reconciliation.identity_map_from_dict,
        reconciliation.reconcile_sealed_run_v2,
    )


(
    evaluate_suite_v2,
    load_suite_manifests,
    identity_map_from_dict,
    reconcile_sealed_run_v2,
) = _load_unchanged_frozen_modules()


def _read_json_without_duplicate_keys(path: Path) -> Any:
    """Reject malformed signed evidence before source/customer verification.

    Reuse the existing strict readiness JSON parser: nested duplicate keys,
    NaN/Infinity, numeric overflow, oversized integers, and pathological
    nesting must not reach the unchanged signed or frozen reconciliation.
    This reads only; it never changes producer signatures or source bytes.
    """
    try:
        return _parse_evidence_json(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        # Preserve the established signed-evidence duplicate-key error
        # contract; the shared readiness parser uses different wording.
        prefix = "duplicate JSON key: "
        if str(exc).startswith(prefix):
            raise ValueError(
                "signed evidence JSON contains duplicate key: "
                + str(exc)[len(prefix):]
            ) from exc
        raise


def _json_object(path: Path) -> dict[str, Any]:
    value = _read_json_without_duplicate_keys(path)
    if type(value) is not dict:
        raise ValueError("signed evidence file must contain a JSON object")
    return value


def _json_customer_rows(path: Path, *, allow_manual: bool = False) -> list[dict[str, Any]]:
    value = _read_json_without_duplicate_keys(path)
    if type(value) is not list or any(type(row) is not dict for row in value):
        raise ValueError("customer projection must be a JSON array of objects")
    # Use the already authoritative V1 identity reader. Persisted commercial
    # rows may carry the quantity ID in structured provenance or strict notes
    # rather than in a top-level optional column. Full provenance validity is
    # checked independently by verify_sealed_customer_output below.
    # Do not count unsourced manual client quote lines as verified physical quantities.
    # Malformed source-owned rows must still be rejected by the V1 customer verifier.
    if any(not _customer_quantity_id(row) and (
        not allow_manual or "quantity_id" in row
        or row.get("commercial_projection_provenance") is not None
    ) for row in value):
        raise ValueError("automated customer row lacks canonical quantity identity")
    return value


def _assert_inputs_unchanged(
    *, manifest: dict[str, Any],
    originals: list[Path],
    expected_hashes: list[str],
    signed_hashes: dict[Path, str],
) -> None:
    """Reject TOCTOU changes to originals or signed artifacts during scoring."""
    source_ok, _, hashes = _original_sha_gate(manifest, originals)
    if not source_ok or hashes != expected_hashes:
        raise ValueError("original source changed during reconciliation")
    if any(_sha256(path) != digest for path, digest in signed_hashes.items()):
        raise ValueError("frozen manifest or signed artifact changed during reconciliation")


def _verify_customer_counts(sealed: Any, verified: Any, customer_rows: list[dict[str, Any]]) -> None:
    """Check signed commercial bijection without treating ABSTAIN as a sale."""
    valid = {
        quantity.quantity_id
        for quantity in sealed.quantities if not quantity.abstained
    }
    abstained = {
        quantity.quantity_id
        for quantity in sealed.quantities if quantity.abstained
    }
    if valid & abstained or len(valid) + len(abstained) != len(sealed.quantities):
        raise ValueError("duplicate or conflicting signed quantity identities")
    # Match the identity source actually accepted by the V1 verifier; a
    # top-level-only lookup would reject valid database-row projections.
    customer_ids = [qid for row in customer_rows
                    if (qid := _customer_quantity_id(row))]
    if (
        verified.project_id != sealed.project_id
        or verified.sealed_quantity_count != len(sealed.quantities)
        or verified.valid_quantity_count != len(valid)
        or verified.abstained_quantity_count != len(abstained)
        or verified.customer_row_count != len(customer_ids)
        or len(customer_ids) != len(set(customer_ids))
        or set(customer_ids) != valid
        or set(verified.verified_quantity_ids) != valid
        or len(verified.verified_quantity_ids) != len(valid)
    ):
        raise ValueError("signed customer projection cardinality or identity mismatch")


def _enforce_cross_project_quantity_uniqueness(
    sealed: Any,
    *, project_id: str,
    seen: dict[str, str],
) -> None:
    """Reject reused sealed quantity identities even across different projects."""
    candidate_ids = tuple(quantity.quantity_id for quantity in sealed.quantities)
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("duplicate quantity identity inside signed project")
    for quantity_id in candidate_ids:
        previous_project = seen.get(quantity_id)
        if previous_project is not None and previous_project != project_id:
            raise ValueError("cross-project signed quantity identity collision")
    for quantity_id in candidate_ids:
        seen[quantity_id] = project_id


def _enforce_mapped_production_family_trade(
    manifest: Any, sealed: Any, mapping: Any,
) -> None:
    """Share exactly the same commercial-semantic veto as project-only score."""
    require_signed_v2_family_trade_integrity(
        verified_items=manifest.verified_items,
        sealed_quantities=sealed.quantities,
        identity_bindings=mapping.bindings,
    )


def _resolve_original_paths(
    source_dir: Path, project_id: str, source_documents: tuple,
) -> tuple[list[Path], list[str]]:
    """Allow SHA-checked flat or project-scoped original packages.

    If both contain distinct source bytes for one manifest document, refuse
    to select either. No candidate is preferred by file order or filename.
    """
    selected: list[Path] = []
    conflicts: list[str] = []
    for doc in source_documents:
        scoped = source_dir / project_id / doc.name
        flat = source_dir / doc.name
        if scoped.is_file() and flat.is_file() and scoped.resolve() != flat.resolve():
            try:
                same = (
                    scoped.stat().st_size == flat.stat().st_size
                    and _sha256(scoped) == _sha256(flat)
                )
            except OSError:
                same = False
            if not same:
                conflicts.append("conflicting_flat_and_scoped_original:" + doc.name)
        selected.append(scoped if scoped.is_file() else flat)
    return selected, conflicts


def build_four_project_evidence_ledger(
    *, source_dir: Path, sealed_dir: Path,
    identity_map_dir: Path, customer_dir: Path,
) -> dict[str, Any]:
    """Inventory all frozen projects, verify supplied original bytes and score safely."""
    manifests = load_suite_manifests(FROZEN_ROOT)
    if len(manifests) != 4:
        raise ValueError("frozen V2 suite must contain exactly four projects")
    eligible = sum(
        1 for manifest in manifests for item in manifest.verified_items
        if item.denominator_eligible
    )
    if eligible != 120:
        raise ValueError("frozen V2 denominator drift: expected existing 120-item suite")

    rows: list[dict[str, Any]] = []
    scored: dict[str, tuple] = {}
    source_hashes_by_project: dict[str, tuple[str, ...]] = {}
    completed_by_project: dict[str, bool] = {}
    seen_signed_quantity_ids: dict[str, str] = {}
    for manifest in manifests:
        project_id = manifest.project_id
        entry: dict[str, Any] = {
            "project_id": project_id,
            "denominator": sum(item.denominator_eligible for item in manifest.verified_items),
            "manifest_status": manifest.status,
            "publication_status": "UNAVAILABLE",
            "source_sha_verified": False,
            "missing_original_source_document_count": 0,
            "missing_original_source_document_roles": [],
            "customer_bijection_verified": False,
            "reconciliation_input_presence_status": "NOT_CHECKED_SOURCE_UNAVAILABLE",
            "missing_signed_reconciliation_artifacts": [],
            "reconciliation_complete": False,
            "reason_codes": [],
            "exact_project_report": None,
            "first_failing_authority_stage": None,
        }
        rows.append(entry)
        original_files, path_conflicts = _resolve_original_paths(
            source_dir, project_id, manifest.source_documents,
        )
        if path_conflicts:
            entry["first_failing_authority_stage"] = "original_source_path_conflict"
            entry["publication_status"] = "CONFLICT"
            entry["reason_codes"] = path_conflicts
            continue
        missing = [
            doc.name for doc, path in zip(manifest.source_documents, original_files)
            if not path.is_file()
        ]
        if missing:
            entry["first_failing_authority_stage"] = "original_source_file_absent"
            missing_names = set(missing)
            entry["missing_original_source_document_count"] = len(missing)
            entry["missing_original_source_document_roles"] = sorted(
                doc.role for doc in manifest.source_documents
                if doc.name in missing_names
            )
            entry["reason_codes"] = [
                "original_source_not_supplied_in_this_execution",
                f"missing_original_file_count:{len(missing)}",
            ]
            continue

        canonical_manifest = FROZEN_ROOT / "projects" / project_id / "source_manifest.json"
        original_manifest = _json_object(canonical_manifest)
        verified, source_reasons, hashes = _original_sha_gate(
            original_manifest, original_files,
        )
        if not verified:
            entry["first_failing_authority_stage"] = "original_source_sha_rejected"
            entry["publication_status"] = "CONFLICT"
            entry["reason_codes"] = source_reasons
            continue
        entry["source_sha_verified"] = True
        entry["source_sha256s"] = hashes

        sealed_path = sealed_dir / f"{project_id}.json"
        identity_path = identity_map_dir / f"{project_id}.identity_map.json"
        customer_path = customer_dir / f"{project_id}.customer_rows.json"
        missing_evidence = [
            label for label, path in (
                ("sealed_run", sealed_path),
                ("identity_map", identity_path),
                ("customer_rows", customer_path),
            ) if not path.is_file()
        ]
        if missing_evidence:
            entry["first_failing_authority_stage"] = "sealed_reconciliation_artifact_absent"
            entry["reconciliation_input_presence_status"] = "MISSING"
            entry["missing_signed_reconciliation_artifacts"] = missing_evidence
            entry["reason_codes"] = [
                "signed_production_evidence_unavailable",
                *("missing:" + name for name in missing_evidence),
            ]
            continue

        entry["reconciliation_input_presence_status"] = "PRESENT_UNVERIFIED"
        first_failure_stage = "signed_artifact_byte_read"
        try:
            signed_hashes = {
                path: _sha256(path)
                for path in (canonical_manifest, sealed_path, identity_path, customer_path)
            }
            first_failure_stage = "sealed_source_run_parse_or_signature"
            sealed = sealed_source_closed_run_from_dict(_json_object(sealed_path))
            first_failure_stage = "independent_identity_map_parse"
            mapping = identity_map_from_dict(_json_object(identity_path))
            first_failure_stage = "signed_source_document_envelope"
            actual_hashes = set(hashes)
            if (
                sealed.project_id != project_id
                or mapping.project_id != project_id
                or len(sealed.source_sha256s) != len(actual_hashes)
                or len(mapping.source_sha256s) != len(actual_hashes)
                or set(sealed.source_sha256s) != actual_hashes
                or set(mapping.source_sha256s) != actual_hashes
            ):
                raise ValueError("source envelope or project identity mismatch")
            first_failure_stage = "customer_projection_parse"
            customer_rows = _json_customer_rows(customer_path, allow_manual=True)
            first_failure_stage = "signed_customer_bijection"
            verified_rows = verify_sealed_customer_output(sealed, customer_rows)
            _verify_customer_counts(sealed, verified_rows, customer_rows)
            first_failure_stage = "source_owned_trade_semantics"
            _enforce_mapped_production_family_trade(manifest, sealed, mapping)
            first_failure_stage = "source_owned_physical_identity_mapping"
            produced = reconcile_sealed_run_v2(
                manifest, sealed.to_dict(), mapping,
            )
            first_failure_stage = "frozen_exact_project_reconciliation"
            exact = _unchanged_frozen_exact_report(
                canonical_manifest, sealed_path, identity_path,
            )
            if (
                exact["project_id"] != project_id
                or exact["source_sha_verified"] is not True
                or exact["reconciliation_complete"] is not True
                or exact["denominator"] != entry["denominator"]
            ):
                raise ValueError("unchanged frozen per-project evaluator rejected evidence")
            first_failure_stage = "original_and_signed_input_immutability"
            _assert_inputs_unchanged(
                manifest=original_manifest,
                originals=original_files,
                expected_hashes=hashes,
                signed_hashes=signed_hashes,
            )
            first_failure_stage = "cross_project_signed_quantity_uniqueness"
            _enforce_cross_project_quantity_uniqueness(
                sealed, project_id=project_id, seen=seen_signed_quantity_ids,
            )
            entry["customer_bijection_verified"] = True
            entry["reconciliation_input_presence_status"] = "INDEPENDENTLY_VERIFIED"
            entry["reconciliation_complete"] = True
            entry["exact_project_report"] = exact
            if manifest.status != "VERIFIED" or not manifest.source_package_complete:
                entry["first_failing_authority_stage"] = "frozen_project_source_universe_incomplete"
                entry["publication_status"] = "DIAGNOSTIC_UNPUBLISHED"
                entry["reason_codes"] = [
                    "frozen_project_source_universe_incomplete",
                    *manifest.reason_codes,
                ]
            else:
                entry["publication_status"] = "PROJECT_VERIFIED"
                entry["reason_codes"] = []
                scored[project_id] = produced
                source_hashes_by_project[project_id] = tuple(sorted(hashes))
                completed_by_project[project_id] = True
        except (OSError, UnicodeError, TypeError, ValueError, RuntimeError, KeyError) as exc:
            entry["first_failing_authority_stage"] = first_failure_stage
            entry["publication_status"] = "CONFLICT"
            entry["reconciliation_input_presence_status"] = "REJECTED"
            entry["reconciliation_complete"] = False
            entry["exact_project_report"] = None
            entry["reason_codes"] = ["signed_evidence_reconciliation_rejected", type(exc).__name__]

    result: dict[str, Any] = {
        "benchmark_id": "full_plan_takeoff_reconciliation_v2",
        "required_project_count": 4,
        "frozen_denominator": eligible,
        "publication_status": "UNPUBLISHED",
        "coverage_accuracy": None,
        "precision_adjusted_accuracy": None,
        "projects": rows,
        "reason_codes": [],
        "official_suite_result": None,
    }
    if len(scored) != 4:
        result["reason_codes"] = ["four_project_signed_source_universe_not_complete"]
        return result
    # The unchanged evaluator fails closed unless the caller supplies BOTH
    # complete original-source SHA receipts and independent reconciliation
    # completion for every scored project. Omitting either silently makes even
    # authentic all-project evidence permanently UNPUBLISHED.
    if (
        set(scored) != set(source_hashes_by_project)
        or set(scored) != set(completed_by_project)
        or any(completed is not True for completed in completed_by_project.values())
    ):
        raise ValueError("verified suite publication receipts are incomplete")
    official = evaluate_suite_v2(
        manifests, scored, required_project_count=4,
        evaluated_source_sha256s_by_project=source_hashes_by_project,
        reconciliation_complete_by_project=completed_by_project,
    )
    result["official_suite_result"] = asdict(official)
    if official.publication_status == "PUBLISHED":
        result["publication_status"] = "PUBLISHED"
        result["coverage_accuracy"] = official.coverage_accuracy
        result["precision_adjusted_accuracy"] = official.precision_adjusted_accuracy
    else:
        result["reason_codes"] = ["unchanged_frozen_evaluator_declined_publication"]
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--sealed-dir", type=Path, required=True)
    parser.add_argument("--identity-map-dir", type=Path, required=True)
    parser.add_argument("--customer-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    protected = (
        FROZEN_ROOT, args.source_dir, args.sealed_dir,
        args.identity_map_dir, args.customer_dir,
    )
    # Reject an existing output or alias BEFORE reading original source PDFs
    # and all four projects' sealed/customer data. No two jobs can race to
    # replace an earlier signed-release decision.
    preflight_new_diagnostic(args.output, protected_roots=protected)
    report = build_four_project_evidence_ledger(
        source_dir=args.source_dir, sealed_dir=args.sealed_dir,
        identity_map_dir=args.identity_map_dir, customer_dir=args.customer_dir,
    )
    write_new_diagnostic(
        args.output,
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        protected_roots=protected,
    )
    print(json.dumps({
        "publication_status": report["publication_status"],
        "frozen_denominator": report["frozen_denominator"],
        "project_statuses": {
            value["project_id"]: value["publication_status"] for value in report["projects"]
        },
    }, sort_keys=True))
    return 0 if report["publication_status"] == "PUBLISHED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
