"""Public push checks cannot silently claim private-original verification.

Legacy jobs retain their exact push-variable gate and reusable NOT RUN notice.
A migrated original job may instead use the already enforced owner/manual/main
source-token boundary, actual provisioning and cleanup, and an explicit public
NOT RUN notice. Merely adding a manual-looking condition is not sufficient.
"""
from __future__ import annotations

from pathlib import Path
from functools import lru_cache
import runpy

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
OWNER_MANUAL_GATE = (
    "${{ github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main'"
    " && github.actor == 'BryceCurran86' && github.triggering_actor == 'BryceCurran86' }}"
)


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


@lru_cache(maxsize=1)
def _source_token_boundary_check():
    return runpy.run_path(str(
        ROOT / "tests" / "test_gpt3_private_original_dynamic_workflow_census.py"
    ))["check_original_token_boundary"]


def guarded_owner_manual_original(workflow: dict, name: str) -> bool:
    """Reuse the existing source-token guard; never exempt a bare condition."""
    jobs = workflow.get("jobs") or {}
    job = jobs.get(name) or {}
    if (job.get("if") != OWNER_MANUAL_GATE
            or "${{ secrets.ORIGINAL_SOURCES_TOKEN }}" not in str(job)):
        return False
    public_notice = any(
        public.get("if") == "${{ github.event_name != 'workflow_dispatch' }}"
        and any(
            step.get("if") == "always()"
            and "::notice::Original PDF tests NOT RUN" in str(step.get("run", ""))
            and "GITHUB_STEP_SUMMARY" in str(step.get("run", ""))
            for step in public.get("steps", ())
        )
        for public in jobs.values() if isinstance(public, dict)
    )
    if not public_notice:
        return False
    # safe_load parses the Actions `on` key as True; normalize it before
    # passing the whole workflow to the stricter existing BaseLoader census.
    normalized = dict(workflow)
    if True in normalized:
        normalized["on"] = normalized.pop(True)
    try:
        return _source_token_boundary_check()(yaml.safe_dump(normalized)) >= 1
    except (AssertionError, KeyError, TypeError, yaml.YAMLError):
        return False


def violations(workflow: dict) -> list:
    """Why this workflow does not follow the NOT RUN convention (empty when it does or does not apply)."""
    found = []
    jobs = workflow.get("jobs") or {}
    for name in original_jobs(workflow):
        if guarded_owner_manual_original(workflow, name):
            continue
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
    # Count all original jobs, including strictly verified manual migrations;
    # migrating one must not reduce the census or hide an unsafe source job.
    assert covered >= 29
    assert offenders == {}, (
        "A workflow that sha-checks an original on a push to main must add to that job "
        f"`if: {PUSH_GATE}` and a sibling job `{NOTICE_JOB}` (`if: {NOTICE_IF}`, `uses: {REUSABLE_USES}`, "
        "`with: job: <job id>`), use the validated owner/manual/main provisioned "
        "source boundary with an explicit public NOT RUN notice, or narrow its push trigger"
    )


def test_the_push_gate_is_only_on_original_source_jobs():
    gated_files = set()
    for path in sorted(WORKFLOWS.glob("*.y*ml")):
        workflow = yaml.safe_load(path.read_bytes().decode("utf-8"))
        for job in (workflow.get("jobs") or {}).values():
            if isinstance(job, dict) and job.get("if") == PUSH_GATE:
                gated_files.add(path.name)
    expected = {
        name for name, workflow in _real_workflows().items()
        if any(not guarded_owner_manual_original(workflow, job)
               for job in original_jobs(workflow))
    }
    assert gated_files == expected


def test_pull_request_and_manual_runs_are_never_gated():
    assert "pull_request" not in PUSH_GATE and "workflow_dispatch" not in PUSH_GATE
    for name, workflow in _real_workflows().items():
        for job_id in original_jobs(workflow):
            if guarded_owner_manual_original(workflow, job_id):
                continue
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
        jobs = [job for job in original_jobs(workflow)
                if not guarded_owner_manual_original(workflow, job)]
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


@pytest.mark.parametrize("filename", [
    "test-gpt2-f07-optin-semantic-connected-cells.yml",
    "test-gpt2-a120-original-multipath-optin.yml",
])
def test_provisioned_owner_manual_migration_keeps_source_boundary_and_public_notice(filename):
    import copy

    workflow = _real_workflows()[filename]
    (name,) = original_jobs(workflow)
    assert guarded_owner_manual_original(workflow, name)
    assert violations(workflow) == []

    for mutation in ("foreign_rerun", "pull_request", "checkout", "provision", "cleanup", "notice"):
        changed = copy.deepcopy(workflow)
        job = changed["jobs"][name]
        if mutation == "foreign_rerun":
            job["if"] = job["if"].replace("github.triggering_actor == 'BryceCurran86'", "true")
        elif mutation == "pull_request":
            job["if"] = job["if"].replace("workflow_dispatch", "pull_request")
        elif mutation == "checkout":
            job["steps"][0]["with"]["ref"] = "${{ github.event.pull_request.head.sha }}"
        elif mutation == "provision":
            job["steps"] = [s for s in job["steps"] if "provision-original-sources" not in str(s)]
        elif mutation == "cleanup":
            job["steps"] = [s for s in job["steps"] if s.get("name") != "Destroy private originals"]
        else:
            del changed["jobs"]["focused-public"]
        assert not guarded_owner_manual_original(changed, name), mutation
        assert violations(changed), mutation
