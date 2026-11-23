from pathlib import Path

import yaml


def test_pr_runs_only_source_neutral_pinned_test_and_integrity_paths():
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/gpt1-lot16-original-three-family-first-failure.yml"
    )
    doc = yaml.load(workflow.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert "pull_request" in doc["on"]
    assert set(doc["jobs"]) == {"source-neutral"}
    steps = doc["jobs"]["source-neutral"]["steps"]
    assert steps[0]["with"]["persist-credentials"] == "false"
    for expected in (
        "test_gpt1_figured_dimension_scale_consistency_shadow.py",
        "test_gpt1_source_figured_plan_plane_shadow.py",
        "test_gpt1_source_owned_figured_plan_bridge.py",
        "scripts/check_full_plan_v2_integrity.py",
    ):
        assert expected in str(steps)
