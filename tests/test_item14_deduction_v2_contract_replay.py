"""Replay-only proof that current Item 14 does not satisfy final Item 13 V2.

TEST ONLY / REPLAY ONLY / NEVER MERGE.

This is a negative acceptance proof, not a production patch.  The exact #447
validator is overlaid onto exact #442 production.  Current #442 is expected to
fail the final contract because it has no producer-owned target-applicability
authority parameter/provenance and deliberately always abstains at applicability.
"""
from pathlib import Path
import subprocess

from tools.validator_replay_harness import (
    FailureClassification,
    LaneType,
    ReplayConfig,
    run_replay,
)


VALIDATOR_BASE_SHA = "212f5b0ff9d9e585c4b9db861cf42729166f70f5"
ITEM14_SHA = "16b8724aa06ff769ec92f76ebd46947eefc06caf"
VALIDATOR_REF = "gpt2/opening-deduction-authority-validator-v2-final"
VALIDATOR_PATH = "tests/test_opening_deduction_authority_validator_v2.py"
FROZEN_BLOB = "8afd724d03fdaf1cbe8ef1e9ff7863cbb0dd7449"


def _ensure_exact_item14_object_is_local() -> None:
    """CI may shallow-checkout this replay branch; fetch only the exact target SHA."""
    probe = subprocess.run(
        ["git", "cat-file", "-e", f"{ITEM14_SHA}^{{commit}}"],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
    )
    if probe.returncode == 0:
        return
    subprocess.run(
        ["git", "fetch", "--no-tags", "origin", ITEM14_SHA],
        cwd=Path.cwd(),
        check=True,
        capture_output=True,
        text=True,
    )


def test_current_item14_fails_final_item13_contract_for_applicability_gap() -> None:
    _ensure_exact_item14_object_is_local()
    report = run_replay(
        ReplayConfig(
            # The merged harness has no deduction lane label; lane does not alter
            # replay semantics, only report/worktree naming.
            lane=LaneType.COMPLETENESS,
            repo_path=Path.cwd(),
            production_sha=ITEM14_SHA,
            base_sha=VALIDATOR_BASE_SHA,
            validator_ref=VALIDATOR_REF,
            validator_path=VALIDATOR_PATH,
            expected_validator_blob_sha=FROZEN_BLOB,
        )
    )

    assert report.preflight.passed is True
    assert report.sha_match is True
    assert report.actual_validator_blob_sha == FROZEN_BLOB
    assert report.overlay_blob_sha == FROZEN_BLOB
    assert report.production_file_count == 0
    assert report.benchmark_touched is False
    assert report.gold_touched is False
    assert report.holdout_touched is False

    # #442 must NOT be accepted by the stronger final contract.  Failure must be
    # ordinary behavioral contract failure, not import/fixture/blob drift.
    assert report.verdict == FailureClassification.BEHAVIORAL_REGRESSION.value
    assert report.pytest_normal.returncode != 0
    assert report.pytest_normal.failed >= 1
    assert report.pytest_normal.errors == 0
    assert "test_factory_requires_separate_target_applicability_authority" in (
        report.pytest_normal.output
    )
    assert "test_positive_record_must_retain_applicability_provenance" in (
        report.pytest_normal.output
    )
