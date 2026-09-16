#!/usr/bin/env python3
"""CLI entry point for validator replay harness.

Usage:
    python -m tools.validator_replay_harness_cli --lane identity --production-sha <sha>
    python -m tools.validator_replay_harness_cli --lane dimensions --preflight-only
    python -m tools.validator_replay_harness_cli --lane completeness --json-report report.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tools.validator_replay_harness import (
    LaneType,
    ReplayConfig,
    run_replay,
    setup_logging,
)


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validator replay harness for frozen expected-RED test contracts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run identity validator smoke test
  python -m tools.validator_replay_harness_cli --lane identity \\
    --production-sha 507c57db16be515e2432c695341bdea1e71b3fd7 \\
    --base-sha 62a161519e617cdf9ce23069820dbf7c68aaf521 \\
    --json-report /tmp/identity_replay.json

  # Preflight only on dimensions validator
  python -m tools.validator_replay_harness_cli --lane dimensions \\
    --preflight-only --verbose

  # Full replay with both reports
  python -m tools.validator_replay_harness_cli --lane completeness \\
    --production-sha <sha> --base-sha <sha> \\
    --json-report /tmp/report.json \\
    --markdown-report /tmp/report.md
        """,
    )

    parser.add_argument(
        "--lane",
        required=True,
        choices=["dimensions", "completeness", "host", "identity"],
        help="Validator lane to replay.",
    )

    parser.add_argument(
        "--repo-path",
        type=Path,
        default=Path.cwd(),
        help="Path to PlanReader-3D repository (default: current directory).",
    )

    parser.add_argument(
        "--production-sha",
        required=True,
        help="Exact commit SHA for validator branch head.",
    )

    parser.add_argument(
        "--base-sha",
        help="Base SHA for changed-file detection (optional, auto-detected from lane config if omitted).",
    )

    parser.add_argument(
        "--validator-ref",
        help="Git ref for validator (optional, auto-loaded from lane config if omitted).",
    )

    parser.add_argument(
        "--validator-path",
        help="Path to validator test file (optional, auto-loaded from lane config if omitted).",
    )

    parser.add_argument(
        "--expected-validator-blob-sha",
        help="Expected blob SHA; harness hard-fails if mismatch (optional).",
    )

    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Run only preflight checks, skip pytest execution.",
    )

    parser.add_argument(
        "--json-report",
        type=Path,
        help="Path to write JSON report.",
    )

    parser.add_argument(
        "--markdown-report",
        type=Path,
        help="Path to write Markdown report.",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )

    args = parser.parse_args()

    # Load lane config
    lanes_config_path = Path(__file__).parent / "validator_replay_lanes.json"
    if not lanes_config_path.exists():
        print(
            f"ERROR: Lane configuration not found: {lanes_config_path}",
            file=sys.stderr,
        )
        return 1

    try:
        lanes_config = json.loads(lanes_config_path.read_text())
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse lane config: {e}", file=sys.stderr)
        return 1

    lane_name = args.lane
    if lane_name not in lanes_config.get("lanes", {}):
        print(f"ERROR: Unknown lane: {lane_name}", file=sys.stderr)
        return 1

    lane_cfg = lanes_config["lanes"][lane_name]

    # Build replay config
    config = ReplayConfig(
        lane=LaneType(lane_name),
        repo_path=args.repo_path.resolve(),
        production_sha=args.production_sha,
        base_sha=args.base_sha or lane_cfg.get("base_sha", ""),
        validator_ref=args.validator_ref or lane_cfg.get("validator_ref", ""),
        validator_path=args.validator_path or lane_cfg.get("validator_path", ""),
        expected_validator_blob_sha=(
            args.expected_validator_blob_sha
            or lane_cfg.get("expected_validator_blob_sha")
        ),
        preflight_only=args.preflight_only,
        json_report=args.json_report,
        markdown_report=args.markdown_report,
        verbose=args.verbose,
    )

    # Validate config
    if not config.repo_path.exists():
        print(f"ERROR: Repository not found: {config.repo_path}", file=sys.stderr)
        return 1

    if not config.production_sha or len(config.production_sha) < 7:
        print("ERROR: --production-sha is required and must be a valid commit SHA", file=sys.stderr)
        return 1

    if not config.base_sha or len(config.base_sha) < 7:
        print("ERROR: --base-sha is required and must be a valid commit SHA", file=sys.stderr)
        return 1

    if not config.validator_ref:
        print("ERROR: --validator-ref is required", file=sys.stderr)
        return 1

    if not config.validator_path:
        print("ERROR: --validator-path is required", file=sys.stderr)
        return 1

    # Run replay
    try:
        report = run_replay(config)

        # Print summary
        print("\n" + "=" * 80)
        print(f"Validator Replay Summary: {config.lane.value}")
        print("=" * 80)
        print(f"Verdict: {report.verdict}")
        print(f"SHA Match: {'✓' if report.sha_match else '✗'}")
        print(f"Preflight: {'✓ PASS' if report.preflight.passed else '✗ FAIL'}")
        print(f"Production Files Changed: {report.production_file_count}")
        print(f"Pytest Normal (GREEN): {report.pytest_normal.passed} passed")
        print(f"Pytest --runxfail (RED): {report.pytest_runxfail.passed} passed")
        print("=" * 80)

        if report.preflight.errors:
            print("\nPreflight Errors:")
            for err in report.preflight.errors:
                print(f"  - {err}")

        if args.json_report:
            print(f"\nJSON report: {args.json_report}")
        if args.markdown_report:
            print(f"Markdown report: {args.markdown_report}")

        # Return success if verdict is acceptable
        if report.verdict in ("VALIDATOR_GREEN", "PREFLIGHT_ONLY"):
            return 0
        else:
            return 1

    except Exception as e:
        print(f"ERROR: Replay failed: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
