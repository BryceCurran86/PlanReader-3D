"""CLI for the Full Plan V2 development scoreboard."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

if __package__:
    from .development_scoreboard import evaluate_development_suite_v2
    from .manifest_io import load_produced_items, load_suite_manifests
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Score the current independently verified Full Plan V2 truth set."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
    )
    parser.add_argument(
        "--produced-dir",
        type=Path,
        default=None,
        help="Directory containing sealed <project_id>.json production outputs.",
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    manifests = load_suite_manifests(args.root)
    produced = {}
    if args.produced_dir is not None:
        for manifest in manifests:
            path = args.produced_dir / f"{manifest.project_id}.json"
            if path.exists():
                produced[manifest.project_id] = load_produced_items(path)

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
