"""Replay-only baseline proof for host-binding authenticated-prerequisite v3."""
from pathlib import Path

from tools.validator_replay_harness import LaneType, ReplayConfig, run_replay


BASE_SHA = "444e601f27f8c2f7852cba5b3435503349532575"
VALIDATOR_REF = "gpt2/opening-host-binding-authenticated-prerequisite-v3"
VALIDATOR_COMMIT = "a7f8b32494f8103750cac6d400ac5580e80bc3e1"
VALIDATOR_PATH = "tests/test_opening_host_binding_authority_redteam_v3.py"
VALIDATOR_BLOB = "85e68cb1f451e84225ee4447a86138e575c310a6"


def test_host_binding_v3_is_clean_behavioral_red_on_current_main() -> None:
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

    assert report.pytest_normal.passed == 5
    assert report.pytest_normal.failed == 0
    assert report.pytest_normal.xfailed == 15
    assert report.pytest_normal.errors == 0

    assert report.pytest_runxfail.passed == 5
    assert report.pytest_runxfail.failed == 1
    assert report.pytest_runxfail.errors == 0
    assert "test_attack01_real_producer_owned_opening_and_complete_unique_host_may_bind" in (
        report.pytest_runxfail.first_failure
    )
