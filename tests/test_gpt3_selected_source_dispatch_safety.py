"""Public selected-two CI must not falsely score unavailable private drawings.

Only owner-dispatched replay may provision exact original PDFs, and that job
must run byte verification before original-source reconciliation. This test
never needs access to private drawings or any GitHub secret.
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
    replay = _job("original-two-project-replay")
    assert "pytest -q tests/test_gpt3_selected_two_project_original_evidence.py" in focused
    assert "secrets.ORIGINAL_SOURCES_TOKEN" not in focused
    assert "github.event_name == 'workflow_dispatch'" in replay
    assert "actions/checkout" in replay
    assert "secrets.ORIGINAL_SOURCES_TOKEN" in replay
    assert "vars.ORIGINAL_SOURCES_REPOSITORY" in replay


def test_exact_original_replay_requires_frozen_source_provision_before_any_score():
    replay = _job("original-two-project-replay")
    provision = replay.index("uses: ./.github/actions/provision-original-sources")
    recalc = replay.index("Reverify original PDF bytes")
    assert provision < recalc
    assert "1. Construction Plans - Lot 16 Power (REV E).pdf" in replay
    assert "Arch_Combined_Maryborough_Service_Station.pdf" in replay
    assert "allow-missing: true" not in replay
    assert "allow-missing: 'true'" not in replay
    assert "--output \"$ROOT/selected_two_project_development_ONLY.json\"" in replay
    assert "full_four_project_publication_allowed" in replay
    assert "official_four_project_accuracy" in replay


def test_private_sources_never_enter_public_replay_artifacts():
    replay = _job("original-two-project-replay")
    assert "actions/upload-artifact" in replay
    assert "path: artifacts/gpt3-selected-source-v2/" in replay
    assert "path: documents/" not in replay
    assert "path: ./" not in replay
    assert "path: ${{ github.workspace }}" not in replay
