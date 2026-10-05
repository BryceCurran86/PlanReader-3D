"""Exact per-project Full Plan V2 reconciliation report.

Reporting only. Production extraction is already sealed before this module sees
it; exact identity binding and the existing V2 evaluator remain authoritative.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from pb_source_closed_run_export import sealed_source_closed_run_from_dict

from .development_scoreboard import evaluate_development_project_v2
from .manifest_io import load_project_manifest
from .sealed_reconciliation import (
    identity_map_from_dict,
    reconcile_sealed_run_v2,
)


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
    source_sha_verified = bool(
        run_hashes
        and run_hashes.issubset(expected_hashes)
        and map_hashes
        and map_hashes.issubset(expected_hashes)
    )

    return {
        "project_id": manifest.project_id,
        "source_sha_verified": source_sha_verified,
        "source_sha256s": sorted(run_hashes),
        "reconciliation_complete": True,
        "denominator": result.truth_denominator,
        "matched_within_tolerance": result.matched_within_tolerance,
        "matched_outside_tolerance": result.matched_outside_tolerance,
        "missed": result.missed,
        "partial": result.partial,
        "unresolved": result.unresolved,
        "unsupported_extra": result.unsupported_extra,
        "coverage_accuracy": result.observed_accuracy,
        "precision_adjusted_accuracy": result.precision_adjusted_accuracy,
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
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    report = build_exact_project_report(
        manifest_path=args.manifest,
        sealed_run_path=args.sealed_run,
        identity_map_path=args.identity_map,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
