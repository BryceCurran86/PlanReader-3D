"""Replay-only baseline proof for source-backed physical-wall validator v1."""
from pathlib import Path

from tools.validator_replay_harness import LaneType, ReplayConfig, run_replay


BASE_SHA = "90406f5849733469cab57c43150f299fd61380cb"
VALIDATOR_REF = "gpt2/source-backed-physical-wall-candidate-validator-v1"
VALIDATOR_COMMIT = "4f9503d027b32664bbdac235289fb401d310d27e"
VALIDATOR_PATH = "tests/test_source_backed_physical_wall_candidate_authority_v1.py"
VALIDATOR_BLOB = "52e29d89e1dd6dce2a4547e9fcdf86be5dd9b5ed"


def test_source_backed_wall_validator_is_clean_behavioral_red_on_current_main() -> None:
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

    assert report.pytest_normal.passed == 4
    assert report.pytest_normal.failed == 0
    assert report.pytest_normal.xfailed == 15
    assert report.pytest_normal.errors == 0

    assert report.pytest_runxfail.passed == 4
    assert report.pytest_runxfail.failed == 1
    assert report.pytest_runxfail.errors == 0
    assert "test_attack01_required_module_and_sealed_factory_exist" in (
        report.pytest_runxfail.first_failure
    )
