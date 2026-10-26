"""Safety contract for owner-initiated, SHA-pinned private source replays."""
from pathlib import Path
import os
import subprocess
import re
import shlex
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / ".github/workflows/gpt2-trusted-original-source-replay-manual.yml"
SOURCE = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
HEADS = {
    "a600": "14d50e0b58c62e624974e481e4805a72bebb1ba7",
    "freezer": "2e2e622515db29203f6299d537b1ccb232adea30",
    "d15": "e8700f3030d66121d793f1a1924f20f7e3b2ddb9",
    "rcp": "8db7ef5c931c5f37bf63cdfbbb8b0b7a5fce29a1",
    "grid": "2fddfb5746a9f066eee318daeb40214df1a6a103",
    "rcp_ink": "794a114c3b422aa81f044f45d8f099b79b3454f1",
}


class _WorkflowLoader(yaml.SafeLoader):
    """Keep GitHub's 'on' trigger distinct from YAML 1.1 bool aliases."""


_WorkflowLoader.yaml_implicit_resolvers = {
    initial: [(tag, regex) for tag, regex in rules
              if tag != "tag:yaml.org,2002:bool"]
    for initial, rules in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_WorkflowLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    list("tTfF"),
)


def _unique_mapping(loader, node, deep=False):
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=True)
        if key in seen:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate mapping key {key!r}",
                key_node.start_mark,
            )
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)


_WorkflowLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping,
)


def _parse_workflow(raw):
    document = yaml.load(raw, Loader=_WorkflowLoader)
    assert type(document) is dict
    # A second trigger alias must not be silently discarded by YAML1.1
    # coercion, and unreviewed top-level workflow controls must not pass.
    assert set(document) == {"name", "on", "permissions", "concurrency", "jobs"}
    assert document["on"] == {"workflow_dispatch": None}
    return document


def _load():
    return _parse_workflow(FILE.read_text(encoding="utf8"))


def test_owner_only_manual_source_triggers():
    document = _load()
    assert document["on"] == {"workflow_dispatch": None}
    assert document["permissions"] == {"contents": "read"}
    assert tuple(document["jobs"]) == ("original",)
    job = document["jobs"]["original"]
    assert "github.ref == 'refs/heads/main'" in job["if"]
    assert "github.actor == 'BryceCurran86'" in job["if"]
    assert job["strategy"]["fail-fast"] is False
    assert job["strategy"]["matrix"]["target"] == list(HEADS)
    assert job["strategy"]["matrix"]["python-version"] == ["3.13", "3.14"]


@pytest.mark.parametrize("malformed_trigger", (
    "on:\n  pull_request:\ntrue:\n  workflow_dispatch:",
    "on:\n  pull_request:\nyes:\n  workflow_dispatch:",
    "on:\n  workflow_dispatch:\non:\n  pull_request:",
    "true:\n  workflow_dispatch:",
    "on:\n  pull_request:",
))
def test_trigger_alias_or_duplicate_cannot_masquerade_as_owner_manual(
    malformed_trigger,
):
    original = FILE.read_text(encoding="utf8")
    assert original.count("on:\n  workflow_dispatch:") == 1
    corrupt = original.replace("on:\n  workflow_dispatch:", malformed_trigger, 1)
    with pytest.raises((AssertionError, yaml.YAMLError)):
        _parse_workflow(corrupt)


def test_pinned_sha_allowlist_and_no_arbitrary_input():
    steps = _load()["jobs"]["original"]["steps"]
    guard = next(s for s in steps if s["name"].startswith("Validate immutable"))
    script = guard["run"]
    assert "ce322d69bbc9f47b5b2aed001684e01cbe04f48b" in script
    for target, sha in HEADS.items():
        assert target + ")" in script
        assert "approved_head=" + sha in script
    assert "git diff --name-only" in script
    assert "git checkout --detach" not in script
    assert 'git archive "$approved_head" | tar -x -C "$target_tree"' in script
    assert 'mkdir -p "$target_tree/documents/sources"' in script
    assert '[[ "$(git rev-parse HEAD)" == "$GITHUB_SHA" ]]' in script
    assert '[[ -f "$target_tree/$test_path" ]]' in script
    assert 'GPT2_APPROVED_TREE=$target_tree' in script
    assert "expected_paths=" in script
    assert "github.event.inputs" not in FILE.read_text(encoding="utf8")


