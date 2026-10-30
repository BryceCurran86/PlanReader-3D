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
    "a600": "f32e01ed58369bf400a7a91a0360fd25963b3d1a",
    "freezer": "2e2e622515db29203f6299d537b1ccb232adea30",
    "d15": "e8700f3030d66121d793f1a1924f20f7e3b2ddb9",
    "rcp": "8db7ef5c931c5f37bf63cdfbbb8b0b7a5fce29a1",
    "grid": "9b0657d54957061a46148857226250500ad35f57",
    "rcp_ink": "20c0b7e9978683ddb1e6f6490bfbfd8c2db259f6",
    "d15_ink": "c52f45f3365b74f3b4070ea051e338329f09de76",
    "finish_page": "cb19b928982f8565f86443af11c7e2ccc0c5f672",
    "office_caps": "80ab45ddb082f3364cd9c7f429814f921e8b889d",
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



def _target_matrix_expression():
    # Never interpolate caller-provided text into the JSON matrix or shell.
    # Only five immutable reviewed targets may be individually selected;
    # the default preserves the full historical matrix.
    all_targets = "[" + ",".join('"' + target + '"' for target in HEADS) + "]"
    return (
        "${{ fromJSON(inputs.target == 'a600' && '[\"a600\"]' "
        "|| inputs.target == 'grid' && '[\"grid\"]' "
        "|| inputs.target == 'rcp_ink' && '[\"rcp_ink\"]' "
        "|| inputs.target == 'finish_page' && '[\"finish_page\"]' "
        "|| inputs.target == 'office_caps' && '[\"office_caps\"]' "
        "|| '" + all_targets + "') }}"
    )


def _parse_workflow(raw):
    document = yaml.load(raw, Loader=_WorkflowLoader)
    assert type(document) is dict
    # A second trigger alias must not be silently discarded by YAML1.1
    # coercion, and unreviewed top-level workflow controls must not pass.
    assert set(document) == {"name", "on", "permissions", "concurrency", "jobs"}
    assert document["on"] == {"workflow_dispatch": {"inputs": {"target": {
        "description": "Select one immutable original replay or all approved targets",
        "required": True,
        "type": "choice",
        "default": "all",
        "options": ["all", "a600", "grid", "rcp_ink", "finish_page", "office_caps"],
    }}}}
    return document


def _load():
    return _parse_workflow(FILE.read_text(encoding="utf8"))


def test_owner_only_manual_source_triggers():
    document = _load()
    assert document["on"] == {"workflow_dispatch": {"inputs": {"target": {
        "description": "Select one immutable original replay or all approved targets",
        "required": True,
        "type": "choice",
        "default": "all",
        "options": ["all", "a600", "grid", "rcp_ink", "finish_page", "office_caps"],
    }}}}
    assert document["permissions"] == {"contents": "read"}
    assert tuple(document["jobs"]) == ("original",)
    job = document["jobs"]["original"]
    assert "github.ref == 'refs/heads/main'" in job["if"]
    assert "github.actor == 'BryceCurran86'" in job["if"]
    # GitHub re-runs keep the original actor's privileges, while the user who
    # clicked rerun is github.triggering_actor. A non-owner writer must not
    # re-run an owner-secret job under the owner's original identity.
    assert job["if"] == (
        "${{ github.event_name == 'workflow_dispatch' && "
        "github.ref == 'refs/heads/main' && "
        "github.actor == 'BryceCurran86' && "
        "github.triggering_actor == 'BryceCurran86' }}"
    )
    assert job["strategy"]["fail-fast"] is False
    assert job["strategy"]["matrix"]["target"] == _target_matrix_expression()
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


