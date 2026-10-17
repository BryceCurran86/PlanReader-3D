"""Coordinated CI must not weaken required checks or create a false score."""
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]
WORKFLOW=ROOT/".github/workflows/ci.yml"


def workflow():
    # BaseLoader preserves "on" as a YAML key (PyYAML's YAML1.1 loader treats
    # "on" as boolean True, which is not GitHub Actions YAML semantics).
    return yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)


def test_public_required_ci_trigger_and_check_context_stay_unchanged():
    doc=workflow()
    assert doc["name"]=="CI"
    assert doc["on"]["push"]["branches"]==["main"]
    assert doc["on"]["pull_request"]["branches"]==["main"]
    test=doc["jobs"]["test"]
    assert test["strategy"]["matrix"]["python-version"]==["3.13","3.14"]
    assert "github.event_name != 'workflow_dispatch'" in test["if"]
    steps="\\n".join(str(v) for v in test["steps"])
    assert "pytest -q tests/" in steps
    for guard in ("check_private_original_source_additions.py",
                  "check_provider_gold_isolation.py",
                  "check_full_plan_v2_integrity.py",
                  "check_v2_truth_separation.py"):
        assert guard in steps


def test_manual_modes_share_ci_no_automatic_duplicate_workflow():
    doc=workflow()
    dispatch=doc["on"]["workflow_dispatch"]["inputs"]["suite"]
    assert dispatch["options"]==["full","focused","readiness"]
    assert dispatch["default"]=="full"
    assert len(doc["jobs"])==3
    assert doc["concurrency"]["cancel-in-progress"]=="true"
    focused=doc["jobs"]["focused"]
    assert focused["if"].find("workflow_dispatch")>=0
    assert "refs/heads/main" not in focused["if"]
    assert focused["runs-on"]=="ubuntu-latest"
    assert len(focused["steps"])>1


def test_source_neutral_readiness_has_no_private_token_or_false_accuracy():
    raw=WORKFLOW.read_text()
    doc=workflow()
    for name in ("focused","readiness"):
        job=doc["jobs"][name]
        assert job["permissions"]=={"contents":"read"}
        assert "workflow_dispatch" in job["if"]
    # Source provisioning is intentionally a separate trusted owner workflow.
    assert "ORIGINAL_SOURCES_TOKEN" not in raw
    assert "pull_request_target" not in raw
    assert "upload-artifact" not in raw
    assert "UNPUBLISHED" in raw
    assert "coverage_accuracy" in raw
    assert "precision_adjusted_accuracy" in raw
    assert 'sum(p["denominator"] for p in projects) == 120' in raw
    assert 'p["coverage_accuracy"] is None' in raw


def test_focus_is_not_an_alternative_to_required_full_matrix():
    d=workflow()
    assert d["jobs"]["focused"]["if"] != d["jobs"]["test"]["if"]
    tests="\\n".join(str(x) for x in d["jobs"]["focused"]["steps"])
    assert "test_ci_coordinated_entrypoint.py" in tests
    assert "test_full_plan_v2_readiness_report.py" in tests
    assert "test_opening_host_source_candidate_witness.py" in tests
