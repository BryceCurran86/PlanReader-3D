"""CLI for the Full Plan V2 development scoreboard."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

if __package__:
    from .development_scoreboard import evaluate_development_suite_v2
    from .manifest_io import load_produced_items, load_suite_manifests
    from .sealed_reconciliation import (
        identity_map_from_dict,
        reconcile_sealed_run_v2,
    )
else:
    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root))
    from benchmarks.frozen_holdout.full_plan_v2.development_scoreboard import (
        evaluate_development_suite_v2,
    )
    from benchmarks.frozen_holdout.full_plan_v2.manifest_io import (
        load_produced_items,
        load_suite_manifests,
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Score the current independently verified Full Plan V2 truth set."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
    )
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument(
        "--produced-dir",
        type=Path,
        default=None,
        help="Directory containing direct <project_id>.json evaluator rows.",
    )
    inputs.add_argument(
        "--sealed-dir",
        type=Path,
        default=None,
        help="Directory containing benchmark-neutral sealed production runs.",
    )
    parser.add_argument(
        "--identity-map-dir",
        type=Path,
        default=None,
        help=(
            "Directory containing <project_id>.identity_map.json exact-identity "
            "bindings; required with --sealed-dir."
        ),
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    if args.sealed_dir is not None and args.identity_map_dir is None:
        parser.error("--identity-map-dir is required with --sealed-dir")
    if args.identity_map_dir is not None and args.sealed_dir is None:
        parser.error("--identity-map-dir requires --sealed-dir")

    manifests = load_suite_manifests(args.root)
    produced = {}

    if args.produced_dir is not None:
        for manifest in manifests:
            path = args.produced_dir / f"{manifest.project_id}.json"
            if path.exists():
                produced[manifest.project_id] = load_produced_items(path)

    if args.sealed_dir is not None:
        assert args.identity_map_dir is not None
        for manifest in manifests:
            sealed_path = args.sealed_dir / f"{manifest.project_id}.json"
            map_path = (
                args.identity_map_dir
                / f"{manifest.project_id}.identity_map.json"
            )
            if not sealed_path.exists():
                continue
            if not map_path.exists():
                raise FileNotFoundError(
                    f"sealed run exists but identity map is missing: {map_path}"
                )
            sealed_run = _json_object(sealed_path)
            identity_map = identity_map_from_dict(_json_object(map_path))
            produced[manifest.project_id] = reconcile_sealed_run_v2(
                manifest,
                sealed_run,
                identity_map,
            )

    result = evaluate_development_suite_v2(manifests, produced)
    payload = asdict(result)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result.development_accuracy is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())