@pytest.mark.parametrize(
    "event,ref,initial_actor,rerun_actor,allowed",
    (
        ("workflow_dispatch", "refs/heads/main", "BryceCurran86", "BryceCurran86", True),
        ("workflow_dispatch", "refs/heads/main", "BryceCurran86", "OtherWriter", False),
        ("workflow_dispatch", "refs/heads/main", "OtherWriter", "BryceCurran86", False),
        ("workflow_dispatch", "refs/heads/feature", "BryceCurran86", "BryceCurran86", False),
        ("push", "refs/heads/main", "BryceCurran86", "BryceCurran86", False),
    ),
)
def test_owner_only_rerun_guard_boolean_matrix(
    event, ref, initial_actor, rerun_actor, allowed,
):
    """Evaluate only the fixed equality/AND grammar accepted by the contract."""
    expression = _load()["jobs"]["original"]["if"]
    assert expression.startswith("${{ ") and expression.endswith(" }}")
    clauses = expression[4:-3].split(" && ")
    assert len(clauses) == 4
    context = {
        "github.event_name": event,
        "github.ref": ref,
        "github.actor": initial_actor,
        "github.triggering_actor": rerun_actor,
    }
    result = True
    for clause in clauses:
        key, separator, quoted = clause.partition(" == ")
        assert separator and key in context
        assert quoted.startswith("'") and quoted.endswith("'")
        result = result and context[key] == quoted[1:-1]
    assert result is allowed


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
    approved_base = "65dc4684fbcf1ce36c704457d896fc7c12a651de"
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
            r"(?m)^  " + re.escape(target) +
            r"\)\n(?P<body>.*?)(?=^    ;;)",
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


def test_new_immutable_targets_are_collected_source_free_before_private_replay():
    """Source-free public CI must test both newly allowlisted immutable trees."""
    workflow = ROOT / ".github/workflows/test-gpt2-offline-collection-no-original.yml"
    raw = workflow.read_text(encoding="utf8")
    document = _parse_workflow(FILE.read_text(encoding="utf8"))
    assert document["on"] == {"workflow_dispatch": {"inputs": {"target": {
        "description": "Select one immutable original replay or all approved targets",
        "required": True,
        "type": "choice",
        "default": "all",
        "options": ["all", "a600", "grid", "rcp_ink", "finish_page", "office_caps"],
    }}}}
    expected = {
        "grid": (
            "tests/test_gpt2_native_grid_row_membership_shadow.py",
            "test_private_original_d02_grid_membership_from_published_source_if_provisioned",
            "test_original_ruled_row_connects_multiple_native_blocks_without_grants",
        ),
        "rcp_ink": (
            "tests/test_gpt2_original_mary_rcp_native_word_scope_shadow.py",
            "test_real_original_page9_native_source_rivals_if_available",
            "test_later_native_text_whitespace_advance_is_not_painted_overprint",
        ),
    }
    for label, (path, original, synthetic) in expected.items():
        row = (
            label + "|" + HEADS[label] + "|" + path + "::" + original
            + "|" + path + "::" + synthetic
        )
        assert raw.count(row + "\n") == 1
    assert "--network none --read-only --cap-drop ALL" in raw
    assert "python -m pytest --collect-only" in raw
    assert "python -m pytest -q" in raw
    assert "PLANREADER_MARYBOROUGH_ORIGINAL_PDF" not in raw
    assert "ORIGINAL_SOURCES_TOKEN" not in raw
    assert "secrets." not in raw


def test_d15_ink_immutable_source_positive_target_is_exact_and_source_free():
    """New D15 glyph-order head must pass only owner/main offline private replay."""
    guard = next(step for step in _load()["jobs"]["original"]["steps"]
                 if step["name"].startswith("Validate immutable"))
    script = guard["run"]
    matches = re.findall(
        r"(?m)^  d15_ink\)\n(?P<body>.*?)(?=^    ;;)",
        script, flags=re.DOTALL | re.MULTILINE,
    )
    assert len(matches) == 1
    body = matches[0]
    assert "approved_base=b4a9994a98d3d2d8463c490469176f0724b780cc" in body
    assert "approved_head=" + HEADS["d15_ink"] in body
    assert (
        "expected_paths='pb_gpt2_mary_original_figured_door_leader_shadow.py|"
        "tests/test_gpt2_mary_original_figured_door_leader_shadow.py'"
    ) in body
    assert (
        "original_test=test_private_original_maryborough_native_leader_source_if_provisioned"
    ) in body
    assert "test_path=tests/test_gpt2_mary_original_figured_door_leader_shadow.py" in body
    assert "github.event.inputs" not in body
    public = (ROOT / ".github/workflows/test-gpt2-offline-collection-no-original.yml"
              ).read_text(encoding="utf8")
    row = (
        "d15_ink|" + HEADS["d15_ink"]
        + "|tests/test_gpt2_mary_original_figured_door_leader_shadow.py::"
        "test_private_original_maryborough_native_leader_source_if_provisioned"
        "|tests/test_gpt2_mary_original_figured_door_leader_shadow.py::"
        "test_genuine_horizontal_figured_word_remains_source_only_not_a_door"
    )
    assert public.count(row + "\n") == 1
    assert "ORIGINAL_SOURCES_TOKEN" not in public
    assert "PLANREADER_MARYBOROUGH_ORIGINAL_PDF" not in public
    assert "--network none --read-only --cap-drop ALL" in public


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


