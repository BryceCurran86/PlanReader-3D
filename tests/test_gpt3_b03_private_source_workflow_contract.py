"""Fail-closed source access contract for original Maryborough B03 workflow.

Public pull-request checks must not receive private-source credentials. The
real original producer is reserved for owner-dispatched trusted main.
No source PDFs or private receipts are used by these tests.
"""
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/diag-gpt2-maryborough-b03-room-gates.yml"
SOURCE = "Arch_Combined_Maryborough_Service_Station.pdf"
ORIGINAL_GUARD = (
    "${{ github.event_name == 'workflow_dispatch' && "
    "github.ref == 'refs/heads/main' && "
    "github.actor == 'BryceCurran86' && "
    "github.triggering_actor == 'BryceCurran86' && "
    "github.repository == 'BryceCurran86/PlanReader-3D' }}"
)


def _jobs():
    doc = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert set(doc["jobs"]) == {"source-neutral-b03", "original-b03"}
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


def test_original_provisioning_stays_owner_main_only_and_is_sha_attested():
    jobs = _jobs()
    original = jobs["original-b03"]
    assert original["if"] == ORIGINAL_GUARD
    assert int(original["timeout-minutes"]) >= 65
    steps = original["steps"]
    first = steps[0]
    assert first["uses"] == "actions/checkout@v4"
    assert first["with"]["persist-credentials"] == "false"
    prov = [i for i, s in enumerate(steps)
            if s.get("uses") == "./.github/actions/provision-original-sources"]
    assert len(prov) == 1
    i = prov[0]
    assert i > 3
    details = steps[i]["with"]
    assert details["token"] == "${{ secrets.ORIGINAL_SOURCES_TOKEN }}"
    assert details["repository"] == "${{ vars.ORIGINAL_SOURCES_REPOSITORY }}"
    assert details["ref"] == "${{ vars.ORIGINAL_SOURCES_REF }}"
    assert details["names"].strip() == SOURCE
    assert details["allow-missing"] == "false"
    assert i + 1 < len(steps)
    run = steps[i + 1]["run"]
    assert "--pdf documents/sources/" + SOURCE in run
    assert "--expected-sha256 b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007" in run
    assert 'exec > "$RUNNER_TEMP/gpt2-b03-source-private.log" 2>&1' in run
    assert "source_closed_floor_seal_quantity_count" in run
    assert "verified_floor_customer_row_count" in run
    assert "floor_area_customer_row_verified" in run
    assert "commercial_estimator_approved" in run
    assert "benchmark_accuracy" in run
    assert "Original source, signed floor and customer" not in run  # no unsupported source-positive claim
    assert "actions/upload-artifact" not in repr(steps)
    cleanup = steps[-1]
    assert cleanup["if"] == "always()"
    assert "rm -rf documents/sources" in cleanup["run"]
    assert "gpt2-b03-source-private.log" in cleanup["run"]


@pytest.mark.parametrize("bad", [
    "${{ github.event_name == 'pull_request' }}",
    "${{ github.event_name == 'workflow_dispatch' }}",
])
def test_original_guard_is_strictly_more_than_event_name(bad):
    guard = _jobs()["original-b03"]["if"]
    assert guard != bad
    assert "github.actor" in guard and "github.triggering_actor" in guard
    assert "github.repository" in guard and "github.ref" in guard