def test_new_source_positive_targets_have_fixed_base_tree_and_exact_two_paths():
    """The owner-only replay may never select mutable PR code or extra files."""
    guard = next(s for s in _load()["jobs"]["original"]["steps"]
                 if s["name"].startswith("Validate immutable"))
    script = guard["run"]
    approved_base = "d66087e6471c1bbdbf8c38617b8b85e646529417"
    expected = {
        "grid": (
            "pb_gpt2_native_grid_row_membership_shadow.py|"
            "tests/test_gpt2_native_grid_row_membership_shadow.py",
            "test_private_original_d02_grid_membership_from_published_source_if_provisioned",
            "tests/test_gpt2_native_grid_row_membership_shadow.py",
        ),
        "rcp_ink": (
            "pb_gpt2_original_mary_rcp_native_word_scope_shadow.py|"
            "tests/test_gpt2_original_mary_rcp_native_word_scope_shadow.py",
            "test_real_original_page9_native_source_rivals_if_available",
            "tests/test_gpt2_original_mary_rcp_native_word_scope_shadow.py",
        ),
    }
    for target, (paths, original_test, test_path) in expected.items():
        matches = re.findall(
            r"(?m)^            " + target +
            r"\)\n(?P<body>.*?)(?=^              ;;)",
            script, flags=re.DOTALL | re.MULTILINE,
        )
        assert len(matches) == 1
        body = matches[0]
        assert "approved_base=" + approved_base in body
        assert "approved_head=" + HEADS[target] in body
        assert "expected_paths='" + paths + "'" in body
        assert "original_test=" + original_test in body
        assert "test_path=" + test_path in body
        assert "github.event.inputs" not in body
    assert "git diff --name-only" in script
    assert 'git archive "$approved_head"' in script
    assert "git checkout --detach" not in script


def test_token_only_present_in_frozen_manifest_provision_step():
    steps = _load()["jobs"]["original"]["steps"]
    matches = [s for s in steps if "ORIGINAL_SOURCES_TOKEN" in str(s)]
    assert len(matches) == 1
    source = matches[0]
    assert source["uses"] == "./.github/actions/provision-original-sources"
    assert source["with"]["token"] == "${{ secrets.ORIGINAL_SOURCES_TOKEN }}"
    assert source["with"]["repository"] == "${{ vars.ORIGINAL_SOURCES_REPOSITORY }}"
    assert source["with"]["ref"] == "${{ vars.ORIGINAL_SOURCES_REF }}"
    assert source["with"]["allow-missing"] == "false"
    assert source["with"]["names"].strip() == "Arch_Combined_Maryborough_Service_Station.pdf"
    text = FILE.read_text(encoding="utf8")
    assert SOURCE in text
    assert "actions/upload-artifact" not in text
    assert "\n  pull_request:" not in text
    assert "\n  pull_request_target:" not in text


def test_private_source_tests_only_execute_in_offline_container():
    steps = _load()["jobs"]["original"]["steps"]
    build = next(i for i, s in enumerate(steps) if s.get("name", "").startswith("Build sealed Python"))
    provision = next(i for i, s in enumerate(steps) if s.get("name", "").startswith("Provision only SHA"))
    isolated = next(i for i, s in enumerate(steps) if s.get("name", "").startswith("Run private original"))
    assert build < provision < isolated
    assert len(steps[provision + 1:-1]) == 2
    trusted_mount = steps[provision + 1]
    assert trusted_mount["name"].startswith("Verify original PDF SHA")
    assert "python -I -c" in trusted_mount["run"]
    assert "--network none --read-only --cap-drop ALL" in trusted_mount["run"]
    assert "gpt2-private-mount-integrity.log" in trusted_mount["run"]
    assert "private output withheld" in trusted_mount["run"]
    assert "EXPECTED_SHA256" in trusted_mount["env"]
    assert SOURCE == trusted_mount["env"]["EXPECTED_SHA256"]
    assert steps[provision + 2]["name"].startswith("Run private original checks")
    guard = next(s for s in steps if s.get("name", "").startswith("Validate immutable"))
    assert steps.index(guard) < build
    assert 'git checkout --detach' not in guard["run"]
    assert 'git archive "$approved_head"' in guard["run"]
    assert steps[provision]["uses"] == "./.github/actions/provision-original-sources"
    script = steps[isolated]["run"]
    for required in ("docker run --rm --network none --read-only --cap-drop ALL",
                     "--security-opt no-new-privileges", "dst=/workspace,readonly",
                     "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1", "run_test source-positive",
                     "run_test full-module", "grep -Eq", "private log withheld"):
        assert required in script
    assert '--mount "type=bind,src=$GPT2_APPROVED_TREE,dst=/workspace,readonly"' in script
    assert '--mount "type=bind,src=$GITHUB_WORKSPACE/documents/sources,dst=/workspace/documents/sources,readonly"' in script
    assert '--mount "type=bind,src=$PWD,dst=/workspace,readonly"' not in script
    assert "grep -E '^FAILED" not in script
    assert "cat \"$output\"" not in script
    assert "docker build" not in script
    assert SOURCE == steps[isolated]["env"]["PLANREADER_MARYBOROUGH_SOURCE_SHA256"]
    assert steps[-1]["if"] == "always()"
    cleanup_lines = [line.strip() for line in steps[-1]["run"].splitlines()
                     if line.strip().startswith("rm -rf ")]
    assert len(cleanup_lines) == 1
    assert set(shlex.split(cleanup_lines[0])) == {
        "rm", "-rf", "$RUNNER_TEMP/gpt2-empty-original-preflight",
        "$RUNNER_TEMP/gpt2-approved-target", "$RUNNER_TEMP/gpt2-approved-deps", "documents/sources",
    }
    assert "docker build" in steps[build]["run"]