def test_immutable_allowlist_requires_normal_git_blobs_before_any_private_source():
    """Reject symlinks, gitlinks, exec bits and missing entries before archive."""
    steps = _load()["jobs"]["original"]["steps"]
    guard_idx = next(i for i, s in enumerate(steps)
                     if s.get("name", "").startswith("Validate immutable"))
    provision_idx = next(i for i, s in enumerate(steps)
                         if s.get("name", "").startswith("Provision only"))
    assert guard_idx < provision_idx
    script = steps[guard_idx]["run"]
    name_check = script.index('git diff --name-only')
    type_check = script.index('git ls-tree --format=')
    archive = script.index('git archive "$approved_head"')
    assert name_check < type_check < archive
    assert 'while IFS= read -r expected_path' in script
    assert 'done <<< "$allowed"' in script
    assert 'entry="$(git ls-tree --format=' in script
    assert '[[ "$entry" != "100644 blob $expected_path" ]]' in script
    assert 'Approved GPT2 source/test path has unreviewed Git object type or mode' in script
    assert 'github.event.inputs' not in script


@pytest.mark.parametrize("git_mode", ("100644", "100755", "120000", "160000"))
def test_real_git_tree_mode_gate_fail_closed(tmp_path, git_mode):
    """Exercise Git's actual ls-tree mode/type output, without a private PDF."""
    repo = tmp_path / "git-object-modes"
    repo.mkdir()

    def git(*args, input_text=None):
        proc = subprocess.run(
            ["git", "-C", str(repo), *args], input=input_text,
            encoding="utf-8", capture_output=True, check=True,
        )
        return proc.stdout.strip()

    git("init", "-q")
    blob_sha = git("hash-object", "-w", "--stdin", input_text="dummy\n")
    if git_mode == "160000":
        # A gitlink refers to a commit, never to an ordinary Python blob.
        tree_sha = git("mktree", input_text="")
        item_sha = git(
            "-c", "user.name=GPT2", "-c", "user.email=gpt2@example.invalid",
            "commit-tree", tree_sha, "-m", "synthetic-submodule",
        )
    else:
        item_sha = blob_sha
    git("update-index", "--add", "--cacheinfo",
        f"{git_mode},{item_sha},reviewed.py")
    candidate = git("write-tree")
    entry = git(
        "ls-tree", "--format=%(objectmode) %(objecttype) %(path)",
        candidate, "--", "reviewed.py",
    )
    assert (entry == "100644 blob reviewed.py") is (git_mode == "100644")
    assert git(
        "ls-tree", "--format=%(objectmode) %(objecttype) %(path)",
        candidate, "--", "missing.py",
    ) == ""


