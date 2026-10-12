"""Unpublished exact-ID delta for original-source opening diagnostic JSON.

Does not authenticate PDF bytes, host identity, or benchmark quantities.
Never substitutes aggregate counts for original source-membership parity.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.report_full_plan_v2_readiness import _write_readiness_report


FROZEN_V2_ROOT = Path(__file__).resolve().parents[1] / "benchmarks" / "frozen_holdout" / "full_plan_v2"


_NATIVE_MEMBERS = ("unresolved_candidate_ids", "unresolved_observation_ids")
_SEMANTIC_MEMBERS = (
    "visible_observation_ids",
    "conflict_observation_ids",
    "residual_visible_observation_ids",
    "opening_support_observation_ids",
    "physical_opening_record_ids",
    "representative_observation_ids",
)
_PROTECTED = (
    "canonical_openings", "opening_bindings", "host_frame_traces",
    "resolved_host_frame_evidence", "opening_label_semantic_traces",
    "opening_figured_label_traces", "source_owned_wall_scopes",
)


def _unique_ids(value: object, path: str) -> set[str]:
    if (
        type(value) is not list
        or any(type(v) is not str or not v or v != v.strip() for v in value)
        or len(set(value)) != len(value)
    ):
        raise ValueError(f"invalid or duplicate original IDs: {path}")
    return set(value)


def _pages(report: dict) -> dict[str, dict]:
    rows = report.get("native_candidate_closures")
    if type(rows) is not list:
        raise ValueError("missing native_candidate_closures")
    result = {}
    for row in rows:
        if type(row) is not dict:
            raise ValueError("malformed native closure")
        page = row.get("page_id")
        if type(page) is not str or not page or page != page.strip() or page in result:
            raise ValueError("invalid or duplicate native source page")
        result[page] = row
    return result


def compare_source_membership(before: dict, after: dict) -> dict:
    """Report exact original source evidence changes; never grant a score."""
    if type(before) is not dict or type(after) is not dict:
        raise ValueError("reports must be JSON objects")
    source_sha = before.get("source_sha256")
    if (
        type(source_sha) is not str or len(source_sha) != 64
        or any(c not in "0123456789abcdef" for c in source_sha)
    ):
        raise ValueError("invalid source SHA-256")
    for field in (
        "source_sha256", "revision_id", "snapshot_id",
        "selected_geometry_page_ids", "all_source_pages_requested",
        "primitive_safety_cap",
    ):
        if field not in before or field not in after or before[field] != after[field]:
            raise ValueError(f"incomparable original source scope: {field}")
    if type(before["primitive_safety_cap"]) is not int or before["primitive_safety_cap"] != 20_000:
        raise ValueError("source primitive safety cap must remain 20000")

    changes = []

    def compare_ids(path: str, old: object, new: object) -> None:
        a, b = _unique_ids(old, path + ".before"), _unique_ids(new, path + ".after")
        added, removed = sorted(b - a), sorted(a - b)
        if added or removed:
            changes.append({
                "path": path, "before_count": len(a), "after_count": len(b),
                "added_count": len(added), "removed_count": len(removed),
                "added_ids_sample": added[:8], "removed_ids_sample": removed[:8],
            })

    def compare_value(path: str, old: object, new: object) -> None:
        if old != new:
            changes.append({"path": path, "changed": True})

    old_pages, new_pages = _pages(before), _pages(after)
    compare_ids("native_candidate_closures.pages", list(old_pages), list(new_pages))
    for page in sorted(set(old_pages) & set(new_pages)):
        a, b = old_pages[page], new_pages[page]
        for field in _NATIVE_MEMBERS:
            compare_ids(f"native_candidate_closures[{page}].{field}", a.get(field), b.get(field))
        for field in ("raw_candidate_count", "resolved_candidate_count",
                      "candidate_universe_complete", "status", "reason_codes"):
            compare_value(f"native_candidate_closures[{page}].{field}",
                          a.get(field), b.get(field))

    old_sem, new_sem = before.get("semantic_inventory"), after.get("semantic_inventory")
    if type(old_sem) is not dict or type(new_sem) is not dict:
        raise ValueError("missing semantic source inventory")
    a, b = old_sem.get("record"), new_sem.get("record")
    if type(a) is not dict or type(b) is not dict:
        raise ValueError("missing semantic source record")
    for field in _SEMANTIC_MEMBERS:
        compare_ids("semantic_inventory.record." + field, a.get(field), b.get(field))
    for field in ("record_id", "decision_scope_id", "snapshot_id", "revision_id",
                  "physical_opening_universe_complete", "structural_enumeration_complete",
                  "reason_codes"):
        compare_value("semantic_inventory.record." + field, a.get(field), b.get(field))
    for field in _PROTECTED:
        if field not in before or field not in after:
            raise ValueError(f"missing protected original source authority: {field}")
        compare_value(field, before[field], after[field])

    return {
        "status": "IDENTICAL_DIAGNOSTIC" if not changes else "SOURCE_MEMBERSHIP_DRIFT_UNPUBLISHED",
        "parity_pass": not changes,
        "source_sha256": source_sha,
        "benchmark_score_granted": False,
        "benchmark_accuracy": None,
        "source_authenticated_independently": False,
        "comparison_only": True,
        "changes": changes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = compare_source_membership(
            json.loads(args.baseline.read_text(encoding="utf-8")),
            json.loads(args.candidate.read_text(encoding="utf-8")),
        )
    except (ValueError, TypeError, KeyError) as exc:
        parser.error(str(exc))
    _write_readiness_report(
        args.output, json.dumps(report, indent=2, sort_keys=True) + "\n",
        protected_roots=(args.baseline, args.candidate, FROZEN_V2_ROOT),
    )
    print(json.dumps({"parity_pass": report["parity_pass"],
                      "changed_paths": [row["path"] for row in report["changes"]]},
                     sort_keys=True))
    return 0 if report["parity_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
