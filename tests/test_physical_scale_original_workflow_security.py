"""Private original proof stays owner/main-only; public PR tests need no secret."""
from pathlib import Path

import yaml


PATH = Path(__file__).resolve().parents[1] / ".github/workflows/gpt1-source-owned-physical-scale-plan-view.yml"


def workflow():
    return yaml.safe_load(PATH.read_text())


def test_public_focused_jobs_remain_dual_python_source_free_and_have_no_credentials():
    doc = workflow()
    job = doc["jobs"]["focused"]
    assert job["strategy"]["matrix"]["python-version"] == ["3.13", "3.14"]
    text = yaml.safe_dump(job)
    assert "secrets." not in text and "provision-original-sources" not in text
    checkout = next(s for s in job["steps"] if s.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"]["persist-credentials"] is False
    events = doc.get("on", doc.get(True))
    assert events["pull_request"]["branches"] == ["main"]
    assert "workflow_dispatch" in events
    assert "tests/test_physical_scale_cached_source_scope.py" in events["pull_request"]["paths"]
