"""Replay-only proof for the frozen post-completeness host validator."""
from pathlib import Path

from tools.validator_replay_harness import LaneType, ReplayConfig, run_replay


BASE_SHA = "36a1f49ad92f553102101f8a2bf1d01ee45b2f52"
VALIDATOR_REF = "gpt2/opening-host-binding-post-completeness-v2"
VALIDATOR_PATH = "tests/test_opening_host_binding_authority_redteam_v2.py"
VALIDATOR_BLOB = "55b2b3e87bc5263aa1693dce672c0d26aa94636b"


def test_frozen_host_validator_is_clean_behavioral_red_on_current_main() -> None:
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

    assert report.verdict == "expected_behavioral_red"
    assert report.preflight.passed is True
    assert report.sha_match is True
    assert report.actual_validator_blob_sha == VALIDATOR_BLOB
    assert report.overlay_blob_sha == VALIDATOR_BLOB
    assert report.production_file_count == 0
    assert report.benchmark_touched is False
    assert report.gold_touched is False
    assert report.holdout_touched is False

    assert report.pytest_normal.passed == 10
    assert report.pytest_normal.failed == 0
    assert report.pytest_normal.xfailed == 18
    assert report.pytest_normal.errors == 0

    assert report.pytest_runxfail.passed == 10
    assert report.pytest_runxfail.failed == 1
    assert "test_attack01_one_unambiguous_host_with_complete_producer_scope" in (
        report.pytest_runxfail.first_failure
    )
