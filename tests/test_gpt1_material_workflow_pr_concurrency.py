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
