"""The workflow transform that adds the provisioning step: one inserted step per job that reads the originals, nothing else."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("apply_provision_under_test", ROOT / "scripts" / "apply_provision_original_sources.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


T = _load()
NAMES = ["Plan A (REV 1).pdf", "Plan B.pdf"]

LF_WORKFLOW = """name: Synthetic
on:
  pull_request:
    paths:
      - tools/x.py
jobs:
  needs-a:
    runs-on: ubuntu-latest
    steps:
      # keep this comment where it is
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha || github.sha }}
      - uses: actions/setup-python@v5
      - name: Use the original
        run: |
          PDF='documents/sources/Plan A (REV 1).pdf'
          python -m tools.x --pdf "$PDF"
  no-sources:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo nothing here
  whole-suite:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - run: PYTHONPATH=. pytest -q tests/
  directory-only:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: ls documents/sources
  no-checkout:
    runs-on: ubuntu-latest
    steps:
      - run: cat documents/sources/Plan B.pdf
"""


def _write(tmp_path: Path, text: str, eol: str = "\n") -> Path:
    root = tmp_path / "repo"
    (root / ".github" / "workflows").mkdir(parents=True)
    folder = root / "benchmarks" / "frozen_holdout" / "full_plan_v2" / "projects" / "p"
    folder.mkdir(parents=True)
    docs = [{"name": n, "sha256": "0" * 64, "size_bytes": 1} for n in NAMES]
    (folder / "source_manifest.json").write_text(json.dumps({"project_id": "p", "source_documents": docs}), encoding="utf-8")
    workflow = root / ".github" / "workflows" / "synthetic.yml"
    workflow.write_bytes(text.replace("\n", eol).encode("utf-8"))
    return root


def _plan(root: Path, ref: str = "main"):
    path = root / ".github" / "workflows" / "synthetic.yml"
    return path, T.plan_file(path, T.manifest_names(root), ref)


def test_only_jobs_that_read_the_originals_get_a_step_after_checkout(tmp_path):
    root = _write(tmp_path, LF_WORKFLOW)
    _path, (new, changed, skipped) = _plan(root)
    assert changed == ["needs-a", "whole-suite", "directory-only"]
    assert skipped == ["no-checkout"]
    jobs = yaml.safe_load(new)["jobs"]
    for job in changed:
        steps = jobs[job]["steps"]
        index = next(i for i, s in enumerate(steps) if "actions/checkout" in str(s.get("uses", "")))
        assert "provision-original-sources" in steps[index + 1]["uses"]
        assert steps[index + 1]["with"]["token"] == "${{ secrets.ORIGINAL_SOURCES_TOKEN }}"
    assert not any("provision" in str(s.get("uses", "")) for s in jobs["no-sources"]["steps"] + jobs["no-checkout"]["steps"])


def test_step_names_exactly_the_manifest_files_the_job_mentions(tmp_path):
    root = _write(tmp_path, LF_WORKFLOW)
    _path, (new, _changed, _skipped) = _plan(root)
    jobs = yaml.safe_load(new)["jobs"]
    assert jobs["needs-a"]["steps"][1]["with"]["names"].strip() == "Plan A (REV 1).pdf"
    # whole-suite and directory-only jobs get every document (no names key)
    assert "names" not in jobs["whole-suite"]["steps"][1]["with"]
    assert "names" not in jobs["directory-only"]["steps"][1]["with"]


def test_removing_the_inserted_lines_restores_the_original_bytes_for_lf_and_crlf(tmp_path):
    for eol in ("\n", "\r\n"):
        root = _write(tmp_path / ("lf" if eol == "\n" else "crlf"), LF_WORKFLOW, eol)
        path, (new, _changed, _skipped) = _plan(root)
        original = path.read_bytes().decode("utf-8")
        assert eol in new and (eol == "\r\n" or "\r" not in new)
        kept = []
        skipping = False
        for line in new.split(eol):
            if line.lstrip().startswith("- name: Provision original sources"):
                skipping = True
                indent = len(line) - len(line.lstrip())
                continue
            if skipping:
                if line.strip() and (len(line) - len(line.lstrip())) <= indent:
                    skipping = False
                else:
                    continue
            kept.append(line)
        assert eol.join(kept) == original


def test_second_run_changes_nothing(tmp_path):
    root = _write(tmp_path, LF_WORKFLOW)
    path, (new, _changed, _skipped) = _plan(root)
    path.write_bytes(new.encode("utf-8"))
    _path, again = _plan(root)
    assert again is None or again[1] == []


def test_local_action_reference_and_pinned_reference_forms(tmp_path):
    root = _write(tmp_path, LF_WORKFLOW)
    _p, (local, _c, _s) = _plan(root, "local")
    _p, (pinned, _c, _s) = _plan(root, "0123456789abcdef0123456789abcdef01234567")
    assert "uses: ./.github/actions/provision-original-sources" in local
    assert "uses: BryceCurran86/PlanReader-3D/.github/actions/provision-original-sources@0123456789abcdef0123456789abcdef01234567" in pinned


def test_comments_and_other_steps_are_untouched(tmp_path):
    root = _write(tmp_path, LF_WORKFLOW)
    _p, (new, _c, _s) = _plan(root)
    assert "      # keep this comment where it is\n      - uses: actions/checkout@v4" in new
    before, after = yaml.safe_load(LF_WORKFLOW), yaml.safe_load(new)
    for job in ("no-sources", "no-checkout"):
        assert before["jobs"][job] == after["jobs"][job]


def test_apply_writes_files_and_dry_run_does_not(tmp_path, capsys):
    root = _write(tmp_path, LF_WORKFLOW)
    workflow = root / ".github" / "workflows" / "synthetic.yml"
    original = workflow.read_bytes()
    assert T.main(["--root", str(root)]) == 0
    assert workflow.read_bytes() == original
    assert "would change 1 workflow file(s), 3 job(s)" in capsys.readouterr().out
    assert T.main(["--root", str(root), "--apply"]) == 0
    assert workflow.read_bytes() != original
    assert "provision-original-sources" in workflow.read_text(encoding="utf-8")


@pytest.mark.parametrize("command", ["pytest -q tests/", "python -m pytest -q tests/ -x", "pytest tests", "PYTHONPATH=. python -m pytest -q tests/ "])
def test_whole_suite_commands_are_detected(command):
    assert T.WHOLE_SUITE.search(command)


@pytest.mark.parametrize("command", ["pytest -q tests/test_a.py", "python -m pytest tests/test_a.py tests/test_b.py", "echo tests/", "pytest -q tests_other/"])
def test_file_specific_commands_are_not_whole_suite(command):
    assert not T.WHOLE_SUITE.search(command)


# ---------------------------------------------------------------------------------------------------------------------
# the real workflows (read only)
# ---------------------------------------------------------------------------------------------------------------------


def test_real_workflows_every_original_reading_job_gets_exactly_one_step_before_or_after_the_rewrite():
    """Valid before the transform is applied (it plans the steps) and after (they are already there)."""
    names = T.manifest_names(ROOT)
    reading = 0
    left_alone = set()
    for path in sorted((ROOT / ".github" / "workflows").glob("*.y*ml")):
        raw = path.read_bytes().decode("utf-8")
        result = T.plan_file(path, names, "main")
        assert path.read_bytes().decode("utf-8") == raw  # planning never writes
        new = raw if result is None else result[0]
        if result is not None:
            left_alone.update((path.name, job) for job in result[2])
        eol = "\r\n" if "\r\n" in new else "\n"
        lines = new.split(eol)
        for job, (first, last) in T._job_spans(lines).items():
            text = eol.join(lines[first:last])
            if T.reads_originals(text) and (path.name, job) not in T.EXCLUDED_JOBS:
                reading += 1
                steps = yaml.safe_load(new)["jobs"][job]["steps"]
                assert sum("provision-original-sources" in str(s.get("uses", "")) for s in steps) == 1, (path.name, job)
    assert reading > 100
    assert left_alone <= set(T.EXCLUDED_JOBS), f"jobs left without the originals that are not deliberately excluded: {left_alone}"


def test_ci_workflow_test_job_is_provisioned_with_every_document_before_or_after_the_rewrite():
    names = T.manifest_names(ROOT)
    path = ROOT / ".github" / "workflows" / "ci.yml"
    result = T.plan_file(path, names, "main")
    new = path.read_bytes().decode("utf-8") if result is None else result[0]
    steps = yaml.safe_load(new)["jobs"]["test"]["steps"]
    step = next(s for s in steps if "provision-original-sources" in str(s.get("uses", "")))
    assert "names" not in step["with"]


ARTIFACT_WORKFLOW = """name: Synthetic upload
on: [workflow_dispatch]
jobs:
  broad:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python tool.py documents/sources/Plan B.pdf
      - uses: actions/upload-artifact@v4
        with:
          name: everything
          path: .
  narrow:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python tool.py documents/sources/Plan B.pdf
      - uses: actions/upload-artifact@v4
        with:
          name: results
          path: |
            artifacts/out
            ${{ runner.temp }}/report.json
