"""Replay-only acceptance proof for frozen host-binding V3 over exact Item 4B + corrected host production.

DRAFT / REPLAY ONLY / DO NOT MERGE. Frozen validator #372 is consumed unchanged.
"""
from pathlib import Path

from tools.validator_replay_harness import LaneType, ReplayConfig, run_replay


BASE_SHA = "5b5d92583ef8a8695da90209bf05f84b7385a77a"
PRODUCTION_SHA = "a4dde62688dd12426ca48a6473c3d432b8222e39"
VALIDATOR_REF = "gpt2/opening-host-binding-authenticated-prerequisite-v3"
VALIDATOR_COMMIT = "f7243fd177f423a2725cae663e368350409300b6"
VALIDATOR_PATH = "tests/test_opening_host_binding_authority_redteam_v3.py"
VALIDATOR_BLOB = "c5c55ab81c249cab9cde1b9a2c07fff26b624b7e"


def test_frozen_host_binding_v3_accepts_exact_post_4b_production() -> None:
    report = run_replay(
        ReplayConfig(
            lane=LaneType.HOST,
            repo_path=Path.cwd(),
            production_sha=PRODUCTION_SHA,
            base_sha=BASE_SHA,
            validator_ref=VALIDATOR_REF,
            validator_path=VALIDATOR_PATH,
            expected_validator_blob_sha=VALIDATOR_BLOB,
        )
    )

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

    assert report.pytest_normal.passed == 26
    assert report.pytest_normal.failed == 0
    assert report.pytest_normal.xfailed == 0
    assert report.pytest_normal.errors == 0

    assert report.pytest_runxfail.passed == 26
    assert report.pytest_runxfail.failed == 0
    assert report.pytest_runxfail.errors == 0
