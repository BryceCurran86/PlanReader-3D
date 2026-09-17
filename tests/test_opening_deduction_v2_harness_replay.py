"""Replay-only proof for the Item 13 Opening Deduction V2 validator.

TEST ONLY / REPLAY ONLY / NEVER MERGE.

The merged replay harness currently has no deduction-specific LaneType.  The lane
value below is metadata/worktree naming only; ``run_replay`` does not branch its
validation behavior on lane.  Using COMPLETENESS here avoids changing the merged
harness merely to add a label while still exercising exact blob, preflight,
baseline and --runxfail checks unchanged.
"""
from pathlib import Path

from tools.validator_replay_harness import (
    FailureClassification,
    LaneType,
    ReplayConfig,
    run_replay,
)


PRODUCTION_SHA = "212f5b0ff9d9e585c4b9db861cf42729166f70f5"
VALIDATOR_REF = "gpt2/opening-deduction-authority-validator-v2-final"
VALIDATOR_PATH = "tests/test_opening_deduction_authority_validator_v2.py"
FROZEN_BLOB = "8afd724d03fdaf1cbe8ef1e9ff7863cbb0dd7449"


def test_item13_validator_replay_reaches_genuine_deduction_behavioral_red() -> None:
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

    # The real native-PDF Physical Opening Void baseline and legacy firewall are
    # ordinary green.  Twelve final deduction/applicability propositions remain
    # strict expected-RED on the post-Item-11/12 baseline.
    assert report.pytest_normal.returncode == 0
    assert report.pytest_normal.passed == 2
    assert report.pytest_normal.failed == 0
    assert report.pytest_normal.xfailed == 12

    # --runxfail must reach production absence as a genuine behavioral RED,
    # not an import, collection, fixture, enum, placeholder or blob-drift error.
    assert report.pytest_runxfail.returncode != 0
    assert report.pytest_runxfail.failed == 1
    assert report.pytest_runxfail.errors == 0
    assert "test_deduction_module_exports_sealed_authority_surface" in (
        report.pytest_runxfail.first_failure
    )
