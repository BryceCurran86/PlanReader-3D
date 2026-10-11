"""Q06 integration: material/RCP source checks cannot cancel other agents' PRs."""
from pathlib import Path


def test_material_rcp_source_workflow_isolation_is_per_pull_request():
    workflow = Path(".github/workflows/test-gpt2-final-material-rcp.yml").read_text(
        encoding="utf-8",
    )
    assert (
        "group: test-gpt2-final-material-rcp-${{ github.event.pull_request.number || github.ref }}"
        in workflow
    )
    # Keep cancellation of superseded commits in the SAME PR, not all PRs.
    assert "cancel-in-progress: true" in workflow


def test_material_rcp_original_source_and_frozen_truth_checks_are_preserved():
    workflow = Path(".github/workflows/test-gpt2-final-material-rcp.yml").read_text(
        encoding="utf-8",
    )
    assert "python scripts/check_full_plan_v2_integrity.py" in workflow
    assert "tests/test_source_material_semantic_authority_v1.py" in workflow
    assert "tests/test_cross_view_ceiling_finish_authority.py" in workflow
    assert 'run: pip install -r requirements.txt -r requirements-ci-v1228.txt' in workflow
