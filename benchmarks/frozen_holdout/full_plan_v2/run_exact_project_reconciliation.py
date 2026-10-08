"""Exact per-project Full Plan V2 reconciliation report.

Reporting only. Production extraction is already sealed before this module sees
it; exact identity binding and the existing V2 evaluator remain authoritative.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import importlib
import importlib.util
import json
from pathlib import Path
import sys

if __package__:
    from pb_source_closed_run_export import sealed_source_closed_run_from_dict
    from .development_scoreboard import evaluate_development_project_v2
    from .manifest_io import load_project_manifest
    from .sealed_reconciliation import (
        identity_map_from_dict,
        reconcile_sealed_run_v2,
    )
else:
    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root))
    from pb_source_closed_run_export import sealed_source_closed_run_from_dict

    # tests/benchmarks is itself a package named "benchmarks", so direct/spec
    # loading must not depend on that top-level package name. Load the actual
    # full_plan_v2 package under a private alias so its relative imports remain
    # correct in both pytest collection and direct CLI execution.
    package_dir = Path(__file__).resolve().parent
    package_name = "_planreader_full_plan_v2_exact_report"
    package_spec = importlib.util.spec_from_file_location(
        package_name,
        package_dir / "__init__.py",
        submodule_search_locations=[str(package_dir)],
    )
    assert package_spec is not None and package_spec.loader is not None
    package_module = sys.modules.get(package_name)
    if package_module is None:
        package_module = importlib.util.module_from_spec(package_spec)
        sys.modules[package_name] = package_module
        package_spec.loader.exec_module(package_module)

    development = importlib.import_module(
        f"{package_name}.development_scoreboard"
    )
    manifest_io = importlib.import_module(f"{package_name}.manifest_io")
    reconciliation = importlib.import_module(
        f"{package_name}.sealed_reconciliation"
    )
    evaluate_development_project_v2 = (
        development.evaluate_development_project_v2
    )
    load_project_manifest = manifest_io.load_project_manifest
    identity_map_from_dict = reconciliation.identity_map_from_dict
    reconcile_sealed_run_v2 = reconciliation.reconcile_sealed_run_v2


def _json_object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def build_exact_project_report(
    *,
    manifest_path: Path,
    sealed_run_path: Path,
    identity_map_path: Path,
    source_root: Path | None = None,
) -> dict:
    manifest = load_project_manifest(manifest_path)
    sealed = sealed_source_closed_run_from_dict(_json_object(sealed_run_path))
    identity_map = identity_map_from_dict(_json_object(identity_map_path))

    # reconcile_sealed_run_v2 independently verifies project identity, source
    # hashes, sealed fingerprints and exact production-object bindings.
    produced = reconcile_sealed_run_v2(
        manifest,
        sealed.to_dict(),
        identity_map,
    )
    result = evaluate_development_project_v2(
        manifest,
        produced,
        execution_present=True,
    )

    expected_hashes = {doc.sha256 for doc in manifest.source_documents}
    run_hashes = set(sealed.source_sha256s)
    map_hashes = set(identity_map.source_sha256s)
    source_envelope_verified = bool(
        run_hashes
        and run_hashes.issubset(expected_hashes)
        and map_hashes
        and map_hashes.issubset(expected_hashes)
    )
    # The envelope only repeats claimed hashes; it cannot prove actual PDF
    # bytes. Reuse the already-merged #2010 source-file proof.
    from scripts.report_full_plan_v2_readiness import _source_sha_proof

    source_sha_verified, source_reasons = _source_sha_proof(
        {"source_documents": [asdict(doc) for doc in manifest.source_documents]},
        source_root,
        manifest.project_id,
    )
    # A frozen benchmark trade category is not production-authenticated trade
    # evidence. The existing sealed schema contains family, not source-backed
    # commercial trade ownership. Keep this report diagnostic until that
    # upstream handoff exists; do not publish evaluator-derived percentages.
    trade_classification_verified = False
    blockers = list(manifest.reason_codes) + list(source_reasons)
    if manifest.status != "VERIFIED":
        blockers.append("frozen_manifest_not_verified")
    if not source_envelope_verified:
        blockers.append("sealed_source_envelope_mismatch")
    if not produced:
        blockers.append("sealed_production_quantities_empty")
    if result.lineage_conflicts:
        blockers.append("sealed_production_lineage_conflict")
    if not trade_classification_verified:
        blockers.append("source_authenticated_trade_classification_missing")
    reconciliation_complete = not blockers

    return {
        "project_id": manifest.project_id,
        "source_sha_verified": source_sha_verified,
        "source_envelope_verified": source_envelope_verified,
        "source_sha256s": sorted(run_hashes),
        "trade_classification_verified": trade_classification_verified,
        "manifest_status": manifest.status,
        "publication_status": "UNPUBLISHED",
        "score_claim": False,
        "reason_codes": sorted(set(blockers)),
        "reconciliation_complete": reconciliation_complete,
        "denominator": result.truth_denominator,
        "matched_within_tolerance": result.matched_within_tolerance,
        "matched_outside_tolerance": result.matched_outside_tolerance,
        "missed": result.missed,
        "partial": result.partial,
        "unresolved": result.unresolved,
        "unsupported_extra": result.unsupported_extra,
        "coverage_accuracy": None,
        "precision_adjusted_accuracy": None,
        "abstained_outputs": result.abstained_outputs,
        "lineage_conflicts": result.lineage_conflicts,
        "produced_items": [asdict(item) for item in produced],
        "sealed_run_id": sealed.run_id,
        "sealed_run_fingerprint": sealed.fingerprint,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write one exact Full Plan V2 project reconciliation report."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--sealed-run", type=Path, required=True)
    parser.add_argument("--identity-map", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=None, help="Real source PDF root, organised as <root>/<project_id>/<manifest filename>.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    report = build_exact_project_report(
        manifest_path=args.manifest,
        sealed_run_path=args.sealed_run,
        identity_map_path=args.identity_map,
        source_root=args.source_root,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
