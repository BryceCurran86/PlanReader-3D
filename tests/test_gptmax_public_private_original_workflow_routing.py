"""Public PR checks must not require PDFs kept exclusively in the private source repository.

These are *workflow routing* tests. Passing them says nothing about source
authentication, sealed quantities, or official four-project scoring.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
STAGES = "test-gptmax-source-authority-stages.yml"
OPTION_A = "verify-option-a-original-wall-source.yml"


def _events(workflow: dict) -> set[str]:
    value = workflow.get("on", workflow.get(True))  # YAML 1.1 treats "on" as a boolean.
    if isinstance(value, dict):
        return set(value)
    if isinstance(value, list):
        return set(value)
    return {value} if isinstance(value, str) else set()


def _contract(stages: dict, option_a: dict) -> None:
    assert "pull_request" in _events(stages)
    jobs = stages["jobs"]
    assert "diagnostic-regressions" in jobs
    assert "real-source-stages" not in jobs
    for job in jobs.values():
        text = yaml.safe_dump(job)
        assert "documents/sources/" not in text
        assert "ORIGINAL_SOURCES_TOKEN" not in text
    assert _events(option_a) == {"workflow_dispatch"}
    assert "pull_request" not in _events(option_a)
    assert "pull_request_target" not in _events(option_a)


def test_unguarded_original_source_jobs_do_not_run_on_public_prs():
    stages = yaml.safe_load((WORKFLOWS / STAGES).read_text(encoding="utf-8"))
    option_a = yaml.safe_load((WORKFLOWS / OPTION_A).read_text(encoding="utf-8"))
    _contract(stages, option_a)


@pytest.mark.parametrize("damage", ["restore_real_source", "option_a_pr", "source_secret"])
def test_contract_rejects_missing_pdf_pr_regressions(damage):
    stages = yaml.safe_load((WORKFLOWS / STAGES).read_text(encoding="utf-8"))
    option_a = yaml.safe_load((WORKFLOWS / OPTION_A).read_text(encoding="utf-8"))
    stages, option_a = deepcopy(stages), deepcopy(option_a)
    if damage == "restore_real_source":
        stages["jobs"]["real-source-stages"] = {
            "runs-on": "ubuntu-latest",
            "steps": [{"run": "python original_replay.py documents/sources/3LAUREL.pdf"}],
        }
    elif damage == "option_a_pr":
        option_a["on"] = {"pull_request": {}, "workflow_dispatch": None}
        option_a.pop(True, None)
    else:
        stages["jobs"]["diagnostic-regressions"]["steps"].append({
            "env": {"ORIGINAL_SOURCES_TOKEN": "${{ secrets.ORIGINAL_SOURCES_TOKEN }}"},
            "run": "echo source"
        })
    with pytest.raises(AssertionError):
        _contract(stages, option_a)
