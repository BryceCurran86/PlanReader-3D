"""Replay-only expected-RED proof for frozen opening vertical-placement validator v1.

DRAFT / REPLAY ONLY / DO NOT MERGE.
"""
from pathlib import Path

from tools.validator_replay_harness import LaneType, ReplayConfig, run_replay


CURRENT_MAIN_SHA = "72ae738ee71ecdbdc0e4993e138bc2b0980bdbce"
VALIDATOR_BASE_SHA = CURRENT_MAIN_SHA
VALIDATOR_REF = "chatgpt/opening-vertical-placement-validator-v1"
VALIDATOR_COMMIT = "93da3f3f5e83ff9ccafaad99b6c5aadea3d4b63f"
VALIDATOR_PATH = "tests/test_opening_vertical_placement_authority_validator_v1_frozen.py"
VALIDATOR_BLOB = "f237ed242abe2c1269e53d924539f8d1dc9e93bb"


def test_frozen_vertical_placement_validator_is_expected_red_on_current_main() -> None:
    report = run_replay(
        ReplayConfig(
            lane=LaneType.DIMENSIONS,
            repo_path=Path.cwd(),
            production_sha=CURRENT_MAIN_SHA,
            base_sha=VALIDATOR_BASE_SHA,
            validator_ref=VALIDATOR_REF,
            validator_path=VALIDATOR_PATH,
            expected_validator_blob_sha=VALIDATOR_BLOB,
        )
    )

    assert report.base_sha == VALIDATOR_BASE_SHA
    assert report.validator_commit == VALIDATOR_COMMIT
    assert report.production_sha == CURRENT_MAIN_SHA
    assert report.verdict == "expected_behavioral_red"
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
    assert report.pytest_normal.xfailed == 20
    assert report.pytest_normal.errors == 0

    assert report.pytest_runxfail.passed == 2
    assert report.pytest_runxfail.failed == 1
    assert report.pytest_runxfail.errors == 0
