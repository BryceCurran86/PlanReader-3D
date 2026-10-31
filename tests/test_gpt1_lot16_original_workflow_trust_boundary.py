"""Original-source GPT1 diagnostic cannot execute PR-head code with client PDFs."""
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / (
    ".github/workflows/gpt1-lot16-original-three-family-first-failure.yml"
)


def _jobs():
    text = WORKFLOW.read_text(encoding="utf-8")
    return text, text.split("\n  original-source:\n", 1)[1]


def test_original_job_only_runs_from_owner_manual_main():
    text, source = _jobs()
    assert "  source-neutral:" in text
    assert 'python-version: ["3.13", "3.14"]' in text
    assert "github.event_name == 'workflow_dispatch'" in source
    assert "github.ref == 'refs/heads/main'" in source
    assert "github.actor == 'BryceCurran86'" in source
    assert "github.repository == 'BryceCurran86/PlanReader-3D'" in source
    assert "ref: ${{ github.sha }}" in source
    assert "EXPECTED_SHA: ${{ github.sha }}" in source
    assert "github.event.pull_request.head.sha" not in source
    assert "persist-credentials: false" in source


def test_original_transport_is_fail_closed_and_never_uploaded():
    text, source = _jobs()
    assert "uses: ./.github/actions/provision-original-sources" in source
    assert "token: ${{ secrets.ORIGINAL_SOURCES_TOKEN }}" in source
    assert "projects: au_qld_lot16_power" in source
    assert 'allow-missing: "false"' in source
    assert "actions/upload-artifact" not in text
    assert "rm -rf documents/sources artifacts/gpt1-original-lot16-first-failure" in source
    assert "print(json.dumps({k:fields[k]" not in source
