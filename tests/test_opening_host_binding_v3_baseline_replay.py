"""Replay-only baseline proof for frozen-candidate host-binding V3 validator."""
from pathlib import Path

from tools.validator_replay_harness import LaneType, ReplayConfig, run_replay


BASE_SHA = "76c7882b1c4b28764d1e6a6f467d72bb276c2e01"
VALIDATOR_REF = "gpt2/opening-host-binding-authenticated-prerequisite-v3"
VALIDATOR_COMMIT = "f7243fd177f423a2725cae663e368350409300b6"
VALIDATOR_PATH = "tests/test_opening_host_binding_authority_redteam_v3.py"
VALIDATOR_BLOB = "c5c55ab81c249cab9cde1b9a2c07fff26b624b7e"


def test_host_binding_v3_is_clean_behavioral_red_on_merged_4a_main() -> None:
    report = run_replay(
        ReplayConfig(
            lane=LaneType.HOST,
            repo_path=Path.cwd(),
            production_sha=BASE_SHA,
            base_sha=BASE_SHA,
            validator_ref=VALIDATOR_REF,
            validator_path=VALIDATOR_PATH,
            expected_validator_blob_sha=VALIDATOR_BLOB,
        )
    )

    assert report.validator_commit == VALIDATOR_COMMIT
    assert report.verdict == "expected_behavioral_red"
    assert report.preflight.passed is True
    assert report.sha_match is True
    assert report.actual_validator_blob_sha == VALIDATOR_BLOB
    assert report.overlay_blob_sha == VALIDATOR_BLOB
    assert report.production_file_count == 0
    assert report.benchmark_touched is False
    assert report.gold_touched is False
    assert report.holdout_touched is False

    assert report.pytest_normal.passed == 6
    assert report.pytest_normal.failed == 0
    assert report.pytest_normal.xfailed == 20
    assert report.pytest_normal.errors == 0

    assert report.pytest_runxfail.passed == 6
    assert report.pytest_runxfail.failed == 1
    assert report.pytest_runxfail.errors == 0
    assert "test_attack01_real_source_opening_complete_wall_universe_unique_host_may_bind" in (
        report.pytest_runxfail.first_failure
    )
