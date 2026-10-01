from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")


def test_v2_truth_separation_runs_for_pull_requests_and_pushes() -> None:
    assert "Enforce Full Plan V2 truth / production separation (pull request)" in WORKFLOW
    assert "Enforce Full Plan V2 truth / production separation (push)" in WORKFLOW
    assert "${{ github.event.pull_request.base.sha }}" in WORKFLOW
    assert "${{ github.event.pull_request.head.sha }}" in WORKFLOW
    assert "${{ github.event.before }}" in WORKFLOW
    assert "${{ github.event.after }}" in WORKFLOW
    command = (
        'git diff --name-only "$BASE_SHA" "$HEAD_SHA" '
        '| python scripts/check_v2_truth_separation.py'
    )
    assert WORKFLOW.count(command) == 2


def test_push_v2_truth_separation_fails_closed_on_invalid_range() -> None:
    assert 'ZERO_SHA="0000000000000000000000000000000000000000"' in WORKFLOW
    assert 'if [ -z "$BASE_SHA" ] || [ -z "$HEAD_SHA" ]' in WORKFLOW
    assert 'git cat-file -e "${BASE_SHA}^{commit}"' in WORKFLOW
    assert 'git cat-file -e "${HEAD_SHA}^{commit}"' in WORKFLOW


def test_ci_runs_active_v2_integrity_not_legacy_holdout_gate() -> None:
    assert "Verify Full Plan V2 truth integrity" in WORKFLOW
    assert "python scripts/check_full_plan_v2_integrity.py" in WORKFLOW
    assert "check_frozen_holdout_integrity.py" not in WORKFLOW
    assert "check_benchmark_gold_separation.py" not in WORKFLOW
