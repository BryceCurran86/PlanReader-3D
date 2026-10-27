"""Private original proof stays owner/main-only; public PR tests need no secret."""
import ast
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
    assert "git rev-parse HEAD" in proof["run"]


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


def test_private_original_job_never_uploads_or_logs_source_derived_artifacts():
    steps = workflow()["jobs"]["original-lot16"]["steps"]
    assert not any(s.get("uses", "").startswith("actions/upload-artifact@") for s in steps)
    proof = next(s for s in steps if s.get("name", "").startswith("Reprove original SHA"))
    code = proof["run"].split("python - <<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    tree = ast.parse(code)
    prints = [node for node in ast.walk(tree)
              if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print"]
    assert prints
    assert all(not p.keywords and all(isinstance(a, ast.Constant) and type(a.value) is str for a in p.args)
               for p in prints)
    assert ".write_text(" not in code and "json.dumps" not in code
    assert "artifacts/" not in proof["run"]
    assert any(s.get("if") == "always()" and s.get("run") == "rm -rf documents/sources" for s in steps)
