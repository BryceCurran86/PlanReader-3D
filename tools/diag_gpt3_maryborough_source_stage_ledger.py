"""Read-only Maryborough source host/frame first-failure receipt.

Consumes the ORIGINAL-PDF workflow's production summary and per-opening
composition, never gold/denominator/evaluator or inferred geometry.
Overlapping reason incidences are never counted as independent openings.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re

from scripts.report_full_plan_v2_readiness import _object, _write_readiness_report

_FROZEN_ROOT = Path(__file__).resolve().parents[1] / "benchmarks/frozen_holdout/full_plan_v2"


def _reason_codes(row: dict, context: str) -> list[str]:
    reasons = row.get("reason_codes")
    if (
        type(reasons) is not list
        or any(type(r) is not str or not r or r != r.strip() for r in reasons)
        or len(reasons) != len(set(reasons))
    ):
        raise ValueError(f"{context}: invalid or duplicate source reason codes")
    return reasons


def _indexed_source_rows(rows: object, family: str) -> dict[str, dict]:
    if type(rows) is not list:
        raise ValueError(f"{family}: missing source receipt array")
    result = {}
    for row in rows:
        if type(row) is not dict:
            raise ValueError(f"{family}: invalid source receipt")
        identity = row.get("opening_identity_id")
        if (
            type(identity) is not str or not identity
            or identity != identity.strip() or identity in result
        ):
            raise ValueError(f"{family}: duplicated or invalid physical opening identity")
        receipt = row.get("record_id")
        host = row.get("host_wall_id")
        if (
            (receipt is not None and (type(receipt) is not str or not receipt.strip()))
            or (host is not None and (type(host) is not str or not host.strip()))
        ):
            raise ValueError(f"{family}: malformed physical receipt or wall identity")
        if receipt is not None and host is None:
            raise ValueError(f"{family}: resolved receipt missing authenticated host")
        status = row.get("status")
        if type(status) is not str or not status.strip():
            raise ValueError(f"{family}: missing physical status")
        _reason_codes(row, family)
        result[identity] = row
    return result


def build_maryborough_source_stage_ledger(summary: dict, composition: dict) -> dict:
    """Report first unmet source authority; no commercial or V2 score."""
    if type(summary) is not dict or type(composition) is not dict:
        raise ValueError("original summary and composition must be JSON objects")
    sha = summary.get("source_sha256")
    if (
        type(sha) is not str or re.fullmatch(r"[0-9a-f]{64}", sha) is None
        or composition.get("source_sha256") != sha
    ):
        raise ValueError("composition does not share exact production source SHA")
    project = summary.get("project_id")
    if type(project) is not str or not project:
        raise ValueError("invalid original project identity")
    if summary.get("family_group") != "core":
        raise ValueError("source ledger requires the original CORE handoff")
    if summary.get("benchmark_score_granted") is not False:
        raise ValueError("source summary cannot already grant a benchmark score")

    bindings = _indexed_source_rows(composition.get("bindings"), "bindings")
    frames = _indexed_source_rows(composition.get("frames"), "frames")
    if set(bindings) != set(frames):
        raise ValueError("opening host and frame universes differ")
    binding_resolved = sum(row["record_id"] is not None for row in bindings.values())
    frame_resolved = sum(row["record_id"] is not None for row in frames.values())
    for kind, rows, resolved in (
        ("binding", bindings, binding_resolved),
        ("frame", frames, frame_resolved),
    ):
        if (
            type(composition.get(f"{kind}_count")) is not int
            or composition[f"{kind}_count"] != len(rows)
            or type(composition.get(f"{kind}_resolved_count")) is not int
            or composition[f"{kind}_resolved_count"] != resolved
        ):
            raise ValueError(f"{kind}: source summary count contradicts receipts")
        counts = dict(sorted(Counter(
            reason for row in rows.values() for reason in _reason_codes(row, kind)
        ).items()))
        if composition.get(f"{kind}_reason_counts") != counts:
            raise ValueError(f"{kind}: source reason incidence inventory inconsistent")

    first_gates: Counter[str] = Counter()
    stage_rows: list[dict] = []
    for identity in sorted(bindings):
        binding, frame = bindings[identity], frames[identity]
        if frame["record_id"] is not None and binding["record_id"] is None:
            raise ValueError("source frame resolves an unhosted opening")
        if (
            frame["record_id"] is not None
            and frame["host_wall_id"] != binding["host_wall_id"]
        ):
            raise ValueError("resolved source host and frame disagree")
        if binding["record_id"] is None:
            stage = "HOST_BINDING_UNPROVEN"
            reasons = _reason_codes(binding, "bindings")
        elif frame["record_id"] is None:
            stage = "COMPLETE_HOST_FRAME_UNPROVEN"
            reasons = _reason_codes(frame, "frames")
        else:
            stage = "HOST_AND_FRAME_SOURCE_SUPPORTED_UNSCORED"
            reasons = []
        first_gates[stage] += 1
        stage_rows.append({
            "opening_identity_id": identity,
            "source_page_id": binding.get("page_id"),
            "stage": stage,
            "first_stage_reason_codes": sorted(reasons),
            "host_binding_record_id": binding["record_id"],
            "frame_record_id": frame["record_id"],
        })

    family_counts = summary.get("family_counts")
    if (
        type(family_counts) is not dict
        or any(type(v) is not int or v < 0 for v in family_counts.values())
    ):
        raise ValueError("invalid source family quantity inventory")
    if summary.get("claim_status") not in ("abstained", "conflict", "corroborated"):
        raise ValueError("unknown source claim status")
    return {
        "project_id": project,
        "source_sha256": sha,
        "publication_status": "SOURCE_STAGE_DIAGNOSTIC_BENCHMARK_UNPUBLISHED",
        "original_source_independently_verified": False,
        "benchmark_score_granted": False,
        "benchmark_accuracy": None,
        "frozen_v2_reconciliation_complete": False,
        "source_claim_status": summary["claim_status"],
        "source_family_quantity_counts_unscored": dict(sorted(family_counts.items())),
        "opening_universe_size": len(bindings),
        "host_bindings_source_resolved": binding_resolved,
        "frames_source_resolved": frame_resolved,
        "first_unproved_stage_counts": dict(sorted(first_gates.items())),
        "binding_reason_incidence_counts_overlapping": composition["binding_reason_counts"],
        "frame_reason_incidence_counts_overlapping": composition["frame_reason_counts"],
        "reason_incidences_are_not_disjoint_object_counts": True,
        "opening_first_stage_rows": stage_rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--production-summary", required=True, type=Path)
    parser.add_argument("--composition", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    report = build_maryborough_source_stage_ledger(
        _object(args.production_summary), _object(args.composition),
    )
    _write_readiness_report(
        args.output, json.dumps(report, sort_keys=True, indent=2) + "\n",
        protected_roots=(_FROZEN_ROOT, args.production_summary, args.composition),
    )
    print(json.dumps({
        "project_id": report["project_id"],
        "first_unproved_stage_counts": report["first_unproved_stage_counts"],
        "benchmark_score_granted": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
