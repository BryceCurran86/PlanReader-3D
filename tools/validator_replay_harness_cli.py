#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tools.validator_replay_harness import (
    FailureClassification,
    LaneType,
    ReplayConfig,
    run_replay,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replay a frozen validator against an exact production SHA."
    )
    parser.add_argument("--lane", required=True, choices=[item.value for item in LaneType])
    parser.add_argument("--repo-path", type=Path, default=Path.cwd())
    parser.add_argument("--production-sha", required=True)
    parser.add_argument("--base-sha")
    parser.add_argument("--validator-ref")
    parser.add_argument("--validator-path")
    parser.add_argument("--expected-validator-blob-sha")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--json-report", type=Path)
    parser.add_argument("--markdown-report", type=Path)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    config_path = Path(__file__).with_name("validator_replay_lanes.json")
    lane_config = json.loads(config_path.read_text(encoding="utf-8"))["lanes"][args.lane]
    config = ReplayConfig(
        lane=LaneType(args.lane),
        repo_path=args.repo_path,
        production_sha=args.production_sha,
        base_sha=args.base_sha or lane_config["base_sha"],
        validator_ref=args.validator_ref or lane_config["validator_ref"],
        validator_path=args.validator_path or lane_config["validator_path"],
        expected_validator_blob_sha=(
            args.expected_validator_blob_sha
            if args.expected_validator_blob_sha is not None
            else lane_config.get("expected_validator_blob_sha")
        ),
        preflight_only=args.preflight_only,
        json_report=args.json_report,
        markdown_report=args.markdown_report,
        verbose=args.verbose,
    )
    try:
        report = run_replay(config)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"lane={report.lane}")
    print(f"verdict={report.verdict}")
    print(f"validator_blob={report.actual_validator_blob_sha}")
    print(f"blob_match={report.sha_match}")
    print(
        f"preflight={'PASS' if report.preflight.passed else 'FAIL'} "
        f"({report.preflight.seconds:.3f}s)"
    )
    print(f"validator_production_files={report.production_file_count}")
    print(
        "baseline="
        f"{report.pytest_normal.passed} passed, {report.pytest_normal.failed} failed, "
        f"{report.pytest_normal.xfailed} xfailed"
    )
    print(
        "runxfail="
        f"{report.pytest_runxfail.passed} passed, {report.pytest_runxfail.failed} failed"
    )

    success = {
        FailureClassification.VALIDATOR_GREEN.value,
        FailureClassification.EXPECTED_BEHAVIORAL_RED.value,
        FailureClassification.PREFLIGHT_ONLY.value,
    }
    return 0 if report.verdict in success and report.preflight.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
