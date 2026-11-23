"""Public selected-two CI must not falsely score unavailable private drawings.

The hosted workflow exercises the source-neutral evaluator checks.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/score-gpt3-selected-two-original-projects.yml"


def _job(name: str) -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    marker = f"  {name}:\n"
    assert text.count(marker) == 1
    import re
    tail = text.split(marker, 1)[1]
    next_job = re.search(r"(?m)^  [a-z][a-z0-9_-]*:\s*$", tail)
    return tail[:next_job.start()] if next_job else tail


def test_public_pr_only_executes_source_neutral_project_tests():
    full = WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request:" in full and "workflow_dispatch:" in full
    focused = _job("focused")
    assert "pytest -q tests/test_gpt3_selected_two_project_original_evidence.py" in focused
    assert "secrets.ORIGINAL_SOURCES_TOKEN" not in focused
    assert "  original-two-project-replay:\n" not in full
