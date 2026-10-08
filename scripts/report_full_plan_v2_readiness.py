"""Unpublished Full Plan V2 readiness diagnostics; never a benchmark score.

Only the frozen evaluator can publish an accuracy score. Missing production files
are reported as missing, never converted to empty successful extractions.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

# Resolve the repository's benchmark package before any site-package namesake.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) in sys.path:
    sys.path.remove(str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT))

from benchmarks.frozen_holdout.full_plan_v2.evaluator import PROJECT_VERIFIED
from benchmarks.frozen_holdout.full_plan_v2.manifest_io import (
    load_produced_items,
    load_suite_manifests,
)

DEFAULT_ROOT = Path("benchmarks/frozen_holdout/full_plan_v2")


def diagnostic_report(root: Path, produced_root: Path) -> dict:
    """Report readiness without evaluating or exposing unpublished accuracy."""
    manifests = load_suite_manifests(root)
    projects = []
    for manifest in manifests:
        path = produced_root / manifest.project_id / "produced_items.json"
        exists = path.is_file()
        produced = load_produced_items(path) if exists else ()
        ids = [item.quantity_id for item in produced]
        duplicate_ids = sorted(
            key for key, count in Counter(ids).items() if count > 1
        )
        denominator = sum(item.denominator_eligible for item in manifest.verified_items)
        blockers = list(manifest.reason_codes)
        if manifest.status != PROJECT_VERIFIED:
            blockers.insert(0, "frozen_manifest_not_verified")
        if not exists:
            blockers.append("production_items_missing")
        if duplicate_ids:
            blockers.append("duplicate_produced_quantity_ids")
        if any(not item.lineage_ok for item in produced):
            blockers.append("production_lineage_conflict")
        if not produced and exists:
            blockers.append("empty_produced_items_unverified")
        projects.append({
            "project_id": manifest.project_id,
            "manifest_status": manifest.status,
            "denominator": denominator,
            "produced_file_present": exists,
            "produced_count": len(produced) if exists else None,
            "lineage_conflict_count": sum(not item.lineage_ok for item in produced) if exists else None,
            "abstention_count": sum(item.abstained for item in produced) if exists else None,
            "duplicate_quantity_ids": duplicate_ids,
            "source_sha_verified": False,
            "reconciliation_complete": False,
            "blockers": sorted(set(blockers)),
            "coverage_accuracy": None,
            "precision_adjusted_accuracy": None,
        })
    return {
        "report_type": "FULL_PLAN_V2_READINESS_DIAGNOSTIC",
        "publication_status": "UNPUBLISHED",
        "score_claim": False,
        "required_project_count": len(manifests),
        "projects": projects,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--produced-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = diagnostic_report(args.benchmark_root, args.produced_root)
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