"""


def test_a_job_whose_artifact_could_publish_the_originals_is_refused(tmp_path):
    root = _write(tmp_path, ARTIFACT_WORKFLOW)
    _path, (new, changed, skipped) = _plan(root)
    assert changed == ["narrow"] and skipped == ["broad"]
    jobs = yaml.safe_load(new)["jobs"]
    assert not any("provision" in str(s.get("uses", "")) for s in jobs["broad"]["steps"])
    assert any("provision" in str(s.get("uses", "")) for s in jobs["narrow"]["steps"])


@pytest.mark.parametrize("path, unsafe", [
    (".", True), ("./", True), ("**", True), ("documents", True), ("documents/sources/x.pdf", True),
    ("${{ github.workspace }}", True), ("artifacts/gpt3", False), ("${{ runner.temp }}/x.json", False), ("results.json", False)])
def test_unsafe_artifact_path_rules(path, unsafe):
    step = {"uses": "actions/upload-artifact@v4", "with": {"name": "n", "path": path}}
    assert bool(T.unsafe_artifact_paths([step])) is unsafe
    assert not T.unsafe_artifact_paths([{"uses": "actions/checkout@v4", "with": {"path": "."}}])


def test_no_real_workflow_uploads_a_path_that_could_include_the_originals():
    """The standing guarantee behind the exclusion rule: today no workflow publishes the workspace or documents/."""
    offenders = []
    for path in sorted((ROOT / ".github" / "workflows").glob("*.y*ml")):
        for job, body in ((yaml.safe_load(path.read_bytes().decode("utf-8")) or {}).get("jobs") or {}).items():
            if T.unsafe_artifact_paths((body or {}).get("steps") or []):
                offenders.append((path.name, job))
    assert offenders == []


def test_only_restricts_the_rewrite_to_matching_workflow_files(tmp_path, capsys):
    root = _write(tmp_path, LF_WORKFLOW)
    other = root / ".github" / "workflows" / "other.yml"
    other.write_bytes(LF_WORKFLOW.encode("utf-8"))
    assert T.main(["--root", str(root), "--only", "synth*.yml", "--apply"]) == 0
    assert "provision-original-sources" in (root / ".github" / "workflows" / "synthetic.yml").read_text(encoding="utf-8")
    assert other.read_bytes() == LF_WORKFLOW.encode("utf-8")
    assert "changed 1 workflow file(s), 3 job(s)" in capsys.readouterr().out


# ---------------------------------------------------------------------------------------------------------------------
# a job that asserts the originals are ABSENT is never given them
# ---------------------------------------------------------------------------------------------------------------------

ABSENCE_ONLY_WORKFLOW = """name: Synthetic absence
on:
  pull_request:
