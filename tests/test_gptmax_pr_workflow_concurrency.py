"""A superseded PR cancels only its own GPT MAX workflow run.

Workflow dispatch, public main pushes, and completely independent PRs are
not cancelled by these job-level queue policy changes. No source tests are
excluded or reclassified.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]/".github/workflows"
WORKFLOWS = [
    "test-gptmax-1215-paired-signed-source.yml",
    "test-gptmax-1215-raw-source-bijection.yml",
    "test-gptmax-cross-flank-rail-bands.yml",
    "test-gptmax-customer-receipt-retention.yml",
    "test-gptmax-full-foreground-source.yml",
    "test-gptmax-g17-detector-first-gate.yml",
    "test-gptmax-g17-jamb-pair-source.yml",
    "test-gptmax-g17-original-w2-w4-shadow.yml",
    "test-gptmax-g17-plan-wall-scope.yml",
    "test-gptmax-g17-source-only-retention.yml",
    "test-gptmax-host-rekey-parity.yml",
    "test-gptmax-host-source-witness-integrity.yml",
    "test-gptmax-infill-endpoint-opposition.yml",
    "test-gptmax-interior-dimension-tick-source.yml",
    "test-gptmax-lot16-host-frame-gpt1-gate.yml",
    "test-gptmax-mixed-source-band.yml",
    "test-gptmax-native-cross-view-marks.yml",
    "test-gptmax-native-neutral-fill-source.yml",
    "test-gptmax-native-opening-schedule-source.yml",
    "test-gptmax-native-opening-viewport-scope.yml",
    "test-gptmax-native-paint-partition-shadow.yml",
    "test-gptmax-original-candidate-membership.yml",
    "test-gptmax-original-f07-mark-membership.yml",
    "test-gptmax-original-g17-shadow-cells.yml",
    "test-gptmax-original-opening-role-audit.yml"
]


def test_twenty_five_source_authority_workflows_keep_independent_pr_queues():
    assert len(WORKFLOWS) == len(set(WORKFLOWS)) == 25
    groups = []
    for filename in WORKFLOWS:
        source = (ROOT / filename).read_text(encoding="utf-8")
        assert "pull_request:" in source
        assert source.count("\nconcurrency:\n") == 1
        assert "  cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in source
        expected = filename.removesuffix(".yml")
        group = (
            "  group: " + expected
            + "-${{ github.event.pull_request.number || github.run_id }}"
        )
        assert group in source
        assert source.index("concurrency:\n") < source.index("\njobs:\n")
        assert "runs-on: ubuntu-latest" in source
        assert "pull_request_target:" not in source
        groups.append(expected)
    assert len(groups) == len(set(groups))


def test_original_required_ci_pipeline_is_not_cancelled_by_this_batch():
    ci = (ROOT / "ci.yml").read_text(encoding="utf-8")
    assert "name: CI" in ci
    assert "  test:" in ci
    assert "python-version: [\"3.13\", \"3.14\"]" in ci
