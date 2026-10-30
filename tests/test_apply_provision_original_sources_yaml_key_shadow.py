"""The workflow trust check must read a workflow exactly as GitHub does.

PyYAML resolves ``on``, ``yes`` and ``true`` to the same boolean key, so a
workflow that spells a second trigger key differently could last-key-win past
the ``workflow_dispatch``-only gate. These tests use synthetic workflows only.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "apply_provision_key_shadow_under_test",
        ROOT / "scripts" / "apply_provision_original_sources.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


T = _load()
PINNED_ACTION = "0123456789abcdef0123456789abcdef01234567"
TRUSTED_MAIN_IF = (
    "github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' "
    "&& github.repository == 'BryceCurran86/PlanReader-3D'"
)
JOB = """jobs:
  replay:
    if: {condition}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{{{ github.sha }}}}
      - run: ls "documents/sources/Plan A (REV 1).pdf"
"""


def _workflow(head: str, condition: str = TRUSTED_MAIN_IF, tail: str = "") -> str:
    return head + JOB.format(condition=condition) + tail


def _root(tmp_path: Path, text: str) -> Path:
    root = tmp_path / "repo"
    (root / ".github" / "workflows").mkdir(parents=True)
    folder = root / "benchmarks" / "frozen_holdout" / "full_plan_v2" / "projects" / "p"
    folder.mkdir(parents=True)
    docs = [{"name": "Plan A (REV 1).pdf", "sha256": "0" * 64, "size_bytes": 1}]
    (folder / "source_manifest.json").write_text(
        json.dumps({"project_id": "p", "source_documents": docs}), encoding="utf-8")
    (root / ".github" / "workflows" / "synthetic.yml").write_bytes(text.encode("utf-8"))
    return root


@pytest.mark.parametrize("head", [
    "on: workflow_dispatch\n",
    "on:\n  workflow_dispatch:\n    inputs:\n      note:\n        required: false\n",
    "on: [workflow_dispatch]\n",
])
def test_the_genuine_manual_main_shape_is_still_trusted(head):
    assert T._trusted_manual_main_job(_workflow(head), "replay") is True


@pytest.mark.parametrize("shadow", [
    "true: workflow_dispatch", "True: workflow_dispatch", "TRUE: workflow_dispatch",
    "On: workflow_dispatch", "ON: workflow_dispatch", "yes: workflow_dispatch",
    "y: workflow_dispatch",
])
@pytest.mark.parametrize("order", ["shadow_after", "shadow_before"])
def test_a_second_spelling_of_the_trigger_key_cannot_hide_a_pull_request_trigger(shadow, order):
    real = "on: pull_request\n"
    head = real + shadow + "\n" if order == "shadow_after" else shadow + "\n" + real
    assert T._trusted_manual_main_job(_workflow(head), "replay") is False


@pytest.mark.parametrize("extra", ["true: pull_request", "True: push", "1: push"])
def test_a_non_string_top_level_key_beside_a_manual_trigger_abstains(extra):
    # GitHub does not read a boolean or numeric top-level key as an event, so
    # the trust check will not vouch for a workflow that carries one.
    head = "on: workflow_dispatch\n" + extra + "\n"
    assert T._trusted_manual_main_job(_workflow(head), "replay") is False


def test_a_repeated_job_condition_is_refused_whichever_copy_would_win():
    head = "on: workflow_dispatch\n"
    weak_first = _workflow(head).replace(
        "    if: " + TRUSTED_MAIN_IF + "\n",
        "    if: always()\n    if: " + TRUSTED_MAIN_IF + "\n",
    )
    trusted_first = _workflow(head).replace(
        "    if: " + TRUSTED_MAIN_IF + "\n",
        "    if: " + TRUSTED_MAIN_IF + "\n    if: always()\n",
    )
    assert "always()" in weak_first and "always()" in trusted_first
    assert T._trusted_manual_main_job(weak_first, "replay") is False
    assert T._trusted_manual_main_job(trusted_first, "replay") is False


def test_a_repeated_checkout_ref_is_refused():
    text = _workflow("on: workflow_dispatch\n").replace(
        "          ref: ${{ github.sha }}\n",
        "          ref: ${{ inputs.ref }}\n          ref: ${{ github.sha }}\n",
    )
    assert "inputs.ref" in text
    assert T._trusted_manual_main_job(text, "replay") is False


def test_a_non_mapping_or_unparseable_workflow_abstains():
    assert T._trusted_manual_main_job("- on\n- jobs\n", "replay") is False
    assert T._trusted_manual_main_job("on: [unclosed\n", "replay") is False


def test_apply_refuses_a_shadowed_pull_request_workflow_and_writes_nothing(tmp_path):
    text = _workflow("on: pull_request\ntrue: workflow_dispatch\n")
    root = _root(tmp_path, text)
    source = root / ".github" / "workflows" / "synthetic.yml"
    before = source.read_bytes()
    with pytest.raises(SystemExit, match="refusing to inject"):
        T.main(["--root", str(root), "--action-ref", PINNED_ACTION, "--apply"])
    assert source.read_bytes() == before
    assert b"secrets.ORIGINAL_SOURCES_TOKEN" not in source.read_bytes()


def test_the_strict_loader_does_not_change_pyyaml_for_anything_else():
    assert yaml.safe_load("on: 1") == {True: 1}
    assert yaml.load("on: 1", Loader=T._WorkflowLoader) == {"on": 1}
    assert yaml.load("a: true\nb: False\nc: yes", Loader=T._WorkflowLoader) == {
        "a": True, "b": False, "c": "yes"}
