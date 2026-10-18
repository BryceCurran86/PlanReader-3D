"""Push-to-main original-source replays are NOT RUN, never silently red or green, until provisioning exists.

The original client PDFs are untracked (#2920) and provisioning is not configured, so a workflow that sha-checks
``documents/sources/<original>.pdf`` can never pass on a push to main. Each such job carries a push gate (skipped while the
repository variable ``ORIGINAL_SOURCES_REPOSITORY`` is empty) and a sibling notice job that records the skip. Pull request and
manual runs are not gated: they keep failing closed when the original is missing (#2989). This file pins that convention.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
REUSABLE_NAME = "original-source-not-run.yml"
REUSABLE_USES = "./.github/workflows/" + REUSABLE_NAME
PUSH_GATE = "github.event_name != 'push' || vars.ORIGINAL_SOURCES_REPOSITORY != ''"
NOTICE_JOB = "original-source-not-verified"
NOTICE_IF = "github.event_name == 'push' && vars.ORIGINAL_SOURCES_REPOSITORY == ''"
SOURCE_DIRS = ("documents/sources", "benchmarks/sources")


def _triggers(workflow: dict) -> object:
    return workflow.get(True, workflow.get("on"))  # PyYAML parses a bare ``on`` key as boolean True


def push_reaches_main(workflow: dict) -> bool:
    on = _triggers(workflow)
    if isinstance(on, str):
        on = [on]
    if isinstance(on, list):
        return "push" in on
    if not isinstance(on, dict) or "push" not in on:
        return False
    push = on["push"]
    if not isinstance(push, dict):
        return True
    branches = push.get("branches")
    return branches is None or "main" in branches or any(str(b) in ("*", "**") for b in branches)


def sha_checks_original(job: dict) -> bool:
    text = yaml.dump(job)
    return "sha256sum" in text and any(token in text for token in SOURCE_DIRS)


def original_jobs(workflow: dict) -> list:
    """Job ids of a main-push-reachable workflow that sha-check an original source document."""
    if not push_reaches_main(workflow):
        return []
    return [name for name, job in (workflow.get("jobs") or {}).items() if sha_checks_original(job or {})]


def violations(workflow: dict) -> list:
    """Why this workflow does not follow the NOT RUN convention (empty when it does or does not apply)."""
    found = []
    jobs = workflow.get("jobs") or {}
    for name in original_jobs(workflow):
        if jobs[name].get("if") != PUSH_GATE:
            found.append(f"{name}: job-level push gate missing or different")
        notice = jobs.get(NOTICE_JOB)
        if not isinstance(notice, dict):
            found.append(f"{name}: no {NOTICE_JOB} job")
            continue
        if notice.get("if") != NOTICE_IF:
            found.append(f"{NOTICE_JOB}: wrong condition")
        if notice.get("uses") != REUSABLE_USES:
            found.append(f"{NOTICE_JOB}: must call {REUSABLE_USES}")
        if (notice.get("with") or {}).get("job") != name:
            found.append(f"{NOTICE_JOB}: must name the gated job {name}")
        if any(token in yaml.dump(notice) for token in SOURCE_DIRS):
            found.append(f"{NOTICE_JOB}: must not mention the source directories")
    return found


def _real_workflows() -> dict:
    return {
        path.name: yaml.safe_load(path.read_bytes().decode("utf-8"))
        for path in sorted(WORKFLOWS.glob("*.y*ml"))
    }


# ---------------------------------------------------------------------------------------------------------------------
# the real workflows
# ---------------------------------------------------------------------------------------------------------------------


def test_every_push_reachable_original_source_job_has_the_push_gate_and_notice_job():
    offenders = {}
    covered = 0
    for name, workflow in _real_workflows().items():
        gated = original_jobs(workflow)
        covered += len(gated)
        if violations(workflow):
            offenders[name] = violations(workflow)
    assert covered >= 30
    assert offenders == {}, (
        "A workflow that sha-checks an original on a push to main must add to that job "
        f"`if: {PUSH_GATE}` and a sibling job `{NOTICE_JOB}` (`if: {NOTICE_IF}`, `uses: {REUSABLE_USES}`, "
        "`with: job: <job id>`), or narrow its push trigger so it cannot reach main"
    )


def test_the_push_gate_is_only_on_original_source_jobs():
    gated_files = set()
    for path in sorted(WORKFLOWS.glob("*.y*ml")):
        workflow = yaml.safe_load(path.read_bytes().decode("utf-8"))
        for job in (workflow.get("jobs") or {}).values():
            if isinstance(job, dict) and job.get("if") == PUSH_GATE:
                gated_files.add(path.name)
    expected = {name for name, workflow in _real_workflows().items() if original_jobs(workflow)}
    assert gated_files == expected


def test_pull_request_and_manual_runs_are_never_gated():
    assert "pull_request" not in PUSH_GATE and "workflow_dispatch" not in PUSH_GATE
    for name, workflow in _real_workflows().items():
        for job_id in original_jobs(workflow):
            gate = workflow["jobs"][job_id]["if"]
            # true for every event except a push with the variable unset
            assert gate.startswith("github.event_name != 'push' ||"), name


def test_signed_output_replays_are_not_touched():
    for name, workflow in _real_workflows().items():
        if "signed" in name and "replay" in name:
            for job in (workflow.get("jobs") or {}).values():
                assert not (isinstance(job, dict) and job.get("if") == PUSH_GATE), name
            assert NOTICE_JOB not in (workflow.get("jobs") or {}), name


def test_reusable_workflow_emits_an_explicit_not_run_record():
    text = (WORKFLOWS / REUSABLE_NAME).read_bytes().decode("utf-8")
    workflow = yaml.safe_load(text)
    on = _triggers(workflow)
    assert set(on) == {"workflow_call"}  # reusable only: never triggers by itself
    assert on["workflow_call"]["inputs"]["job"]["required"] is True
    assert workflow["permissions"] == {}
    assert "::notice title=PRIVATE ORIGINAL SOURCE UNAVAILABLE::" in text
    assert "NOT RUN" in text and "not a passing original-source verification" in text
    assert "GITHUB_STEP_SUMMARY" in text
    assert not any(token in text for token in SOURCE_DIRS)  # the provisioning transform must not treat it as a reader
    # caller-controlled values reach the shell through env, never interpolated into the script
    assert "${{ inputs.job }}" not in workflow["jobs"]["notice"]["steps"][0]["run"]


def test_the_provisioning_transform_still_plans_one_step_for_each_gated_job():
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(
        "apply_provision_for_push_gate_test", ROOT / "scripts" / "apply_provision_original_sources.py"
    )
    transform = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = transform
    spec.loader.exec_module(transform)
    names = transform.manifest_names(ROOT)
    for name, workflow in _real_workflows().items():
        jobs = original_jobs(workflow)
        if not jobs:
            continue
        path = WORKFLOWS / name
        result = transform.plan_file(path, names, "main")
        steps = yaml.safe_load(result[0] if result else path.read_bytes().decode("utf-8"))["jobs"]
        for job_id in jobs:
            provisioned = [s for s in steps[job_id]["steps"] if "provision-original-sources" in str(s.get("uses", ""))]
            assert len(provisioned) <= 1, name
        assert "uses" not in steps[NOTICE_JOB] or "provision" not in steps[NOTICE_JOB]["uses"], name
        assert NOTICE_JOB not in (result[1] if result else []), name


# ---------------------------------------------------------------------------------------------------------------------
# synthetic negatives and positives
# ---------------------------------------------------------------------------------------------------------------------

GOOD = {
    "on": {"push": {"branches": ["main"]}, "pull_request": None},
    "jobs": {
        "orig": {
            "if": PUSH_GATE,
            "runs-on": "ubuntu-latest",
            "steps": [{"run": "echo \"x  documents/sources/A.pdf\" | sha256sum --check"}],
        },
        NOTICE_JOB: {"if": NOTICE_IF, "uses": REUSABLE_USES, "with": {"job": "orig"}},
    },
}


def _variant(mutate):
    import copy

    workflow = copy.deepcopy(GOOD)
    mutate(workflow)
    return workflow


def test_a_conforming_workflow_has_no_violations():
    assert original_jobs(GOOD) == ["orig"]
    assert violations(GOOD) == []


@pytest.mark.parametrize("mutate", [
    lambda w: w["jobs"]["orig"].pop("if"),
    lambda w: w["jobs"]["orig"].update({"if": "github.event_name == 'push'"}),
    # a gate that also skips pull requests would hide the fail-closed behaviour
    lambda w: w["jobs"]["orig"].update({"if": "github.event_name == 'push' && vars.ORIGINAL_SOURCES_REPOSITORY != ''"}),
    lambda w: w["jobs"].pop(NOTICE_JOB),
    lambda w: w["jobs"][NOTICE_JOB].update({"if": "always()"}),
    lambda w: w["jobs"][NOTICE_JOB].update({"uses": "./.github/workflows/other.yml"}),
    lambda w: w["jobs"][NOTICE_JOB].update({"with": {"job": "another-job"}}),
    lambda w: w["jobs"][NOTICE_JOB].update({"env": {"P": "documents/sources/A.pdf"}}),
])
def test_synthetic_violations_are_reported(mutate):
    assert violations(_variant(mutate))


def test_workflows_that_cannot_reach_main_on_push_are_out_of_scope():
    pull_request_only = _variant(lambda w: w.update({"on": {"pull_request": None}}))
    pull_request_only["jobs"].pop(NOTICE_JOB)
    pull_request_only["jobs"]["orig"].pop("if")
    assert original_jobs(pull_request_only) == []
    assert violations(pull_request_only) == []
    other_branch = _variant(lambda w: w.update({"on": {"push": {"branches": ["release"]}}}))
    assert original_jobs(other_branch) == []


def test_a_job_that_only_asserts_the_original_is_absent_is_out_of_scope():
    workflow = {
        "on": {"push": {"branches": ["main"]}},
        "jobs": {"absent": {"runs-on": "ubuntu-latest", "steps": [{"run": "test ! -f documents/sources/A.pdf"}]}},
    }
    assert original_jobs(workflow) == []
