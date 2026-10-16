"""Strict post-evaluator target delta for the frozen 120-item V2 suite.

No extraction, producer authority, scoring or promotion is performed. Inputs
MUST be a prior GPT3 120-target ledger, and even two mutually consistent
published claims are NOT independently issuer/source-authenticated here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

from tools.report_gpt3_four_project_evidence import (
    FROZEN_ROOT, _json_object, load_suite_manifests,
)
from scripts.report_full_plan_v2_readiness import _write_readiness_report


_STATES = frozenset((
    "MATCHED_WITHIN_TOLERANCE", "MATCHED_OUTSIDE_TOLERANCE",
    "MISSED", "PARTIAL", "UNRESOLVED",
))
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_HEAD40 = re.compile(r"^[0-9a-f]{40}$")
_WIN = "MATCHED_WITHIN_TOLERANCE"
_SCHEMA = "gpt3-120-target-ledger-v1"


def _expected_inputs_and_targets() -> tuple[dict, dict, dict]:
    manifests = load_suite_manifests(FROZEN_ROOT)
    if len(manifests) != 4:
        raise ValueError("frozen V2 must have four projects")
    targets: dict[tuple[str, str], tuple[str, str]] = {}
    source_sha = {}
    paths = [
        FROZEN_ROOT / "manifest.json",
        FROZEN_ROOT / "evaluator.py",
        FROZEN_ROOT / "sealed_reconciliation.py",
    ]
    for manifest in manifests:
        source_sha[manifest.project_id] = sorted(
            doc.sha256 for doc in manifest.source_documents
        )
        root = FROZEN_ROOT / "projects" / manifest.project_id
        paths.extend([root / "source_manifest.json", root / "reference_takeoff.json"])
        for item in manifest.verified_items:
            if not item.denominator_eligible:
                continue
            key = (manifest.project_id, item.item_id)
            if key in targets:
                raise ValueError("duplicate canonical frozen target")
            targets[key] = (item.trade_category, item.unit)
    if len(targets) != 120:
        raise ValueError("frozen truth denominator drift")
    file_hashes = {
        str(path.relative_to(FROZEN_ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
    }
    return targets, source_sha, file_hashes


def _official_source_universe_verified() -> bool:
    """A provisional frozen manifest cannot yield a published V2 result."""
    manifests = load_suite_manifests(FROZEN_ROOT)
    return (
        len(manifests) == 4
        and all(m.status == "VERIFIED" and m.source_package_complete for m in manifests)
    )


def _validate_input_ledger(
    ledger: Mapping[str, Any],
    *,
    targets: dict, source_sha: dict, frozen_sha: dict,
) -> dict[tuple[str, str], dict]:
    if (
        not isinstance(ledger, dict)
        or ledger.get("schema_version") != _SCHEMA
        or ledger.get("target_count") != 120
        or ledger.get("source_sha256s_by_project") != source_sha
        or ledger.get("frozen_file_sha256s") != frozen_sha
        or ledger.get("publication_status") not in ("PUBLISHED", "UNPUBLISHED")
    ):
        raise ValueError("wrong target, source, or scorer input universe")
    finger = ledger.get("input_fingerprint")
    if type(finger) is not str or _SHA64.fullmatch(finger) is None:
        raise ValueError("missing canonical scoring input fingerprint")
    head = ledger.get("producer_head")
    if head is not None and (type(head) is not str or _HEAD40.fullmatch(head) is None):
        raise ValueError("invalid exact producer head")
    rows = ledger.get("items")
    if not isinstance(rows, list) or len(rows) != 120:
        raise ValueError("missing 120 exact target results")
    by_key: dict[tuple[str, str], dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("malformed target evidence")
        project = row.get("project_id")
        target = row.get("item_id")
        if type(project) is not str or type(target) is not str:
            raise ValueError("untyped target identity")
        key = (project, target)
        if key not in targets or key in by_key:
            raise ValueError("foreign or duplicate physical target")
        if (row.get("trade_category"), row.get("unit")) != targets[key]:
            raise ValueError("target trade/unit identity drift")
        by_key[key] = row
    if len(by_key) != len(targets):
        raise ValueError("canonical target universe incomplete")
    if ledger["publication_status"] == "UNPUBLISHED":
        if (
            ledger.get("evaluated_target_count") != 0
            or ledger.get("not_evaluated_target_count") != 120
            or ledger.get("official_coverage_accuracy") is not None
            or ledger.get("official_precision_adjusted_accuracy") is not None
            or any(row.get("evaluation_state") != "NOT_EVALUATED"
                   or row.get("produced_quantity_id") is not None
                   for row in rows)
        ):
            raise ValueError("unpublished run must never assert scored targets")
    else:
        if not _official_source_universe_verified():
            raise ValueError("published score forbidden while frozen source manifests remain INCOMPLETE")
        if (
            head is None
            or ledger.get("evaluated_target_count") != 120
            or ledger.get("not_evaluated_target_count") != 0
            or any(row.get("evaluation_state") not in _STATES for row in rows)
        ):
            raise ValueError("published claims must have a complete scored producer run")
        for row in rows:
            if row["evaluation_state"] in (
                "MATCHED_WITHIN_TOLERANCE", "MATCHED_OUTSIDE_TOLERANCE"
            ) and (type(row.get("produced_quantity_id")) is not str
                    or not row["produced_quantity_id"]):
                raise ValueError("matched target requires exact produced quantity identity")
            if row["evaluation_state"] in ("MISSED", "PARTIAL") and (
                row.get("produced_quantity_id") is not None
            ):
                raise ValueError("missing/partial target cannot claim exact produced identity")
        within = sum(row["evaluation_state"] == _WIN for row in rows)
        expected = within / 120
        value = ledger.get("official_coverage_accuracy")
        adjusted = ledger.get("official_precision_adjusted_accuracy")
        if (
            type(value) not in (int, float)
            or type(adjusted) not in (int, float)
            or not all(math.isfinite(x) for x in (value, adjusted))
            or not math.isclose(value, expected, rel_tol=0, abs_tol=1e-12)
            or adjusted < 0 or adjusted > value
        ):
            raise ValueError("advertised published score is not consistent with item states")
    return by_key


def compare_postscore_ledgers(before: dict, after: dict) -> dict[str, Any]:
    """Compare frozen-scored 120 item states, never guess their physical causes."""
    targets, sources, frozen = _expected_inputs_and_targets()
    prior = _validate_input_ledger(
        before, targets=targets, source_sha=sources, frozen_sha=frozen,
    )
    next_rows = _validate_input_ledger(
        after, targets=targets, source_sha=sources, frozen_sha=frozen,
    )
    same_input = before["input_fingerprint"] == after["input_fingerprint"]
    if same_input and before.get("producer_head") != after.get("producer_head"):
        raise ValueError("same scoring fingerprint cannot change producer commit")
    if same_input and (
        before["publication_status"] != after["publication_status"]
        or any(
            prior[key]["evaluation_state"] != next_rows[key]["evaluation_state"]
            or prior[key].get("produced_quantity_id")
            != next_rows[key].get("produced_quantity_id")
            for key in targets
        )
        or before.get("official_coverage_accuracy")
        != after.get("official_coverage_accuracy")
        or before.get("official_precision_adjusted_accuracy")
        != after.get("official_precision_adjusted_accuracy")
    ):
        raise ValueError("same scoring fingerprint cannot have changed target results")
    if (
        before["publication_status"] != "PUBLISHED"
        or after["publication_status"] != "PUBLISHED"
    ):
        return {
            "comparison_status": "OFFICIAL_BASELINE_OR_REEVALUATION_UNAVAILABLE",
            "score_comparison_available": False,
            "before_coverage_accuracy": None,
            "after_coverage_accuracy": None,
            "net_additional_correct_items": None,
            "accuracy_percentage_point_change": None,
            "newly_correct_target_ids": [],
            "regressed_target_ids": [],
            "input_fingerprint_unchanged": same_input,
            "issuer_authentication_proven_by_this_comparator": False,
        }

    gains, regressions, other_changes, rekeys = [], [], [], []
    for project_id, target_id in sorted(targets):
        old = prior[(project_id, target_id)]
        new = next_rows[(project_id, target_id)]
        was = old["evaluation_state"] == _WIN
        now = new["evaluation_state"] == _WIN
        ref = {"project_id": project_id, "item_id": target_id}
        if now and not was:
            gains.append(ref)
        if was and not now:
            regressions.append(ref)
        if old["evaluation_state"] != new["evaluation_state"] and was == now:
            other_changes.append({
                **ref, "before": old["evaluation_state"],
                "after": new["evaluation_state"],
            })
        if (old.get("produced_quantity_id") != new.get("produced_quantity_id")):
            rekeys.append(ref)
    net = len(gains) - len(regressions)
    before_accuracy = before["official_coverage_accuracy"]
    after_accuracy = after["official_coverage_accuracy"]
    if not math.isclose(after_accuracy - before_accuracy, net / 120,
                        rel_tol=0, abs_tol=1e-12):
        raise ValueError("before/after evaluator accuracy cannot differ from target deltas")
    return {
        "comparison_status": (
            "UNCHANGED_PRODUCER_SOURCE_SCORING_INPUTS" if same_input
            else "COMPARED_POST_EVALUATOR_CLAIMS"
        ),
        "score_comparison_available": True,
        "before_coverage_accuracy": before_accuracy,
        "after_coverage_accuracy": after_accuracy,
        "before_precision_adjusted_accuracy": before["official_precision_adjusted_accuracy"],
        "after_precision_adjusted_accuracy": after["official_precision_adjusted_accuracy"],
        "newly_correct_target_ids": gains,
        "regressed_target_ids": regressions,
        "other_changed_target_states": other_changes,
        "changed_produced_quantity_ids": rekeys,
        "gross_new_correct_items": len(gains),
        "regressed_correct_items": len(regressions),
        "net_additional_correct_items": net,
        "accuracy_percentage_point_change": 100.0 * net / 120,
        "target_change_count": len(gains) + len(regressions) + len(other_changes),
        "input_fingerprint_unchanged": same_input,
        # Consistent postscore JSON is still not a new PDF/issuer/evaluator proof.
        "issuer_authentication_proven_by_this_comparator": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before-ledger", type=Path, required=True)
    parser.add_argument("--after-ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if (
        args.output.resolve().is_relative_to(FROZEN_ROOT.resolve())
        or args.output.resolve() in (
            args.before_ledger.resolve(), args.after_ledger.resolve()
        )
    ):
        raise ValueError("cannot overwrite scoring inputs or benchmark truth")
    result = compare_postscore_ledgers(
        _json_object(args.before_ledger), _json_object(args.after_ledger),
    )
    _write_readiness_report(
        args.output, json.dumps(result, indent=2, sort_keys=True) + "\n",
        # The two input files are protected above by exact resolved paths.
        # Their containing directory is a valid location for a NEW report.
        protected_roots=(FROZEN_ROOT,),
    )
    print(json.dumps({
        "comparison_status": result["comparison_status"],
        "score_comparison_available": result["score_comparison_available"],
        "net_additional_correct_items": result["net_additional_correct_items"],
    }, sort_keys=True))
    return 0 if result["score_comparison_available"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
