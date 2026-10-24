"""Exact signed-run comparison across all four projects without false zero scores.

This intentionally does NOT read private PDFs or frozen expected quantities.
Missing signed source execution is UNAVAILABLE, not a score of 0/denominator.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from pb_source_closed_run_export import sealed_source_closed_run_from_dict
from tools.gpt3_safe_original_report_output import (
    preflight_new_diagnostic, write_new_diagnostic,
)
from tools.gpt3_signed_v1_physical_drift import compare_signed_v1_physical_runs
from tools.report_gpt3_four_project_evidence import (
    FROZEN_ROOT, _json_object, load_suite_manifests,
)


def build_four_project_signed_run_drift(
    *, baseline_dir: Path, candidate_dir: Path,
) -> dict:
    """Observe exact physical receipt drift in four original-source handoffs."""
    manifests = load_suite_manifests(FROZEN_ROOT)
    if len(manifests) != 4 or len({m.project_id for m in manifests}) != 4:
        raise ValueError("four distinct frozen project identities are required")
    rows = []
    any_changed = False
    verified_comparisons = 0
    identical = 0
    for manifest in sorted(manifests, key=lambda m: m.project_id):
        project_id = manifest.project_id
        first = baseline_dir / f"{project_id}.json"
        second = candidate_dir / f"{project_id}.json"
        missing = tuple(label for label, path in (
            ("baseline", first), ("candidate", second),
        ) if not path.is_file())
        if missing:
            rows.append({
                "project_id": project_id,
                "comparison_status": "SIGNED_RUN_UNAVAILABLE",
                "missing_sources": list(missing),
                "drift_report": None,
            })
            continue
        original_hashes = (sha256(first.read_bytes()).hexdigest(),
                           sha256(second.read_bytes()).hexdigest())
        old = sealed_source_closed_run_from_dict(_json_object(first))
        new = sealed_source_closed_run_from_dict(_json_object(second))
        if old.project_id != project_id or new.project_id != project_id:
            raise ValueError(
                "signed source handoff project identity does not match its frozen slot"
            )
        diff = compare_signed_v1_physical_runs(old, new)
        if (
            sha256(first.read_bytes()).hexdigest(),
            sha256(second.read_bytes()).hexdigest(),
        ) != original_hashes:
            raise ValueError("signed source handoff bytes changed during suite comparison")
        if diff["comparison_status"] != "NO_SIGNED_SOURCE_QUANTITY_UNIVERSE":
            verified_comparisons += 1
        if diff["comparison_status"] == "BYTE_IDENTICAL_SIGNED_RECEIPTS":
            identical += 1
        else:
            any_changed = True
        rows.append({
            "project_id": project_id,
            "comparison_status": diff["comparison_status"],
            "missing_sources": [],
            "drift_report": diff,
        })
    status = (
        "COMPLETE_EXACT_SIGNED_CONTENT"
        if identical == 4 else
        "SIGNED_RUN_DRIFT" if verified_comparisons == 4 and any_changed else
        "PARTIAL_OR_UNAVAILABLE"
    )
    return {
        "schema_version": "gpt3_four_project_signed_run_drift.v1",
        "publication_status": "UNPUBLISHED",
        "source_authenticated": False,
        "official_v2_accuracy": None,
        "required_projects": 4,
        "verified_signed_run_comparisons": verified_comparisons,
        "unchanged_signed_run_comparisons": identical,
        "comparison_status": status,
        "projects": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-dir", type=Path, required=True)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    protected = (FROZEN_ROOT, args.baseline_dir, args.candidate_dir)
    preflight_new_diagnostic(args.output, protected_roots=protected)
    report = build_four_project_signed_run_drift(
        baseline_dir=args.baseline_dir, candidate_dir=args.candidate_dir,
    )
    write_new_diagnostic(
        args.output,
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        protected_roots=protected,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
