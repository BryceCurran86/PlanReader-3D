"""Private original proof stays owner/main-only; public PR tests need no secret."""
from pathlib import Path

import yaml


PATH = Path(__file__).resolve().parents[1] / ".github/workflows/gpt1-source-owned-physical-scale-plan-view.yml"


def workflow():
    return yaml.safe_load(PATH.read_text())


def test_private_original_job_has_no_pr_or_nonowner_entrypoint():
    doc = workflow()
    job = doc["jobs"]["original-lot16"]
    assert job["if"] == (
        "${{ github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' "
        "&& github.actor == 'BryceCurran86' && github.repository == 'BryceCurran86/PlanReader-3D' }}")
    assert doc["permissions"] == {"contents": "read"}
    assert job["strategy"]["matrix"]["python-version"] == ["3.13", "3.14"]
    assert job["strategy"]["fail-fast"] is False
    assert "pull_request_target" not in PATH.read_text()


def test_private_bytes_are_provisioned_only_after_trusted_checkout_and_fail_closed():
    steps = workflow()["jobs"]["original-lot16"]["steps"]
    checkout = next(s for s in steps if s.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"] == {"ref": "${{ github.sha }}", "persist-credentials": False}
    provision = next(s for s in steps if s.get("uses") == "./.github/actions/provision-original-sources")
    assert provision["with"]["token"] == "${{ secrets.ORIGINAL_SOURCES_TOKEN }}"
    assert provision["with"]["repository"] == "${{ vars.ORIGINAL_SOURCES_REPOSITORY }}"
    assert provision["with"]["ref"] == "${{ vars.ORIGINAL_SOURCES_REF }}"
    assert provision["with"]["names"].strip() == "1. Construction Plans - Lot 16 Power (REV E).pdf"
    assert provision["with"].get("allow-missing", "false") == "false"
    proof = next(s for s in steps if s.get("name", "").startswith("Reprove original SHA"))
    assert steps.index(checkout) < steps.index(provision) < steps.index(proof)
    assert "assert sha256(data).hexdigest()==sha" in proof["run"]
    assert 'assert result.status.value=="abstained"' in proof["run"]
    assert 'assert result.evidence is None' in proof["run"]
    assert "exact_head_sha.txt" in proof["run"]


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


def test_private_original_matrix_artifacts_cannot_overwrite_each_other():
    steps = workflow()["jobs"]["original-lot16"]["steps"]
    artifact = next(s for s in steps if s.get("uses", "").startswith("actions/upload-artifact@"))
    assert "${{ matrix.python-version }}" in artifact["with"]["name"]
