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


def _stable_owner_evidence(receipt: Mapping[str, Any] | None) -> dict | None:
    """Exclude elapsed time, machine memory and session folders from input ID.

    Original SHA/preflight receipts, actually sealed production artifacts and
    stable per-project disposition ARE relevant. Logs, performance samples
    and output-folder paths are not a new source/producer/scoring combination.
    """
    if receipt is None:
        return None
    stable_files = []
    files = receipt.get("files")
    if not isinstance(files, list):
        raise ValueError("owner receipt file-digest universe is missing")
    for file_row in files:
        if not isinstance(file_row, dict):
            raise ValueError("malformed owner receipt artifact")
        path = file_row.get("file")
        if type(path) is not str:
            raise ValueError("invalid owner receipt artifact path")
        keep = (
            path == "SOURCE_SHA_VERIFICATION.json"
            or path.endswith("/source_package_preflight.json")
            or path.endswith("/outputs/production_summary.json")
            or path.endswith("/outputs/source_attempt_preflight.json")
            or path.endswith(".sealed.json")
            or (
                path.count("/")==2
                and "/outputs/" in path
                and path.rsplit("/", 1)[-1].startswith("au_qld_")
                and path.endswith(".json")
            )
        )
        if not keep:
            continue
        sha = file_row.get("share_safe_sha256")
        if type(sha) is not str or re.fullmatch(r"[0-9a-f]{64}", sha) is None:
            raise ValueError("owner source/sealed artifact lacks valid digest")
        stable_files.append((path, sha))
    if len({row[0] for row in stable_files}) != len(stable_files):
        raise ValueError("duplicate source/sealed artifact in owner receipt")
    handoffs = receipt.get("project_handoffs")
    if type(handoffs) is not list:
        raise ValueError("owner machine handoff status universe unavailable")
    dispositions = {"COMPLETED", "PROCESS_FAILED", "TIMEOUT", "MEMORY_LIMIT",
                    "SYSTEM_MEMORY_GUARD", "PRIMARY_SOURCE_UNAVAILABLE"}
    for row in handoffs:
        if (type(row) is not dict or type(row.get("status")) is not str
            or row["status"] not in dispositions):
            raise ValueError("unrecognized owner source production disposition")
        status = row["status"]
        code = row.get("exit_code")
        if (
            (status == "COMPLETED" and (type(code) is not int or code != 0))
            or (status == "PROCESS_FAILED" and (type(code) is not int or code == 0))
            or (status not in {"COMPLETED", "PROCESS_FAILED"} and code is not None)
        ):
            raise ValueError("owner source completion and process exit code conflict")
    return {
        "repo_head": receipt.get("repo_head"),
        "handoff_results": sorted(
            (row["project_id"], row["status"], row.get("exit_code"))
            for row in handoffs
        ),
        "source_preflight_and_sealed_artifact_hashes": sorted(stable_files),
    }


def _require_published_suite_summary_parity(
    report: Mapping[str, Any], official: Mapping[str, Any],
    item_results: Mapping[tuple[str, str], Mapping[str, Any]],
) -> None:
    """Only the unchanged evaluator owns score counts; reject altered copies."""
    import math
    if len(item_results) != 120:
        raise ValueError("published exact 120 target result universe incomplete")
    matched = sum(row["state"] == "MATCHED_WITHIN_TOLERANCE"
                  for row in item_results.values())
    # The original evaluator consumes one produced quantity at most once.
    # Even an UNRESOLVED row may carry an exact ID when its value is None;
    # no two frozen targets may claim the same identified sealed quantity.
    source_ids = []
    for row in item_results.values():
        state, qid = row["state"], row.get("produced_quantity_id")
        if state in ("MATCHED_WITHIN_TOLERANCE", "MATCHED_OUTSIDE_TOLERANCE"):
            if type(qid) is not str or not qid or qid != qid.strip():
                raise ValueError("published matched target lacks canonical produced identity")
        elif state in ("MISSED", "PARTIAL") and qid is not None:
            raise ValueError("published missed/partial target cannot claim produced identity")
        elif state == "UNRESOLVED" and qid is not None and (
            type(qid) is not str or not qid or qid != qid.strip()
        ):
            raise ValueError("published unresolved target has invalid produced identity")
        if qid is not None:
            source_ids.append(qid)
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("published target quantity identity reused across frozen items")
    extras = official.get("unsupported_extra")
    if type(extras) is not int or extras < 0:
        raise ValueError("published evaluator unsupported-extra count malformed")
    if type(official.get("matched_within_tolerance")) is not int or (
        official["matched_within_tolerance"] != matched
    ):
        raise ValueError("published official matched total differs from item states")
    expected_coverage = matched / 120
    expected_precision = matched / (120 + extras)
    for field, expected in (
        ("coverage_accuracy", expected_coverage),
        ("precision_adjusted_accuracy", expected_precision),
    ):
        for source in (report, official):
            value = source.get(field)
            if type(value) not in (int, float) or not math.isfinite(value) or (
                not math.isclose(value, expected, rel_tol=0, abs_tol=1e-12)
            ):
                raise ValueError("published score copy differs from official exact item states")
    project_rows = official.get("project_results")
    if type(project_rows) is not list or len(project_rows) != 4:
        raise ValueError("published four-project result universe missing")
    if any(type(row.get("matched_within_tolerance")) is not int
           or type(row.get("unsupported_extra")) is not int
           or row["unsupported_extra"] < 0 for row in project_rows):
        raise ValueError("published per-project counts malformed")
    if sum(row["matched_within_tolerance"] for row in project_rows) != matched or (
        sum(row["unsupported_extra"] for row in project_rows) != extras
    ):
        raise ValueError("published suite totals disagree with project results")
    by_project: dict[str, int] = {}
    for (project_id, _), item in item_results.items():
        by_project[project_id] = by_project.get(project_id, 0) + (
            item["state"] == "MATCHED_WITHIN_TOLERANCE"
        )
    # Equal suite totals do not justify swapping one project winner with
    # another. Project ID and each exact numerator must remain paired.
    if len(by_project) != 4 or any(
        type(row.get("project_id")) is not str
        or row["project_id"] not in by_project
        or row["matched_within_tolerance"] != by_project[row["project_id"]]
        for row in project_rows
    ) or len({row["project_id"] for row in project_rows}) != 4:
        raise ValueError("published project match claims disagree with exact target states")


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
    _require_published_suite_summary_parity(report, official, by_target)
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
    if owner_receipt is not None:
        receipt_head = owner_receipt.get("repo_head")
        if type(receipt_head) is not str or not _SHA.fullmatch(receipt_head):
            raise ValueError("owner receipt lacks canonical exact producer head")
        if producer_head is None:
            producer_head = receipt_head
        elif producer_head != receipt_head:
            raise ValueError("producer commit conflicts with owner-run receipt")
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
        "owner_execution_receipt": _stable_owner_evidence(owner_receipt),
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
    if opts.output.is_symlink():
        raise ValueError("target ledger cannot follow output symlinks")
    if opts.output.exists():
        try:
            existing = _json_object(opts.output)
        except (OSError, ValueError, UnicodeError) as exc:
            raise ValueError("target ledger cannot overwrite unrelated original evidence") from exc
        if existing.get("schema_version") != "gpt3-120-target-ledger-v1":
            raise ValueError("target ledger cannot overwrite unrelated original evidence")
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
