"""Replay-only acceptance proof for frozen opening vertical-placement validator v1.

DRAFT / REPLAY ONLY / DO NOT MERGE.
"""
from pathlib import Path
import subprocess

from tools.validator_replay_harness import LaneType, ReplayConfig, run_replay


CURRENT_MAIN_SHA = "72ae738ee71ecdbdc0e4993e138bc2b0980bdbce"
PRODUCTION_SHA = "bdf50dca6b5920c7ae282c701aad6a69fb2f02da"
VALIDATOR_BASE_SHA = CURRENT_MAIN_SHA
VALIDATOR_REF = "chatgpt/opening-vertical-placement-validator-v1"
VALIDATOR_COMMIT = "93da3f3f5e83ff9ccafaad99b6c5aadea3d4b63f"
VALIDATOR_PATH = "tests/test_opening_vertical_placement_authority_validator_v1_frozen.py"
VALIDATOR_BLOB = "f237ed242abe2c1269e53d924539f8d1dc9e93bb"


def test_frozen_vertical_placement_validator_accepts_production() -> None:
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

    assert report.pytest_normal.passed == 22
    assert report.pytest_normal.failed == 0
    assert report.pytest_normal.xfailed == 0
    assert report.pytest_normal.xpassed == 0
    assert report.pytest_normal.errors == 0

    assert report.pytest_runxfail.passed == 22
    assert report.pytest_runxfail.failed == 0
    assert report.pytest_runxfail.errors == 0