def test_original_source_smoke_test_negative_error_is_privately_captured():
    # A deliberate negative may fail inside the shell but must not emit a
    # GitHub ::error:: annotation on the successful smoke-test run.
    smoke = ROOT / ".github/workflows/provision-original-sources-smoke.yml"
    document = yaml.safe_load(smoke.read_text(encoding="utf8"))
    check = next(step for step in document["jobs"]["provision"]["steps"]
                 if step.get("name") == "Prove the step fails closed without a token")
    script = check["run"]
    assert "ORIGINAL_SOURCES_TOKEN=" in script
    assert "denial_log=" in script
    assert "2>&1" in script
    assert 'test "${rc}" -eq 1' in script
    assert "grep -Fq 'original sources NOT provisioned:'" in script
    assert "grep -Fq 'no ORIGINAL_SOURCES_TOKEN is available'" in script
    assert 'test ! -e "${RUNNER_TEMP}/empty-sources"' in script
    assert 'rm -f "${denial_log}"' in script
    assert "Verified expected no-token refusal" in script



def test_all_approved_originals_collect_without_private_source_before_token_step():
    steps = _load()["jobs"]["original"]["steps"]
    preflight = next(i for i, s in enumerate(steps)
                     if s.get("name", "").startswith("Preflight offline pinned"))
    provision = next(i for i, s in enumerate(steps)
                     if s.get("name", "").startswith("Provision only"))
    build = next(i for i, s in enumerate(steps)
                 if s.get("name", "").startswith("Build sealed Python"))
    assert build < preflight < provision
    source_free = steps[preflight]["run"]
    assert "docker run --rm --network none --read-only --cap-drop ALL" in source_free
    assert "--collect-only" in source_free
    assert '"$GPT2_TEST_PATH::$GPT2_ORIGINAL_TEST"' in source_free
    assert "1 test collected" in source_free
    assert "gpt2-empty-original-preflight" in source_free
    assert "NO_REAL_SOURCE.txt" in source_free
    assert "dst=/workspace/documents/sources,readonly" in source_free
    assert "PLANREADER_MARYBOROUGH_ORIGINAL_PDF" not in source_free
    assert "ORIGINAL_SOURCES_TOKEN" not in source_free
    assert "> \"$output\" 2>&1" in source_free
    assert "no private source accessed" in source_free


def test_private_failure_reports_only_fixed_categories_and_exit_status():
    steps = _load()["jobs"]["original"]["steps"]
    isolated = next(s for s in steps
                    if s.get("name", "").startswith("Run private original"))
    run = isolated["run"]
    assert 'docker_rc=0' in run and '|| docker_rc=$?' in run
    assert 'if (( docker_rc != 0 )); then' in run
    assert 'case "$docker_rc" in' in run
    assert 'reason=container_launch_failure' in run
    assert 'reason=pytest_collection_or_runtime_failure' in run
    for category in ("missing_python_module", "python_import_error",
                     "missing_file_in_container", "container_permission_error",
                     "container_readonly_filesystem", "pytest_no_collector"):
        assert "reason=" + category in run
    assert "private log withheld" in run
    assert 'cat "$output"' not in run
    assert "grep -E '^FAILED" not in run
    assert "actions/upload-artifact" not in FILE.read_text(encoding="utf8")
    assert 'rm -f "$RUNNER_TEMP/gpt2-private-isolated.log" "$RUNNER_TEMP/gpt2-private-preflight.log"' in steps[-1]["run"]