jobs:
  absent-policy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Verify private PDF not present in public checkout
        run: |
          set -euo pipefail
          test ! -f documents/sources/Plan B.pdf
"""

MIXED_WORKFLOW = ABSENCE_ONLY_WORKFLOW + """  reads-original:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python -m tools.x --pdf 'documents/sources/Plan A (REV 1).pdf'
"""


@pytest.mark.parametrize("command", [
    "test ! -f documents/sources/Plan B.pdf",
    "test ! -e 'documents/sources/Plan B.pdf'",
    "test ! -d benchmarks/sources",
    "[ ! -f documents/sources/Plan B.pdf ]",
    "[[ ! -e \"documents/sources/Plan B.pdf\" ]]",
    "! test -f documents/sources/Plan B.pdf",
    "  test  !  -f  ./documents/sources/Plan B.pdf",
])
def test_absence_assertions_are_detected(command):
    assert T.asserts_originals_absent("run: " + command)


@pytest.mark.parametrize("command", [
    "test -f documents/sources/Plan B.pdf",
    "[ -f documents/sources/Plan B.pdf ]",
    "test ! -f docs/other/Plan B.pdf",
    "ls documents/sources",
    "cat documents/sources/Plan B.pdf",
    "contest ! -f documents/sources/Plan B.pdf",
])
def test_presence_checks_and_reads_are_not_absence_assertions(command):
    assert not T.asserts_originals_absent("run: " + command)


def test_a_job_that_asserts_the_original_is_absent_is_skipped_and_left_unchanged(tmp_path):
    root = _write(tmp_path, ABSENCE_ONLY_WORKFLOW)
    path, (new, changed, skipped) = _plan(root)
    assert changed == []
    assert skipped == ["absent-policy"]
    assert new == path.read_bytes().decode("utf-8")
    assert "provision-original-sources" not in new


def test_in_a_mixed_workflow_only_the_reading_job_gets_the_step(tmp_path):
    root = _write(tmp_path, MIXED_WORKFLOW)
    _path, (new, changed, skipped) = _plan(root)
    assert changed == ["reads-original"]
    assert skipped == ["absent-policy"]
    jobs = yaml.safe_load(new)["jobs"]
    assert not any("provision" in str(s.get("uses", "")) for s in jobs["absent-policy"]["steps"])
    assert sum("provision-original-sources" in str(s.get("uses", "")) for s in jobs["reads-original"]["steps"]) == 1


def test_second_run_over_a_mixed_workflow_changes_nothing(tmp_path):
    root = _write(tmp_path, MIXED_WORKFLOW)
    path, (new, _changed, _skipped) = _plan(root)
    path.write_bytes(new.encode("utf-8"))
    _path, (again, changed, skipped) = _plan(root)
    assert changed == []
    assert skipped == ["absent-policy"]
    assert again == new


def test_the_real_private_original_policy_job_is_excluded_and_never_rewritten():
    name, job = "test-gpt2-private-original-ci-policy.yml", "absent-private-source-synthetic-policy"
    assert (name, job) in T.EXCLUDED_JOBS
    path = ROOT / ".github" / "workflows" / name
    text = path.read_bytes().decode("utf-8")
    jobs = yaml.safe_load(text)["jobs"]
    assert job in jobs
    assert T.asserts_originals_absent(text)  # excluded by rule as well as by name
    result = T.plan_file(path, T.manifest_names(ROOT), "main")
    assert result is not None
    new, changed, skipped = result
    assert changed == [] and skipped == [job]
    assert new == text


def test_every_real_job_with_an_absence_assertion_is_deliberately_excluded():
    offenders = []
    for path in sorted((ROOT / ".github" / "workflows").glob("*.y*ml")):
        raw = path.read_bytes().decode("utf-8")
        eol = "\r\n" if "\r\n" in raw else "\n"
        lines = raw.split(eol)
        for job, (first, last) in T._job_spans(lines).items():
            if T.asserts_originals_absent(eol.join(lines[first:last])) and (path.name, job) not in T.EXCLUDED_JOBS:
                offenders.append((path.name, job))
    assert offenders == []