def test_finish_page_source_positive_is_exact_tree_and_never_public_secret():
    """A140/A110 source negative is owner/main-only; no PR-run private source."""
    guard = next(s for s in _load()["jobs"]["original"]["steps"]
                 if s["name"].startswith("Validate immutable"))
    script = guard["run"]
    match = re.search(
        r"(?m)^  finish_page\)\n(?P<body>.*?)(?=^    ;;)",
        script, flags=re.DOTALL | re.MULTILINE,
    )
    assert match is not None
    body = match.group("body")
    assert "approved_base=f4fd0f786411b45784f77c784546df0ae5f67d6b" in body
    assert "approved_head=" + HEADS["finish_page"] in body
    assert (
        "expected_paths='pb_source_floor_finish_occurrence_ownership_shadow.py|"
        "pb_source_full_plan_recovery_engine_shadow.py|"
        "tests/test_source_floor_finish_occurrence_ownership_shadow.py|"
        "tests/test_source_full_plan_recovery_engine_shadow.py'"
    ) in body
    original_test = (
        "test_private_original_maryborough_p11_ft3_foreign_page_abstains_if_provisioned"
    )
    assert "original_test=" + original_test in body
    assert "test_path=tests/test_source_full_plan_recovery_engine_shadow.py" in body
    assert "github.event.inputs" not in body
    assert "git diff --name-only" in script
    assert "git ls-tree" in script
    assert "100644 blob $expected_path" in script
    assert 'git archive "$approved_head"' in script
    assert "git checkout --detach" not in script

    public = (ROOT / ".github/workflows/test-gpt2-offline-collection-no-original.yml"
              ).read_text(encoding="utf8")
    row = (
        "finish_page|" + HEADS["finish_page"]
        + "|tests/test_source_full_plan_recovery_engine_shadow.py::"
        + original_test
        + "|tests/test_source_full_plan_recovery_engine_shadow.py::"
        + "test_foreign_page_finish_not_recovered_by_full_plan_shadow_engine"
    )
    assert public.count(row + "\n") == 1
    assert "--network none --read-only --cap-drop ALL" in public
    assert "python -m pytest --collect-only" in public
    assert "python -m pytest -q" in public
    assert "ORIGINAL_SOURCES_TOKEN" not in public
    assert "PLANREADER_MARYBOROUGH_ORIGINAL_PDF" not in public
    assert "secrets." not in public
    trusted = FILE.read_text(encoding="utf8")
    assert trusted.count("on:\n  workflow_dispatch:") == 1
    assert "\n  pull_request:" not in trusted
    assert "\n  pull_request_target:" not in trusted
    assert "actions/upload-artifact" not in trusted


def test_office_caps_original_replay_pin_is_immutable_and_source_free():
    """Only the reviewed OFFICE cap source/test tree can meet private PDF."""
    guard = next(step for step in _load()["jobs"]["original"]["steps"]
                 if step["name"].startswith("Validate immutable"))
    script = guard["run"]
    matches = re.findall(
        r"(?m)^  office_caps\)\n(?P<body>.*?)(?=^    ;;)",
        script, flags=re.DOTALL | re.MULTILINE,
    )
    assert len(matches) == 1
    body = matches[0]
    assert "approved_base=6be737582400c739c41420c19962e9b30b9c7d37" in body
    assert "approved_head=" + HEADS["office_caps"] in body
    assert (
        "expected_paths='pb_gpt2_original_native_crossview_wall_caps_shadow.py|"
        "tests/test_gpt2_original_native_crossview_wall_caps_shadow.py'"
    ) in body
    assert "original_test=test_original_maryborough_p7_p11_when_owner_pdf_provisioned" in body
    assert "test_path=tests/test_gpt2_original_native_crossview_wall_caps_shadow.py" in body
    assert "github.event.inputs" not in body
    assert 'git diff --name-only "$approved_base" "$approved_head"' in script
    assert 'git archive "$approved_head" | tar -x -C "$target_tree"' in script
    assert 'git ls-tree --format=' in script
    assert 'entry" != "100644 blob $expected_path"' in script

    public = (ROOT / ".github/workflows/test-gpt2-offline-collection-no-original.yml"
              ).read_text(encoding="utf8")
    row = (
        "office_caps|" + HEADS["office_caps"]
        + "|tests/test_gpt2_original_native_crossview_wall_caps_shadow.py::"
        "test_original_maryborough_p7_p11_when_owner_pdf_provisioned"
        "|tests/test_gpt2_original_native_crossview_wall_caps_shadow.py::"
        "test_exact_original_two_cap_ink_selects_one_candidate_not_physical_wall"
    )
    assert public.count(row + "\n") == 1
    assert "--network none --read-only --cap-drop ALL" in public
    assert "python -m pytest --collect-only" in public
    assert "python -m pytest -q" in public
    assert "PLANREADER_MARYBOROUGH_ORIGINAL_PDF" not in public
    assert "ORIGINAL_SOURCES_TOKEN" not in public
    assert "secrets." not in public

