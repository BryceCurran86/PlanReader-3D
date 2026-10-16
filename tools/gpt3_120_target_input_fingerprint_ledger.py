"""Post-reconciliation 120-target inventory and no-repeat input fingerprint.

This file is reporting ONLY. It does not extract source PDFs, score a missing
project, call the evaluator or construct benchmark/physical-object mappings.
An UNPUBLISHED input yields NO target-level accuracy claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from tools.report_gpt3_four_project_evidence import (
    FROZEN_ROOT, load_suite_manifests, _json_object,
)
from scripts.report_full_plan_v2_readiness import _write_readiness_report

_SHA = re.compile(r"^[0-9a-f]{40}$")
_V2_STATES = frozenset((
    "MATCHED_WITHIN_TOLERANCE", "MATCHED_OUTSIDE_TOLERANCE", "MISSED",
    "PARTIAL", "UNRESOLVED",
))


def _digest_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _frozen_input_digests(manifests: tuple) -> dict[str, str]:
    paths = [
        FROZEN_ROOT / "manifest.json",
        FROZEN_ROOT / "evaluator.py",
        FROZEN_ROOT / "sealed_reconciliation.py",
    ]
    for manifest in manifests:
        root = FROZEN_ROOT / "projects" / manifest.project_id
        paths.extend((root / "source_manifest.json", root / "reference_takeoff.json"))
    return {
        str(path.relative_to(FROZEN_ROOT)): _digest_bytes(path.read_bytes())
        for path in paths
    }


def _exact_official_items(report: Mapping[str, Any], manifests: tuple) -> dict:
    """Copy post-evaluator item states ONLY from a complete published suite."""
    if report.get("publication_status") != "PUBLISHED":
        return {}
    if any(m.status != "VERIFIED" or not m.source_package_complete for m in manifests):
        raise ValueError("official publication requires VERIFIED frozen project manifests")
    official = report.get("official_suite_result")
    if not isinstance(official, dict) or official.get("publication_status") != "PUBLISHED":
        raise ValueError("published claim lacks authoritative official suite report")
    if official.get("denominator") != 120:
        raise ValueError("published suite denominator mismatch")
    project_rows = official.get("project_results")
    if not isinstance(project_rows, list) or len(project_rows) != 4:
        raise ValueError("published suite project result universe incomplete")
    official_by_id = {}
    for row in project_rows:
        if not isinstance(row, dict) or type(row.get("project_id")) is not str:
            raise ValueError("malformed official project result")
        if row["project_id"] in official_by_id:
            raise ValueError("duplicate official project result")
        official_by_id[row["project_id"]] = row
    expected_ids = {m.project_id for m in manifests}
    if set(official_by_id) != expected_ids:
        raise ValueError("official suite project identities differ from frozen suite")

    by_target = {}
    for manifest in manifests:
        row = official_by_id[manifest.project_id]
        expected = {item.item_id for item in manifest.verified_items if item.denominator_eligible}
        results = row.get("item_results")
        if (
            row.get("denominator") != len(expected)
            or row.get("manifest_status") != "VERIFIED"
            or not isinstance(results, list)
            or len(results) != len(expected)
        ):
            raise ValueError("official project item universe incomplete")
        for result in results:
            if not isinstance(result, dict) or type(result.get("item_id")) is not str:
                raise ValueError("malformed official target result")
            key = (manifest.project_id, result["item_id"])
            if (
                result["item_id"] not in expected
                or key in by_target
                or result.get("state") not in _V2_STATES
            ):
                raise ValueError("unknown, duplicate or invalid official target result")
            by_target[key] = result
        if {target for project, target in by_target if project == manifest.project_id} != expected:
            raise ValueError("official target identity gap")
    if len(by_target) != 120:
        raise ValueError("official target count mismatch")
    return by_target


def build_120_target_ledger(
    report: Mapping[str, Any],
    *, owner_receipt: Mapping[str, Any] | None = None,
    producer_head: str | None = None,
    previous_input_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Create an audit inventory, not an independent scoring result."""
    manifests = load_suite_manifests(FROZEN_ROOT)
    if (
        len(manifests) != 4
        or report.get("benchmark_id") != "full_plan_takeoff_reconciliation_v2"
        or report.get("required_project_count") != 4
        or report.get("frozen_denominator") != 120
        or report.get("publication_status") not in ("PUBLISHED", "UNPUBLISHED")
    ):
        raise ValueError("not the exact four-project frozen V2 evidence report")
    projects = report.get("projects")
    if not isinstance(projects, list) or len(projects) != 4:
        raise ValueError("four distinct project evidence reports required")
    by_project = {}
    for project in projects:
        if not isinstance(project, dict) or type(project.get("project_id")) is not str:
            raise ValueError("invalid project evidence")
        if project["project_id"] in by_project:
            raise ValueError("duplicate project evidence")
        by_project[project["project_id"]] = project
    if set(by_project) != {m.project_id for m in manifests}:
        raise ValueError("unexpected or missing project evidence")
    if producer_head is not None and (
        type(producer_head) is not str or not _SHA.fullmatch(producer_head)
    ):
        raise ValueError("producer head must be an exact lowercase 40-char commit")
    if owner_receipt is not None and not isinstance(owner_receipt, dict):
        raise ValueError("owner run receipt must be a JSON object")
    owner_statuses: dict[str, str] = {}
    if owner_receipt is not None:
        owner_rows = owner_receipt.get("project_handoffs")
        if not isinstance(owner_rows, list) or len(owner_rows) != 4:
            raise ValueError("owner receipt must include four handoff outcomes")
        if producer_head is not None and owner_receipt.get("repo_head") != producer_head:
            raise ValueError("producer commit conflicts with owner-run receipt")
        for row in owner_rows:
            if (
                not isinstance(row, dict)
                or type(row.get("project_id")) is not str
                or type(row.get("status")) is not str
                or row["project_id"] in owner_statuses
            ):
                raise ValueError("duplicate or invalid owner handoff")
            owner_statuses[row["project_id"]] = row["status"]
        if set(owner_statuses) != set(by_project):
            raise ValueError("owner run projects mismatch frozen suite")

    official_items = _exact_official_items(report, manifests)
    if bool(official_items):
        if any(
            by_project[m.project_id].get("publication_status") != "PROJECT_VERIFIED"
            or by_project[m.project_id].get("customer_bijection_verified") is not True
            or by_project[m.project_id].get("source_sha_verified") is not True
            or by_project[m.project_id].get("reconciliation_complete") is not True
            for m in manifests
        ):
            raise ValueError("published per-target states without verified customer/source gates")
    else:
        if report.get("publication_status") == "PUBLISHED":
            raise ValueError("published report missing 120 evaluated targets")

    items = []
    for manifest in manifests:
        project = by_project[manifest.project_id]
        eligible = [item for item in manifest.verified_items if item.denominator_eligible]
        if project.get("denominator") != len(eligible):
            raise ValueError("project denominator differs from frozen manifest")
        reasons = project.get("reason_codes")
        if not isinstance(reasons, list) or any(type(x) is not str for x in reasons):
            raise ValueError("invalid project-level failure reason codes")
        for item in eligible:
            result = official_items.get((manifest.project_id, item.item_id))
            items.append({
                "project_id": manifest.project_id,
                "item_id": item.item_id,
                "trade_category": item.trade_category,
                "unit": item.unit,
                "evaluation_state": result["state"] if result else "NOT_EVALUATED",
                "produced_quantity_id": result.get("produced_quantity_id") if result else None,
                # A project-level blockage is NOT an exact target-level failure.
                "first_target_authority_failure": "NOT_DIAGNOSED",
                "project_evidence_status": project.get("publication_status"),
                "project_gate_reasons": list(reasons),
                "owner_handoff_status": owner_statuses.get(manifest.project_id),
            })
    if len(items) != 120 or len({(x["project_id"], x["item_id"]) for x in items}) != 120:
        raise ValueError("frozen 120-target inventory is not a unique 120-item set")
    source_shas = {
        manifest.project_id: sorted(doc.sha256 for doc in manifest.source_documents)
        for manifest in manifests
    }
    frozen_shas = _frozen_input_digests(manifests)
    identity = {
        "schema_version": "gpt3-120-target-input-fingerprint-v1",
        "producer_head": producer_head,
        "frozen_file_sha256s": frozen_shas,
        "source_sha256s_by_project": source_shas,
        "reported_reconciliation": report,
        "owner_execution_receipt": owner_receipt,
    }
    digest = _digest_bytes(json.dumps(
        identity, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8"))
    comparable = producer_head is not None and owner_receipt is not None
    return {
        "schema_version": "gpt3-120-target-ledger-v1",
        "publication_status": report["publication_status"],
        "official_coverage_accuracy": report.get("coverage_accuracy") if official_items else None,
        "official_precision_adjusted_accuracy": (
            report.get("precision_adjusted_accuracy") if official_items else None
        ),
        "target_count": 120,
        "evaluated_target_count": len(official_items),
        "not_evaluated_target_count": 120 - len(official_items),
        "producer_head": producer_head,
        "source_sha256s_by_project": source_shas,
        "frozen_file_sha256s": frozen_shas,
        "input_fingerprint": digest,
        "repeat_evaluation_advice": (
            "UNCHANGED_PRODUCER_SOURCE_SCORING_INPUTS_DO_NOT_RERUN"
            if comparable and digest == previous_input_fingerprint
            else "CHANGED_INPUTS_OR_UNPROVEN_COMPARISON"
        ),
        "items": items,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence-report", required=True, type=Path)
    p.add_argument("--owner-run-receipt", type=Path)
    p.add_argument("--producer-head")
    p.add_argument("--previous-ledger", type=Path)
    p.add_argument("--output", required=True, type=Path)
    opts = p.parse_args(argv)
    inputs = [opts.evidence_report, opts.owner_run_receipt, opts.previous_ledger]
    if opts.output.resolve().is_relative_to(FROZEN_ROOT.resolve()) or any(
        path is not None and opts.output.resolve() == path.resolve() for path in inputs
    ):
        raise ValueError("cannot overwrite frozen evidence or input receipts")
    report = _json_object(opts.evidence_report)
    receipt = _json_object(opts.owner_run_receipt) if opts.owner_run_receipt else None
    previous = _json_object(opts.previous_ledger) if opts.previous_ledger else None
    ledger = build_120_target_ledger(
        report, owner_receipt=receipt, producer_head=opts.producer_head,
        previous_input_fingerprint=(previous.get("input_fingerprint") if previous else None),
    )
    _write_readiness_report(
        opts.output, json.dumps(ledger, indent=2, sort_keys=True) + "\n",
        protected_roots=(FROZEN_ROOT,),
    )
    print(json.dumps({
        "publication_status": ledger["publication_status"],
        "target_count": ledger["target_count"],
        "evaluated_target_count": ledger["evaluated_target_count"],
        "repeat_evaluation_advice": ledger["repeat_evaluation_advice"],
    }, sort_keys=True))
    return 0 if ledger["publication_status"] == "PUBLISHED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