def _approved_dependency_image_context_contract(raw: str) -> bool:
    """The networked build may see approved dependency bytes, not moving main."""
    try:
        steps = _parse_workflow(raw)["jobs"]["original"]["steps"]
        build = next(step["run"] for step in steps
                     if step["name"].startswith("Build sealed Python"))
        cleanup = steps[-1]["run"]
        assert 'deps_dir="$RUNNER_TEMP/gpt2-approved-deps"' in build
        assert 'mkdir -p "$deps_dir"' in build
        assert 'cp -- "$GPT2_APPROVED_TREE/requirements.txt" "$GPT2_APPROVED_TREE/requirements-ci-v1228.txt" "$deps_dir/"' in build
        assert 'docker build -q -f "$dockerfile" -t "gpt2-offline:${{ matrix.python-version }}" "$deps_dir"' in build
        assert 'rm -rf "$RUNNER_TEMP/gpt2-empty-original-preflight" "$RUNNER_TEMP/gpt2-approved-target" "$RUNNER_TEMP/gpt2-approved-deps" documents/sources' in cleanup
    except (AssertionError, KeyError, StopIteration, TypeError, yaml.YAMLError):
        return False
    return True


@pytest.mark.parametrize(("old", "new"), (
    ('cp -- "$GPT2_APPROVED_TREE/requirements.txt" "$GPT2_APPROVED_TREE/requirements-ci-v1228.txt" "$deps_dir/"',
     'cp -- requirements.txt requirements-ci-v1228.txt "$deps_dir/"'),
    ('docker build -q -f "$dockerfile" -t "gpt2-offline:${{ matrix.python-version }}" "$deps_dir"',
     'docker build -q -f "$dockerfile" -t "gpt2-offline:${{ matrix.python-version }}" .'),
    ('deps_dir="$RUNNER_TEMP/gpt2-approved-deps"', 'deps_dir="$GITHUB_WORKSPACE"'),
    ('rm -rf "$RUNNER_TEMP/gpt2-empty-original-preflight" "$RUNNER_TEMP/gpt2-approved-target" "$RUNNER_TEMP/gpt2-approved-deps" documents/sources',
     'rm -rf "$RUNNER_TEMP/gpt2-empty-original-preflight" "$RUNNER_TEMP/gpt2-approved-target" documents/sources'),
))
def test_moving_main_dependency_context_mutations_are_rejected(old, new):
    original = FILE.read_text(encoding="utf8")
    assert _approved_dependency_image_context_contract(original)
    assert original.count(old) == 1
    assert not _approved_dependency_image_context_contract(original.replace(old, new, 1))


def test_offline_image_copies_only_approved_dependency_bytes(tmp_path):
    """Execute the actual workflow copy command with deliberately divergent main."""
    main = tmp_path / "moving-main"
    approved = tmp_path / "approved-snapshot"
    deps = tmp_path / "image-context"
    for directory in (main, approved, deps):
        directory.mkdir()
    for filename in ("requirements.txt", "requirements-ci-v1228.txt"):
        (main / filename).write_text("main-only==99\n", encoding="utf8")
        (approved / filename).write_text("approved-only==1\n", encoding="utf8")
    (main / "private-original.pdf").write_bytes(b"NEVER COPY")
    (approved / "candidate-code.py").write_text("pass\n", encoding="utf8")
    steps = _load()["jobs"]["original"]["steps"]
    build = next(step["run"] for step in steps
                 if step["name"].startswith("Build sealed Python"))
    copy_lines = [line.strip() for line in build.splitlines()
                  if line.strip().startswith("cp -- ")]
    assert len(copy_lines) == 1
    env = os.environ.copy()
    env.update(GPT2_APPROVED_TREE=str(approved), deps_dir=str(deps))
    subprocess.run(["bash", "-c", "set -euo pipefail\n" + copy_lines[0]],
                   cwd=main, env=env, check=True, capture_output=True, text=True)
    assert sorted(path.name for path in deps.iterdir()) == [
        "requirements-ci-v1228.txt", "requirements.txt",
    ]
    for filename in ("requirements.txt", "requirements-ci-v1228.txt"):
        assert (deps / filename).read_bytes() == (approved / filename).read_bytes()
        assert (deps / filename).read_bytes() != (main / filename).read_bytes()