def test_manual_replay_selects_only_static_reviewed_targets():
    """A selected original-positive replay must run only its reviewed target."""
    document = _load()
    assert document["on"]["workflow_dispatch"]["inputs"]["target"]["options"] == [
        "all", "a600", "grid", "rcp_ink", "finish_page", "office_caps",
    ]
    job = document["jobs"]["original"]
    matrix = job["strategy"]["matrix"]
    assert matrix["python-version"] == ["3.13", "3.14"]
    assert matrix["target"] == _target_matrix_expression()
    assert 'format(' not in matrix["target"]
    assert 'github.event.inputs' not in matrix["target"]
    assert "github.actor == 'BryceCurran86'" in job["if"]
    assert "github.ref == 'refs/heads/main'" in job["if"]
    guard = next(s for s in job["steps"] if s["name"].startswith("Validate immutable"))
    for label, sha in HEADS.items():
        assert label + ")" in guard["run"]
        assert "approved_head=" + sha in guard["run"]
    assert "ORIGINAL_SOURCES_TOKEN" not in matrix["target"]
    assert "--network none --read-only --cap-drop ALL" in next(
        s["run"] for s in job["steps"] if s["name"].startswith("Run private original")
    )


def test_public_offline_matrix_exactly_matches_trusted_private_target_pins():
    """A public source-free PASS must attest the SAME immutable tree as private replay."""
    raw = (ROOT / ".github/workflows/test-gpt2-offline-collection-no-original.yml").read_text(encoding="utf8")
    marker = "          done <<'TARGETS'\n"
    assert raw.count(marker) == 1
    section = raw.split(marker, 1)[1].split("\n          TARGETS", 1)[0]
    rows = [line.strip().split("|") for line in section.splitlines() if line.strip()]
    assert len(rows) == len(HEADS)
    assert {row[0] for row in rows} == set(HEADS)
    assert len({row[0] for row in rows}) == len(rows)
    guard = next(step for step in _load()["jobs"]["original"]["steps"]
                 if step["name"].startswith("Validate immutable"))
    script = guard["run"]
    for label, sha, original_id, synthetic_id in rows:
        assert re.fullmatch(r"[0-9a-f]{40}", sha)
        assert sha == HEADS[label]
        path, separator, original_test = original_id.partition("::")
        assert separator and path.startswith("tests/") and original_test.startswith("test_")
        synthetic_path, separator, synthetic_test = synthetic_id.partition("::")
        assert separator and synthetic_path.startswith("tests/") and synthetic_test.startswith("test_")
        assert synthetic_path == path
        match = re.search(
            r"(?ms)^  " + re.escape(label) + r"\)\n(.*?)^    ;;",
            script,
        )
        assert match is not None
        case = match.group(1)
        assert "approved_head=" + sha in case
        assert "test_path=" + path in case
        assert "original_test=" + original_test in case
    assert "ORIGINAL_SOURCES_TOKEN" not in raw
    assert "PLANREADER_MARYBOROUGH_ORIGINAL_PDF" not in raw
    assert "secrets." not in raw


def test_latest_gpt2_private_replay_pins_match_public_sourcefree_smoke():
    """Owner-only source-positive targets and public source-free heads stay aligned."""
    guard = next(s for s in _load()["jobs"]["original"]["steps"]
                 if s["name"].startswith("Validate immutable"))["run"]
    public = (ROOT / ".github/workflows/test-gpt2-offline-collection-no-original.yml"
              ).read_text(encoding="utf8")
    for target, expected_base, paths in (
        ("a600", "65dc4684fbcf1ce36c704457d896fc7c12a651de",
         "pb_gpt2_original_a600_table_row_scope_shadow.py|"
         "pb_source_door_schedule_authority.py|"
         "pb_source_plan_door_correspondence_authority.py|"
         "tests/test_gpt2_original_a600_table_row_scope_shadow.py"),
        ("grid", "65dc4684fbcf1ce36c704457d896fc7c12a651de",
         "pb_gpt2_native_grid_row_membership_shadow.py|"
         "tests/test_gpt2_native_grid_row_membership_shadow.py"),
        ("rcp_ink", "837befe133e89db7d5cb5878bff141e1e6d08923",
         "pb_gpt2_original_mary_rcp_native_word_scope_shadow.py|"
         "tests/test_gpt2_original_mary_rcp_native_word_scope_shadow.py"),
    ):
        match = re.search(
            r"(?m)^  " + re.escape(target) +
            r"\)\n(?P<body>.*?)(?=^    ;;)",
            guard, flags=re.DOTALL | re.MULTILINE,
        )
        assert match is not None
        body = match.group("body")
        assert "approved_base=" + expected_base in body
        assert "approved_head=" + HEADS[target] in body
        assert "expected_paths='" + paths + "'" in body
        assert public.count(target + "|" + HEADS[target] + "|") == 1
    assert "ORIGINAL_SOURCES_TOKEN" not in public
    assert "PLANREADER_MARYBOROUGH_ORIGINAL_PDF" not in public
    assert "secrets." not in public


