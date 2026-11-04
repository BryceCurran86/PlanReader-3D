"""Provisional Full Plan V2 development coverage, without modifying frozen code.

Read the existing frozen development scorer's verified sealed/identity output.
Show matched / ALL 120 fixed eligible items even before all four projects run.
This is not the official V2 publication evaluator and cannot set its status.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import Any, Mapping

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# This repository deliberately loads frozen V2 modules by exact file path:
# benchmarks/ may be shadowed by a third-party package. Reuse the installed
# source-verified reporter's loader without modifying frozen files.
from tools.report_gpt3_four_project_evidence import load_suite_manifests
_FROZEN_ROOT = _REPO_ROOT / "benchmarks" / "frozen_holdout" / "full_plan_v2"
_FROZEN_RUNNER = _FROZEN_ROOT / "run_development_scoreboard.py"
_SCHEMA = "gpt3-provisional-frozen120-development-v1"


def _exact_score_int(row: Mapping[str, Any], name: str) -> int:
    value = row.get(name)
    if type(value) is not int or value < 0:
        raise ValueError("frozen development result has invalid " + name)
    return value


def provisional_full_120_results(
    frozen_score: Mapping[str, Any],
    frozen_ledger: Mapping[str, Any],
    *,
    frozen_root: Path = _FROZEN_ROOT,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Augment already evaluated source-closed development receipts, not truth.

    A missing project's objects are NOT_EXECUTED, never evaluator MISSED.
    The official 4/4 scoring/reporting implementation remains byte-identical.
    """
    if type(frozen_score) is not dict or type(frozen_ledger) is not dict:
        raise ValueError("frozen development receipts must be objects")
    manifests = tuple(load_suite_manifests(frozen_root))
    if len(manifests) != 4:
        raise ValueError("expected four unchanged frozen projects")
    by_id = {manifest.project_id: manifest for manifest in manifests}
    if len(by_id) != 4:
        raise ValueError("duplicate frozen project identity")
    denominator_items = {
        manifest.project_id: tuple(
            item for item in manifest.verified_items if item.denominator_eligible
        )
        for manifest in manifests
    }
    denominator = sum(len(items) for items in denominator_items.values())
    if denominator != 120:
        raise ValueError("frozen 120-item denominator changed")

    projects = frozen_score.get("project_results")
    if type(projects) is not list or len(projects) != 4:
        raise ValueError("development project receipt universe incomplete")
    by_project = {}
    for project in projects:
        if type(project) is not dict or project.get("project_id") not in by_id:
            raise ValueError("unrecognized development project")
        project_id = project["project_id"]
        if project_id in by_project:
            raise ValueError("duplicate development project")
        if _exact_score_int(project, "truth_denominator") != len(
            denominator_items[project_id]
        ):
            raise ValueError("project development denominator changed")
        if type(project.get("execution_present")) is not bool:
            raise ValueError("untyped project execution receipt")
        by_project[project_id] = project
    if set(by_project) != set(by_id):
        raise ValueError("development project universe mismatch")

    executed_ids = {
        project_id for project_id, row in by_project.items()
        if row["execution_present"]
    }
    missing_ids = sorted(set(by_id) - executed_ids)
    if frozen_score.get("configured_projects") != 4 or (
        _exact_score_int(frozen_score, "source_closed_truth_items") != denominator
        or _exact_score_int(frozen_score, "executed_projects") != len(executed_ids)
        or _exact_score_int(frozen_score, "executed_denominator") != sum(
            len(denominator_items[project_id]) for project_id in executed_ids
        )
    ):
        raise ValueError("inconsistent development execution/denominator receipt")
    if (type(frozen_ledger.get("missing_execution_project_ids")) is not list
        or sorted(frozen_ledger["missing_execution_project_ids"]) != missing_ids):
        raise ValueError("failure ledger and execution roster conflict")
    if (
        type(frozen_ledger.get("failure_items")) is not list
        or type(frozen_ledger.get("unsupported_outputs")) is not list
    ):
        raise ValueError("frozen item failure ledger missing")

    matched = _exact_score_int(frozen_score, "matched_within_tolerance")
    conflicts = _exact_score_int(frozen_score, "lineage_conflicts")
    executed_denominator = _exact_score_int(
        frozen_score, "executed_denominator"
    )
    if matched > executed_denominator:
        raise ValueError("matched output exceeds executed denominator")
    observed = frozen_score.get("observed_accuracy")
    expected_observed = (
        matched / executed_denominator if executed_denominator else None
    )
    if expected_observed is None:
        if observed is not None:
            raise ValueError("observed accuracy without executed sources")
    elif (
        type(observed) not in (int, float)
        or not math.isfinite(observed)
        or not math.isclose(observed, expected_observed, abs_tol=1e-12, rel_tol=0)
    ):
        raise ValueError("development observed accuracy lacks matching items")

    expected_status = (
        "COMPLETE_CURRENT_TRUTH_SET"
        if len(executed_ids) == 4 and not conflicts
        else "PARTIAL_OR_BLOCKED"
    )
    if frozen_score.get("status") != expected_status:
        raise ValueError("frozen scorer publication state conflict")
    if (len(executed_ids) != 4 and
        not all(
            f"{project_id}:production_output_missing"
            in frozen_score.get("reason_codes", ())
            for project_id in missing_ids
        )):
        raise ValueError("missing source runs not recorded as blocked")

    # The development-only numerator comes from the unchanged V2 evaluator
    # after its signed/identity reconciliation, never from reference targets.
    full_coverage = (
        matched / denominator if executed_denominator and not conflicts else None
    )
    score = dict(frozen_score)
    score["schema_version"] = _SCHEMA
    score["unexecuted_denominator"] = denominator - executed_denominator
    score["coverage_accuracy"] = full_coverage
    score["development_accuracy"] = full_coverage
    score["official_four_project_accuracy"] = None
    score["official_score_published"] = False
    score["development_score_denominator"] = denominator
    score["development_score_provisional"] = True

    not_executed: list[dict[str, Any]] = []
    for project_id in missing_ids:
        for item in denominator_items[project_id]:
            not_executed.append({
                "project_id": project_id,
                "item_id": item.item_id,
                "state": "NOT_EXECUTED",
                "trade_category": item.trade_category,
                "unit": item.unit,
                "produced_quantity_id": None,
                "error_fraction": None,
                "expected_object_refs": list(item.expected_object_refs),
                "matched_object_refs": [],
            })
    not_executed.sort(key=lambda item: (item["project_id"], item["item_id"]))
    ledger = dict(frozen_ledger)
    ledger["schema_version"] = _SCHEMA
    ledger["not_executed_items"] = not_executed
    ledger["unexecuted_denominator"] = len(not_executed)
    ledger["official_score_published"] = False
    if len(not_executed) != score["unexecuted_denominator"]:
        raise ValueError("not-executed item count differs from denominator")
    return score, ledger


