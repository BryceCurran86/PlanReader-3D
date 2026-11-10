"""Fast, source-neutral first-gate triage for PlanReader agents.

Usage: python -m tools.agent_fast_gate --lane claude-corner

This tests only the immediate coding blocker, not original source authority.
It never issues quantities, customer seals or a benchmark score. Full dual-
Python CI and private exact-head signed/customer retention remain mandatory.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Callable, Mapping


@dataclass(frozen=True)
class Lane:
    tests: tuple[str, ...]
    selector: str = "not original and not private"


LANES: Mapping[str, Lane] = {
    "claude-corner": Lane(
        ("tests/test_opening_corner_terminated_host_shadow_v1.py",)
    ),
    "claude-pier": Lane(
        ("tests/test_lot16_shared_solid_pier_not_an_opening_v1.py",)
    ),
    "claude-door-height": Lane(
        ("tests/test_external_door_height_estimate_policy.py",)
    ),
    "antigravity-office": Lane((
        "tests/test_source_cross_view_floor_correspondence_shadow.py",
        "tests/test_gptmax_maryborough_revision_source_veto.py",
    )),
    "gptmax-customer": Lane((
        "tests/test_source_role_customer_aggregation.py",
        "tests/test_full_project_customer_handoff.py",
        "tests/test_q5446_source_role_customer_runtime.py",
    )),
}


def build_command(lane: str, root: Path, python: str = sys.executable) -> tuple[str, ...]:
    """Fixed non-shell command; a missing test fails rather than quietly skipping."""
    if lane not in LANES:
        raise ValueError(f"unknown lane: {lane}")
    spec = LANES[lane]
    missing = [path for path in spec.tests if not (root / path).is_file()]
    if missing:
        raise FileNotFoundError(
            "Lane code is not on this branch: " + ", ".join(missing)
        )
    return (
        str(python), "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider",
        "-k", spec.selector, *spec.tests,
    )


def execute(
    lane: str,
    root: Path,
    *,
    python: str = sys.executable,
    timeout_seconds: int = 600,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, object]:
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 3600:
        raise ValueError("timeout_seconds must be an integer in 1..3600")
    command = build_command(lane, root, python=python)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["PLANREADER_PRIVATE_ORIGINAL_POLICY"] = "skip_missing_in_public_ci"
    try:
        outcome = runner(
            list(command), cwd=root, env=env, timeout=timeout_seconds, check=False
        )
        code = int(outcome.returncode)
        state = "PASSED" if code == 0 else "FAILED"
    except subprocess.TimeoutExpired:
        code = 124
        state = "TIMEOUT"
    return {
        "lane": lane,
        "result": state,
        "exit_code": code,
        "source_neutral_only": True,
        "private_original_verified": False,
        "signed_customer_retention_verified": False,
        "full_dual_python_ci_verified": False,
        "frozen120_score_granted": False,
        "release_approved": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lane", choices=tuple(sorted(LANES)), required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        command = build_command(args.lane, root)
        if args.dry_run:
            print(json.dumps({
                "lane": args.lane,
                "command": list(command),
                "source_neutral_only": True,
                "release_approved": False,
            }, sort_keys=True))
            return 0
        result = execute(args.lane, root, timeout_seconds=args.timeout_seconds)
    except (FileNotFoundError, ValueError) as error:
        print(json.dumps({
            "lane": args.lane,
            "result": "BLOCKED",
            "reason": str(error),
            "release_approved": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
