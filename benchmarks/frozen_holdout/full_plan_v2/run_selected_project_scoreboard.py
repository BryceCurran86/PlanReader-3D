"""Exact scoreboard for an explicitly selected Full Plan V2 project set.

This is reporting/orchestration only. It reuses the existing frozen manifests,
sealed-run verifier, exact identity reconciliation, evaluator and failure ledger.

Unlike the default suite runner, the caller explicitly names the projects that
form the active score. This allows the current Maryborough + Lot16 51-object
lane to be scored without editing the frozen suite manifest or pretending the
other verified projects were executed.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from typing import Iterable

if __package__:
    from pb_source_closed_run_export import sealed_source_closed_run_from_dict
    from .development_scoreboard import (
        build_development_failure_ledger_v2,
        evaluate_development_suite_v2,
    )
    from .manifest_io import load_project_manifest
    from .sealed_reconciliation import (
        identity_map_from_dict,
        reconcile_sealed_run_v2,
    )
else:
    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root))
    from pb_source_closed_run_export import sealed_source_closed_run_from_dict
    from benchmarks.frozen_holdout.full_plan_v2.development_scoreboard import (
        build_development_failure_ledger_v2,
        evaluate_development_suite_v2,
    )
    from benchmarks.frozen_holdout.full_plan_v2.manifest_io import (
        load_project_manifest,
    )
    from benchmarks.frozen_holdout.full_plan_v2.sealed_reconciliation import (
        identity_map_from_dict,
        reconcile_sealed_run_v2,
    )


def _json_object(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return raw


def score_selected_projects(
    *,
    root: Path,
    project_ids: Iterable[str],
    sealed_dir: Path,
    identity_map_dir: Path,
):
    selected = tuple(str(value).strip() for value in project_ids if str(value).strip())
    if not selected:
        raise ValueError("at least one project_id is required")
    if len(set(selected)) != len(selected):
        raise ValueError("project_ids must be unique")

    manifests = []
    produced = {}
    for project_id in selected:
        manifest_path = root / "projects" / project_id / "source_manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(
                f"project manifest is missing: {manifest_path}"
            )
        manifest = load_project_manifest(manifest_path)
        if manifest.project_id != project_id:
            raise ValueError(
                f"project manifest identity mismatch: {project_id}"
            )

        sealed_path = sealed_dir / f"{project_id}.json"
        map_path = identity_map_dir / f"{project_id}.identity_map.json"
        if not sealed_path.is_file():
            raise FileNotFoundError(
                f"selected project sealed run is missing: {sealed_path}"
            )
        if not map_path.is_file():
            raise FileNotFoundError(
                f"selected project identity map is missing: {map_path}"
            )

        sealed = sealed_source_closed_run_from_dict(_json_object(sealed_path))
        identity_map = identity_map_from_dict(_json_object(map_path))
        produced[project_id] = reconcile_sealed_run_v2(
            manifest,
            sealed.to_dict(),
            identity_map,
        )
        manifests.append(manifest)

    score = evaluate_development_suite_v2(tuple(manifests), produced)
    ledger = build_development_failure_ledger_v2(tuple(manifests), produced)
    return score, ledger


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Score an explicit set of exact Full Plan V2 projects."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
    )
    parser.add_argument(
        "--project-id",
        action="append",
        dest="project_ids",
        required=True,
        help="Project id to include. Repeat for each selected project.",
    )
    parser.add_argument("--sealed-dir", type=Path, required=True)
    parser.add_argument("--identity-map-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--failure-ledger-output", type=Path, default=None)
    args = parser.parse_args(argv)

    score, ledger = score_selected_projects(
        root=args.root,
        project_ids=args.project_ids,
        sealed_dir=args.sealed_dir,
        identity_map_dir=args.identity_map_dir,
    )

    payload = asdict(score)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if args.failure_ledger_output is not None:
        args.failure_ledger_output.parent.mkdir(parents=True, exist_ok=True)
        args.failure_ledger_output.write_text(
            json.dumps(asdict(ledger), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if score.development_accuracy is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())