def _write_new(path: Path, payload: dict[str, Any], *, protected: tuple[Path, ...]) -> None:
    destination = path.resolve()
    if path.is_symlink() or path.exists() or any(
        destination == root.resolve() or destination.is_relative_to(root.resolve())
        for root in protected
    ):
        raise ValueError("provisional score cannot overwrite source, frozen or signed evidence")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as output:
        json.dump(payload, output, indent=2, sort_keys=True, allow_nan=False)
        output.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=_FROZEN_ROOT)
    parser.add_argument("--sealed-dir", type=Path, required=True)
    parser.add_argument("--identity-map-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--failure-ledger-output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.resolve() == args.failure_ledger_output.resolve():
        raise ValueError("provisional score and failure ledger need distinct outputs")
    protected = (args.root, args.sealed_dir, args.identity_map_dir)
    for output in (args.output, args.failure_ledger_output):
        destination = output.resolve()
        if output.is_symlink() or output.exists() or any(
            destination == root.resolve() or destination.is_relative_to(root.resolve())
            for root in protected
        ):
            raise ValueError("provisional output must be new and outside protected inputs")
    with TemporaryDirectory(prefix="gpt3-live-development-") as temporary:
        tmp = Path(temporary)
        prior = tmp / "frozen-score.json"
        prior_ledger = tmp / "frozen-ledger.json"
        command = [
            sys.executable, str(_FROZEN_RUNNER),
            "--root", str(args.root),
            "--sealed-dir", str(args.sealed_dir),
            "--identity-map-dir", str(args.identity_map_dir),
            "--output", str(prior),
            "--failure-ledger-output", str(prior_ledger),
        ]
        outcome = subprocess.run(
            command, cwd=_REPO_ROOT, capture_output=True, text=True,
            check=False,
        )
        if outcome.returncode not in (0, 2) or (
            not prior.is_file() or not prior_ledger.is_file()
        ):
            raise ValueError("unchanged frozen scorer rejected sealed or identity inputs")
        score, ledger = provisional_full_120_results(
            json.loads(prior.read_text(encoding="utf-8")),
            json.loads(prior_ledger.read_text(encoding="utf-8")),
            frozen_root=args.root,
        )
    _write_new(args.output, score, protected=protected)
    _write_new(args.failure_ledger_output, ledger, protected=protected)
    print(json.dumps({
        "status": score["status"],
        "matched_within_tolerance": score["matched_within_tolerance"],
        "frozen_denominator": 120,
        "coverage_accuracy": score["coverage_accuracy"],
        "observed_accuracy_on_executed_projects": score["observed_accuracy"],
        "executed_denominator": score["executed_denominator"],
        "not_executed_items": len(ledger["not_executed_items"]),
        "official_score_published": False,
    }, sort_keys=True))
    return 0 if score["status"] == "COMPLETE_CURRENT_TRUTH_SET" else 2


if __name__ == "__main__":
    raise SystemExit(main())
