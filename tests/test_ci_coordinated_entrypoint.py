"""Required CI remains intact; manual consolidation cannot fake a score.

Avoid a new PyYAML runtime dependency: these guards inspect the original
GitHub Actions file text and exact top-level structural markers. The Actions
runner is the authoritative workflow schema validator.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/ci.yml"


def source() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def job(name: str) -> str:
    text = source().split("\njobs:\n", 1)[1]
    marker = f"  {name}:\n"
    assert text.count(marker) == 1
    tail = text.split(marker, 1)[1]
    next_job = re.search(r"(?m)^  [a-z][a-z0-9_-]*:\s*$", tail)
    return tail[:next_job.start()] if next_job else tail


def test_public_required_ci_trigger_and_check_context_stay_unchanged():
    text = source()
    assert text.startswith("name: CI\n")
    assert "  push:\n    branches: [main]" in text
    assert "  pull_request:\n    branches: [main]" in text
    full = job("test")
    assert "python-version: [\"3.13\", \"3.14\"]" in full
    assert "github.event_name != 'workflow_dispatch'" in full
    # The full suite still runs the whole tests/ tree; "-rs" (list skipped tests) was added with the public-CI
    # private-original policy (#2989), so allow it without allowing a narrower selection.
    assert re.search(r"PYTHONPATH=\. pytest -q(?: -rs)? tests/(?:\s|$)", full)
    for guard in ("check_private_original_source_additions.py",
                  "check_provider_gold_isolation.py",
                  "check_full_plan_v2_integrity.py",
                  "check_v2_truth_separation.py"):
        assert guard in full


def test_manual_suites_do_not_create_duplicate_automatic_triggers():
    text = source()
    assert text.count("  workflow_dispatch:") == 1
    assert "    inputs:\n      suite:" in text
    assert "        default: full" in text
    for mode in ("full", "focused", "readiness"):
        assert f"          - {mode}" in text
    assert "  cancel-in-progress: true" in text
    assert len(re.findall(r"(?m)^  (?:test|focused|readiness):$", text)) == 3
    assert "workflow_dispatch" in job("focused")
    assert "runs-on: ubuntu-latest" in job("focused")


def test_source_neutral_readiness_has_no_client_secrets_or_score_claim():
    text = source()
    for name in ("focused", "readiness"):
        section = job(name)
        assert "workflow_dispatch" in section
        assert "permissions:\n      contents: read" in section
    assert "ORIGINAL_SOURCES_TOKEN" not in text
    assert "pull_request_target" not in text
    assert "upload-artifact" not in text
    assert "UNPUBLISHED" in text
    assert "coverage_accuracy" in text
    assert "precision_adjusted_accuracy" in text
    assert 'sum(p["denominator"] for p in projects) == 120' in text
    assert 'p["coverage_accuracy"] is None' in text


def test_focus_is_not_an_alternative_to_required_full_ci():
    full, focused = job("test"), job("focused")
    assert "inputs.suite == 'full'" in full
    assert "inputs.suite == 'focused'" in focused
    assert "test_ci_coordinated_entrypoint.py" in focused
    assert "test_full_plan_v2_readiness_report.py" in focused
    assert "test_opening_host_source_candidate_witness.py" in focused
