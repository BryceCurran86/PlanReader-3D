"""Replay-only acceptance proof for frozen opening-height validator v1.

DRAFT / REPLAY ONLY / DO NOT MERGE.
"""
from pathlib import Path
import subprocess

from tools.validator_replay_harness import LaneType, ReplayConfig, run_replay


CURRENT_MAIN_SHA = "e00ec09c9a24f898fdd5fb8e24b0cb5587fb49c9"
VALIDATOR_BASE_SHA = CURRENT_MAIN_SHA
PRODUCTION_SHA = "169ba8a175b3096f0a5ba9a7972b8be9fc3e1277"
VALIDATOR_REF = "claude/opening-height-authority-validator-v1"
VALIDATOR_COMMIT = "99bb8099335176541a098d036b687b30986aba40"
VALIDATOR_PATH = "tests/test_opening_height_authority_validator_v1.py"
VALIDATOR_BLOB = "9104d224bc6d392dd36d811bf73ab17c492d003b"


def test_frozen_opening_height_validator_accepts_exact_production() -> None:
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", CURRENT_MAIN_SHA, PRODUCTION_SHA],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert ancestry.returncode == 0, ancestry.stderr

    report = run_replay(
        ReplayConfig(
            lane=LaneType.DIMENSIONS,
            repo_path=Path.cwd(),
            production_sha=PRODUCTION_SHA,
            base_sha=VALIDATOR_BASE_SHA,
            validator_ref=VALIDATOR_REF,
            validator_path=VALIDATOR_PATH,
            expected_validator_blob_sha=VALIDATOR_BLOB,
        )
    )

    assert report.base_sha == VALIDATOR_BASE_SHA
    assert report.validator_commit == VALIDATOR_COMMIT
    assert report.production_sha == PRODUCTION_SHA
    assert report.verdict == "validator_green"
    assert report.preflight.passed is True
    assert report.sha_match is True
    assert report.actual_validator_blob_sha == VALIDATOR_BLOB
    assert report.overlay_blob_sha == VALIDATOR_BLOB
    assert report.production_file_count == 0
    assert report.benchmark_touched is False
    assert report.gold_touched is False
    assert report.holdout_touched is False

    assert report.pytest_normal.passed == 2
    assert report.pytest_normal.failed == 0
    assert report.pytest_normal.xfailed == 0
    assert report.pytest_normal.xpassed == 13
    assert report.pytest_normal.errors == 0

    assert report.pytest_runxfail.passed == 15
    assert report.pytest_runxfail.failed == 0
    assert report.pytest_runxfail.errors == 0