def _rcp_ink_exact_sourcefree_pin_contract(manual_raw, offline_raw):
    """Current RCP candidate must be compared to the reviewed post-#4136 base."""
    try:
        steps = _parse_workflow(manual_raw)["jobs"]["original"]["steps"]
        guard = next(step["run"] for step in steps
                     if step["name"].startswith("Validate immutable"))
        blocks = re.findall(
            r"(?m)^  rcp_ink\)\n(?P<body>.*?)(?=^    ;;)",
            guard, flags=re.DOTALL | re.MULTILINE,
        )
        if len(blocks) != 1:
            return False
        body = blocks[0]
        row = (
            "rcp_ink|" + HEADS["rcp_ink"] + "|"
            "tests/test_gpt2_original_mary_rcp_native_word_scope_shadow.py::"
            "test_real_original_page9_native_source_rivals_if_available|"
            "tests/test_gpt2_original_mary_rcp_native_word_scope_shadow.py::"
            "test_later_native_text_whitespace_advance_is_not_painted_overprint"
        )
        return all((
            "approved_base=837befe133e89db7d5cb5878bff141e1e6d08923" in body,
            "approved_head=" + HEADS["rcp_ink"] in body,
            "expected_paths='pb_gpt2_original_mary_rcp_native_word_scope_shadow.py|"
            "tests/test_gpt2_original_mary_rcp_native_word_scope_shadow.py'" in body,
            "original_test=test_real_original_page9_native_source_rivals_if_available" in body,
            "test_path=tests/test_gpt2_original_mary_rcp_native_word_scope_shadow.py" in body,
            offline_raw.count(row + "\n") == 1,
            "ORIGINAL_SOURCES_TOKEN" not in offline_raw,
            "PLANREADER_MARYBOROUGH_ORIGINAL_PDF" not in offline_raw,
            "--network none --read-only --cap-drop ALL" in offline_raw,
        ))
    except (AssertionError, KeyError, StopIteration, TypeError, yaml.YAMLError):
        return False


def test_rcp_ink_replay_current_head_and_reviewed_base_are_consistent():
    public = (ROOT / ".github/workflows/test-gpt2-offline-collection-no-original.yml"
              ).read_text(encoding="utf8")
    assert _rcp_ink_exact_sourcefree_pin_contract(
        FILE.read_text(encoding="utf8"), public,
    )


@pytest.mark.parametrize(("target", "old", "new"), (
    ("manual", "approved_base=837befe133e89db7d5cb5878bff141e1e6d08923",
     "approved_base=65dc4684fbcf1ce36c704457d896fc7c12a651de"),
    ("manual", "approved_head=20c0b7e9978683ddb1e6f6490bfbfd8c2db259f6",
     "approved_head=bd9aff98dd1bc644b14de916e8f88e8f7159cadc"),
    ("public", "rcp_ink|20c0b7e9978683ddb1e6f6490bfbfd8c2db259f6|",
     "rcp_ink|bd9aff98dd1bc644b14de916e8f88e8f7159cadc|"),
))
def test_rcp_ink_stale_base_or_head_pin_mutations_fail_closed(target, old, new):
    manual = FILE.read_text(encoding="utf8")
    public = (ROOT / ".github/workflows/test-gpt2-offline-collection-no-original.yml"
              ).read_text(encoding="utf8")
    assert _rcp_ink_exact_sourcefree_pin_contract(manual, public)
    if target == "manual":
        assert manual.count(old) == 1
        manual = manual.replace(old, new, 1)
    else:
        assert public.count(old) == 1
        public = public.replace(old, new, 1)
    assert not _rcp_ink_exact_sourcefree_pin_contract(manual, public)
