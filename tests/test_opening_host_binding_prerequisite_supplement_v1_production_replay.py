"""Replay-only defect proof for frozen host prerequisite supplement vs PR #362."""
from pathlib import Path

from tools.validator_replay_harness import LaneType, ReplayConfig, run_replay


BASE_SHA = "36a1f49ad92f553102101f8a2bf1d01ee45b2f52"
PRODUCTION_SHA = "56c2ef3cb25e98a7fe93163b5daa300e44c9f44f"
VALIDATOR_REF = "gpt2/opening-host-binding-prerequisite-supplement-v1"
VALIDATOR_COMMIT = "931506b0b80531383c78a621ca9c09473642ed58"
VALIDATOR_PATH = "tests/test_opening_host_binding_prerequisite_supplement_v1.py"
VALIDATOR_BLOB = "d26aab02676a65829781255ccbb88a6d03e936a0"
FIRST_DEFECT = "test_attack_s01_arbitrary_opening_id_and_raw_geometry_cannot_mint_host_binding"


def test_frozen_host_prerequisite_supplement_rejects_pr362_candidate() -> None:
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
    assert report.preflight.passed is True
    assert report.sha_match is True
    assert report.actual_validator_blob_sha == VALIDATOR_BLOB
    assert report.overlay_blob_sha == VALIDATOR_BLOB
    assert report.production_file_count == 0
    assert report.benchmark_touched is False
    assert report.gold_touched is False
    assert report.holdout_touched is False

    # Once the production module exists the strict xfails are intentionally
    # inactive. A failure in the ordinary frozen run is therefore classified
    # as a production behavioral regression, not validator expected-RED.
    assert report.verdict == "behavioral_regression"
    assert report.pytest_normal.returncode != 0
    assert report.pytest_normal.failed >= 1
    assert report.pytest_normal.errors == 0
    assert FIRST_DEFECT in report.pytest_normal.first_failure
