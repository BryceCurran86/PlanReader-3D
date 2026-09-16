"""Replay-only baseline proof for Item 4B expected-RED validator."""
from pathlib import Path

from tools.validator_replay_harness import LaneType, ReplayConfig, run_replay


BASE_SHA = "76c7882b1c4b28764d1e6a6f467d72bb276c2e01"
PRODUCTION_SHA = BASE_SHA
VALIDATOR_REF = "gpt2/physical-wall-equivalence-host-prerequisite-v1"
VALIDATOR_COMMIT = "bc51dfdf41a8af71c60c78070082c68c705596db"
VALIDATOR_PATH = "tests/test_physical_wall_equivalence_host_prerequisite_v1.py"
VALIDATOR_BLOB = "e092acbf3c114d5dcfe54c8035e91780c8b0ccee"


def test_item_4b_baseline_is_genuine_expected_red() -> None:
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
    assert report.pytest_normal.xfailed == 3
    assert report.pytest_normal.errors == 0

    assert report.pytest_runxfail.passed == 5
    assert report.pytest_runxfail.failed == 1
    assert report.pytest_runxfail.errors == 0
    assert "test_real_source_wall_band_relevant_representations_are_not_ambiguous" in report.pytest_runxfail.first_failure
