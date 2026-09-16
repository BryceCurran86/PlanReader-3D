"""Replay-only proof for opening-universe completeness remediation v2.

This file is not part of the frozen validator or production remediation.  It
uses the merged replay harness to overlay the exact frozen validator onto the
exact production head and requires the formerly expected-RED contract to turn
fully green.
"""
from pathlib import Path

from tools.validator_replay_harness import (
    FailureClassification,
    LaneType,
    ReplayConfig,
    run_replay,
)


PRODUCTION_SHA = "3d9f546f67696f0aaf5fa39108a3d48a502de84d"
BASE_SHA = "4b7b7412eecb7c7d434ac0732184314f97c85678"
VALIDATOR_REF = "gpt2/opening-universe-completeness-post-identity-v3"
VALIDATOR_PATH = "tests/test_opening_universe_completeness_authority_redteam_v2.py"
FROZEN_BLOB = "96ad4ad77899ebde504c1deab265905469d026be"


def test_frozen_completeness_validator_is_green_on_remediation_v2() -> None:
    report = run_replay(
        ReplayConfig(
            lane=LaneType.COMPLETENESS,
            repo_path=Path.cwd(),
            production_sha=PRODUCTION_SHA,
            base_sha=BASE_SHA,
            validator_ref=VALIDATOR_REF,
            validator_path=VALIDATOR_PATH,
            expected_validator_blob_sha=FROZEN_BLOB,
        )
    )

    assert report.verdict == FailureClassification.VALIDATOR_GREEN.value
    assert report.preflight.passed is True
    assert report.sha_match is True
    assert report.actual_validator_blob_sha == FROZEN_BLOB
    assert report.overlay_blob_sha == FROZEN_BLOB
    assert report.production_file_count == 0
    assert report.benchmark_touched is False
    assert report.gold_touched is False
    assert report.holdout_touched is False

    assert report.pytest_normal.returncode == 0
    assert report.pytest_normal.passed == 30
    assert report.pytest_normal.failed == 0
    assert report.pytest_normal.xfailed == 0

    assert report.pytest_runxfail.returncode == 0
    assert report.pytest_runxfail.passed == 30
    assert report.pytest_runxfail.failed == 0
