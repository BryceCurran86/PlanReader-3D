"""Compare two original-source Maryborough authority ledgers, without scoring.

A matching original PDF SHA does not prove opening-identity completeness.
Never treat a changed physical candidate universe as improved accuracy.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re

from scripts.report_full_plan_v2_readiness import _object, _write_readiness_report

_FROZEN_ROOT = Path(__file__).resolve().parents[1] / "benchmarks" / "frozen_holdout" / "full_plan_v2"
_PROJECT = "au_qld_maryborough_service_station"
_STAGE_ORDER = {
    "HOST_BINDING_UNPROVEN": 0,
    "COMPLETE_HOST_FRAME_UNPROVEN": 1,
    "HOST_AND_FRAME_SOURCE_SUPPORTED_UNSCORED": 2,
}


def _ledger_rows(ledger: dict, side: str) -> dict[str, dict]:
    if type(ledger) is not dict:
        raise ValueError(f"{side}: source ledger must be a JSON object")
    if ledger.get("project_id") != _PROJECT:
        raise ValueError(f"{side}: wrong source project identity")
    sha = ledger.get("source_sha256")
    if type(sha) is not str or re.fullmatch(r"[0-9a-f]{64}", sha) is None:
        raise ValueError(f"{side}: invalid source SHA receipt")
    if (
        ledger.get("publication_status") != "SOURCE_STAGE_DIAGNOSTIC_BENCHMARK_UNPUBLISHED"
        or ledger.get("benchmark_score_granted") is not False
        or ledger.get("benchmark_accuracy") is not None
        or ledger.get("frozen_v2_reconciliation_complete") is not False
        or ledger.get("original_source_independently_verified") is not False
    ):
        raise ValueError(f"{side}: forged benchmark/source authority claim")
    rows = ledger.get("opening_first_stage_rows")
    if type(rows) is not list:
        raise ValueError(f"{side}: missing original first-stage rows")
    indexed = {}
    counts: Counter[str] = Counter()
    for row in rows:
        if type(row) is not dict:
            raise ValueError(f"{side}: malformed physical opening row")
        identity = row.get("opening_identity_id")
        stage = row.get("stage")
        if (
            type(identity) is not str or not identity or identity != identity.strip()
            or identity in indexed
            or type(stage) is not str or stage not in _STAGE_ORDER
        ):
            raise ValueError(f"{side}: invalid or duplicated physical opening identity")
        reasons = row.get("first_stage_reason_codes")
        if (
            type(reasons) is not list
            or any(type(v) is not str or not v or v != v.strip() for v in reasons)
            or reasons != sorted(set(reasons))
        ):
            raise ValueError(f"{side}: invalid source first-stage reason witnesses")
        binding = row.get("host_binding_record_id")
        frame = row.get("frame_record_id")
        for val in (binding, frame):
            if val is not None and (type(val) is not str or not val.strip()):
                raise ValueError(f"{side}: malformed source binding/frame receipt")
        if stage == "HOST_BINDING_UNPROVEN" and (binding is not None or frame is not None):
            raise ValueError(f"{side}: host-unproven row has a positive receipt")
        if stage == "COMPLETE_HOST_FRAME_UNPROVEN" and (binding is None or frame is not None):
            raise ValueError(f"{side}: incomplete frame row contradicts receipts")
        if stage == "HOST_AND_FRAME_SOURCE_SUPPORTED_UNSCORED" and (binding is None or frame is None):
            raise ValueError(f"{side}: source-supported frame has no receipt")
        indexed[identity] = row
        counts[stage] += 1
    if (
        type(ledger.get("opening_universe_size")) is not int
        or ledger["opening_universe_size"] != len(indexed)
        or type(ledger.get("host_bindings_source_resolved")) is not int
        or ledger["host_bindings_source_resolved"] != (
            counts["COMPLETE_HOST_FRAME_UNPROVEN"]
            + counts["HOST_AND_FRAME_SOURCE_SUPPORTED_UNSCORED"]
        )
        or type(ledger.get("frames_source_resolved")) is not int
        or ledger["frames_source_resolved"] != counts["HOST_AND_FRAME_SOURCE_SUPPORTED_UNSCORED"]
        or ledger.get("first_unproved_stage_counts") != dict(counts)
    ):
        raise ValueError(f"{side}: source-stage counts contradict physical identity rows")
    return indexed


def compare_maryborough_source_stages(baseline: dict, candidate: dict) -> dict:
    """Exact physical-ID stage changes only; always not benchmark accuracy."""
    old, new = _ledger_rows(baseline, "baseline"), _ledger_rows(candidate, "candidate")
    if baseline["source_sha256"] != candidate["source_sha256"]:
        raise ValueError("different original source SHA: stage runs not comparable")
    shared = sorted(old.keys() & new.keys())
    gained = sorted(new.keys() - old.keys())
    lost = sorted(old.keys() - new.keys())
    universe_unchanged = not (gained or lost)
    advanced, regressed, unchanged, changed_receipts = [], [], [], []
    for identity in shared:
        a, b = old[identity], new[identity]
        old_level, new_level = _STAGE_ORDER[a["stage"]], _STAGE_ORDER[b["stage"]]
        record = {
            "opening_identity_id": identity, "before": a["stage"],
            "after": b["stage"],
            "before_reasons": a["first_stage_reason_codes"],
            "after_reasons": b["first_stage_reason_codes"],
        }
        if new_level > old_level:
            advanced.append(record)
        elif new_level < old_level:
            regressed.append(record)
        else:
            unchanged.append(identity)
        if (
            a["host_binding_record_id"] != b["host_binding_record_id"]
            or a["frame_record_id"] != b["frame_record_id"]
        ):
            changed_receipts.append(identity)
    return {
        "project_id": _PROJECT,
        "source_sha256": baseline["source_sha256"],
        "publication_status": "SOURCE_STAGE_DELTA_BENCHMARK_UNPUBLISHED",
        "source_authenticated_independently": False,
        "benchmark_score_granted": False,
        "benchmark_accuracy": None,
        "frozen_v2_reconciliation_complete": False,
        "physical_candidate_universe_comparable": universe_unchanged,
        "source_stage_improvement_comparable": universe_unchanged and bool(advanced)
            and not regressed,
        "note": (
            "Stage advancement only, never construction quantity or benchmark matches"
            if universe_unchanged else
            "Source candidate universe changed; cannot claim stage accuracy improvement"
        ),
        "before_physical_openings": len(old),
        "after_physical_openings": len(new),
        "added_physical_ids": gained,
        "removed_physical_ids": lost,
        "advanced_count": len(advanced),
        "regressed_count": len(regressed),
        "unchanged_stage_count": len(unchanged),
        "stage_advanced": advanced,
        "stage_regressed": regressed,
        "changed_positive_receipt_ids": changed_receipts,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = compare_maryborough_source_stages(
        _object(args.before), _object(args.after),
    )
    _write_readiness_report(
        args.output, json.dumps(result, indent=2, sort_keys=True) + "\n",
        protected_roots=(_FROZEN_ROOT, args.before, args.after),
    )
    print(json.dumps({
        "candidate_universe_comparable": result["physical_candidate_universe_comparable"],
        "advanced_count": result["advanced_count"],
        "regressed_count": result["regressed_count"],
        "benchmark_score_granted": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
