"""CLI for the full-plan takeoff reconciliation benchmark V2."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

if __package__:
    from .evaluator import evaluate_suite_v2
    from .manifest_io import load_produced_items, load_suite_manifests
else:
    repo_root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(repo_root))
    from benchmarks.frozen_holdout.full_plan_v2.evaluator import evaluate_suite_v2
    from benchmarks.frozen_holdout.full_plan_v2.manifest_io import (
        load_produced_items,
        load_suite_manifests,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
    )
    parser.add_argument(
        "--produced-dir",
        type=Path,
        default=None,
        help="Optional directory containing <project_id>.json sealed produced items",
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    manifests = load_suite_manifests(args.root)
    produced = {}
    if args.produced_dir is not None:
        for manifest in manifests:
            produced[manifest.project_id] = load_produced_items(
                args.produced_dir / f"{manifest.project_id}.json"
            )
    result = evaluate_suite_v2(manifests, produced, required_project_count=5)
    payload = asdict(result)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result.publication_status == "PUBLISHED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
