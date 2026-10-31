"""The GPT1 PR CI must never execute untrusted code against client PDFs.

The skipped original job is NOT evidence of a source-positive replay.
An independent owner-controlled trusted-main, no-egress original runner is
required before releasing any new source-backed opening quantity.
"""
from pathlib import Path


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github/workflows/test-gptmax-lot16-host-frame-gpt1-gate.yml"
)


def test_pr_head_cannot_execute_private_original_replay_even_if_ready():
    text = WORKFLOW.read_text(encoding="utf-8")
    source_job = text.split("  immutable-original-production-replay:", 1)[1]
    assert "    if: ${{ false }}" in source_job
    assert "vars.PLANREADER_OWNER_ORIGINAL_SOURCE_READY" not in source_job
    assert "on:\n  pull_request:" in text
    assert "source-integrity-regressions:" in text
    assert 'python-version: ["3.13", "3.14"]' in text


def test_pr_workflow_cannot_upload_original_derived_reports():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "actions/upload-artifact" not in text
