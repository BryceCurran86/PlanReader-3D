"""Replay-only proof that the frozen completeness validator is executable.

This file is intentionally NOT part of the frozen validator PR. It exercises
the merged validator replay harness against current main and the exact v3
validator blob, then asserts that --runxfail reaches a genuine behavioral RED.
"""
from pathlib import Path

from tools.validator_replay_harness import (
    FailureClassification,
    LaneType,
    ReplayConfig,
    run_replay,
)


PRODUCTION_SHA = "4b7b7412eecb7c7d434ac0732184314f97c85678"
VALIDATOR_REF = "gpt2/opening-universe-completeness-post-identity-v3"
VALIDATOR_PATH = "tests/test_opening_universe_completeness_authority_redteam_v2.py"
FROZEN_BLOB = "96ad4ad77899ebde504c1deab265905469d026be"


def test_frozen_completeness_validator_replay_reaches_genuine_behavioral_red() -> None:
    report = run_replay(
        ReplayConfig(
            lane=LaneType.COMPLETENESS,
            repo_path=Path.cwd(),
            production_sha=PRODUCTION_SHA,
            base_sha=PRODUCTION_SHA,
            validator_ref=VALIDATOR_REF,
            validator_path=VALIDATOR_PATH,
            expected_validator_blob_sha=FROZEN_BLOB,
        )
    )

    assert report.verdict == FailureClassification.EXPECTED_BEHAVIORAL_RED.value
    assert report.preflight.passed is True
    assert report.sha_match is True
    assert report.actual_validator_blob_sha == FROZEN_BLOB
    assert report.overlay_blob_sha == FROZEN_BLOB
    assert report.production_file_count == 0
    assert report.benchmark_touched is False
    assert report.gold_touched is False
    assert report.holdout_touched is False

    assert report.pytest_normal.returncode == 0
    assert report.pytest_normal.passed == 9
    assert report.pytest_normal.failed == 0
    assert report.pytest_normal.xfailed == 21

    assert report.pytest_runxfail.returncode != 0
    assert report.pytest_runxfail.failed == 1
    assert "test_attack01_complete_full_page_universe_may_resolve" in report.pytest_runxfail.first_failure
