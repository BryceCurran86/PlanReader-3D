"""Owner-only protected source compute may use public runners without exposing originals."""
import ast
from pathlib import Path
import re

import yaml

PATH = Path(__file__).resolve().parents[1] / ".github/workflows/gptmax-protected-lot16-fixed-receipts-public.yml"


def workflow():
    return yaml.load(PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_no_pull_request_or_arbitrary_input_can_receive_private_sources():
    data = workflow()
    assert set(data["on"]) == {"workflow_dispatch", "push"}
    assert data["on"]["push"]["branches"] == ["main"]
    assert data["on"]["push"]["paths"] == [".github/workflows/gptmax-protected-lot16-fixed-receipts-public.yml"]
    assert data["on"]["workflow_dispatch"] in (None, "")
    gate = data["jobs"]["acceptance"]["if"]
    for condition in ("github.ref == 'refs/heads/main'", "github.actor == 'BryceCurran86'",
                      "github.triggering_actor == 'BryceCurran86'",
                      "github.repository == 'BryceCurran86/PlanReader-3D'"):
        assert condition in gate
    assert "pull_request" not in data["on"]
    assert data["permissions"] == {"contents": "read"}


def test_producer_and_dependency_trees_are_fixed_before_source_access():
    job = workflow()["jobs"]["acceptance"]
    for key in ("BASE_SHA", "CANDIDATE_SHA", "TRUSTED_SHA"):
        assert re.fullmatch("[0-9a-f]{40}", job["env"][key])
    steps = job["steps"]
    checkouts = [s for s in steps if s.get("uses") == "actions/checkout@v4"]
    assert len(checkouts) == 1
    assert checkouts[0]["with"]["ref"] == "${{ github.sha }}"
    assert all(s["with"]["persist-credentials"] == "false" for s in checkouts)
    first_secret = next(i for i, s in enumerate(steps) if "ORIGINAL_SOURCES_TOKEN" in s.get("env", {}))
    for name in ("Verify fixed reviewed tree, allowed paths and frozen input identity",
                 "Build isolated dependencies before receiving private inputs"):
        assert next(i for i, s in enumerate(steps) if s.get("name") == name) < first_secret
    proof = next(s["run"] for s in steps if s.get("name") == "Verify fixed reviewed tree, allowed paths and frozen input identity")
    assert 'git archive "$CANDIDATE_SHA"' in proof
    assert 'git archive "$TRUSTED_SHA"' in proof
    assert "git('diff', '--name-only', base, candidate)" in proof
    assert "72937edeae5874321862e93b05056f67ea3aadba" in proof
    assert "requirements-ci-v1228.txt" in proof
    assert "inputs." not in PATH.read_text(encoding="utf-8")


def test_private_credentials_only_reach_inert_staging_and_trusted_provisioner():
    steps = workflow()["jobs"]["acceptance"]["steps"]
    secret_steps = [s for s in steps if "ORIGINAL_SOURCES_TOKEN" in s.get("env", {})]
    assert len(secret_steps) == 1
    stage = provision = secret_steps[0]
    assert "git/blobs/" in stage["run"]
    assert "hashlib.sha1" in stage["run"]
    assert "os.O_EXCL" in stage["run"]
    assert "lot16-fixed-trusted/.github/actions/provision-original-sources/provision.py" in provision["run"]
    assert '--manifest-root "$RUNNER_TEMP/lot16-fixed-trusted/benchmarks/' in provision["run"]
    assert "--allow-missing false" in provision["run"]
    assert "--ref 387a0792c25de7d67d34540cea52ac2228a09cbd" in provision["run"]
    for step in secret_steps:
        assert "docker run" not in step["run"]
        assert "python -m tools." not in step["run"]


def test_all_private_execution_is_readonly_no_network_and_has_no_credentials():
    steps = workflow()["jobs"]["acceptance"]["steps"]
    containers = [s for s in steps if "docker run " in s.get("run", "")]
    assert len(containers) == 2
    for step in containers:
        command = step["run"]
        assert "--network none" in command and "--read-only" in command
        assert "--cap-drop ALL" in command and "--security-opt no-new-privileges" in command
        assert "--pids-limit 256" in command and "--memory 6g" in command
        assert "ORIGINAL_SOURCES_TOKEN" not in command
        assert not step.get("env")
        assert "dst=/workspace,readonly" in command
        assert "dst=/acceptance,readonly" in command
        assert "--privileged" not in command and "docker.sock" not in command
    run = next(s["run"] for s in containers if "operation verification verify" in s["run"])
    assert "dst=/workspace/documents/sources,readonly" in run
    for command in ("operation roster roster", "operation off run off", "operation on run on",
                    "operation retention retention", "operation verification verify"):
        assert command in run
    assert "PROTECTED_RETENTION_TESTS_SKIPPED=0" in run
    assert "FROZEN_V2_DENOMINATOR_UNCHANGED=120" in run


def test_private_logs_are_filtered_and_unconditionally_removed():
    steps = workflow()["jobs"]["acceptance"]["steps"]
    run = next(s["run"] for s in steps if "operation verification verify" in s.get("run", ""))
    assert 'PRIVATE_SOURCE_ACCEPTANCE_FAILED=$phase' in run
    assert "allowed.fullmatch(line)" in run
    assert "OFFICIAL_FOUR_PROJECT_SCORE_GRANTED" in run
    assert "cat " not in run
    assert not any(s.get("uses", "").startswith("actions/upload-artifact") for s in steps)
    cleanup = steps[-1]
    assert cleanup["if"] == "always()"
    assert "test ! -e documents/sources" in cleanup["run"]
    for folder in ("lot16-fixed-harness", "lot16-fixed-output"):
        assert folder in cleanup["run"]
        assert 'test ! -e "$RUNNER_TEMP/' + folder + '"' in cleanup["run"]


def test_embedded_python_parses_without_execution():
    for step in workflow()["jobs"]["acceptance"]["steps"]:
        for fragment in step.get("run", "").split("<<'PY'\n")[1:]:
            ast.parse(fragment.split("\nPY", 1)[0])
