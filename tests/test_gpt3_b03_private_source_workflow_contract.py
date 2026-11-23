"""The Maryborough B03 workflow runs source-neutral checks."""
from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/diag-gpt2-maryborough-b03-room-gates.yml"
SOURCE = "Arch_Combined_Maryborough_Service_Station.pdf"


def _jobs():
    doc = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert set(doc["jobs"]) == {"source-neutral-b03"}
    assert set(doc["on"]) == {"pull_request", "workflow_dispatch"}
    assert doc["permissions"] == {"contents": "read"}
    return doc["jobs"]


def test_pr_never_receives_original_pdf_secret_or_falsely_reports_original_positive():
    jobs = _jobs()
    public = jobs["source-neutral-b03"]
    assert public["if"] == "${{ github.event_name == 'pull_request' }}"
    assert len(public["steps"]) >= 4
    raw = repr(public)
    for blocked in ("ORIGINAL_SOURCES_TOKEN", "ORIGINAL_SOURCES_REPOSITORY", SOURCE,
                    "documents/sources", "provision-original-sources",
                    "actions/upload-artifact"):
        assert blocked not in raw
    assert "tests/test_gpt2_b03_room_measurement_gates.py" in raw
    assert "source-neutral" in public["name"].lower() or "synthetic" in public["name"].lower()
    assert "NOT RUN" in raw
    assert "no FIRM or score grant" in raw
