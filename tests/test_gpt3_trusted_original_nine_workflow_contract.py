"""Fail-closed static security contract for owner-only source-positive GPT3 replay.

No benchmark, original PDF, secrets or producer authority is used by this test.
"""
import ast
from pathlib import Path
import os
import re
import subprocess
import sys

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/gpt3-trusted-original-nine-replay-manual.yml"
APPROVED = "296f48e8d89496afd96b4eda5a2e65f18285227b"
BASE = "a8d0fa5ef2dc0db3e1171ab8e8558bf9448f1e94"
OWNER_REPOSITORY_GUARD = (
    "${{ github.event_name == 'workflow_dispatch' && "
    "github.ref == 'refs/heads/main' && github.actor == 'BryceCurran86' && "
    "github.repository == 'BryceCurran86/PlanReader-3D' && "
    "github.triggering_actor == 'BryceCurran86' }}"
)


class StrictWorkflowLoader(yaml.SafeLoader):
    pass


StrictWorkflowLoader.yaml_implicit_resolvers = {
    start: [(tag, rule) for tag, rule in rules if tag != "tag:yaml.org,2002:bool"]
    for start, rules in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
StrictWorkflowLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    list("tTfF"),
)


def _unique(loader, node, deep=False):
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=True)
        if type(key) not in (str, int, bool) or key in seen:
            raise yaml.constructor.ConstructorError(None, None, "duplicate or invalid YAML key", key_node.start_mark)
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)


StrictWorkflowLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique,
)


def _parse(raw):
    doc = yaml.load(raw, Loader=StrictWorkflowLoader)
    assert type(doc) is dict
    assert set(doc) == {"name", "on", "permissions", "concurrency", "jobs"}
    assert doc["on"] == {"workflow_dispatch": None}
    return doc


def _load():
    return _parse(WORKFLOW.read_text(encoding="utf-8"))


def test_main_owner_only_immutable_source_positive_workflow():
    doc = _load()
    assert doc["permissions"] == {"contents": "read"}
    assert tuple(doc["jobs"]) == ("original",)
    job = doc["jobs"]["original"]
    assert job["if"] == OWNER_REPOSITORY_GUARD
    for fragment in ("github.event_name == 'workflow_dispatch'", "github.ref == 'refs/heads/main'",
                     "github.actor == 'BryceCurran86'",
                     "github.repository == 'BryceCurran86/PlanReader-3D'",
                     "github.triggering_actor == 'BryceCurran86'"):
        assert fragment in job["if"]
    assert job["strategy"]["fail-fast"] is False
    assert job["strategy"]["matrix"]["python-version"] == ["3.13", "3.14"]
    steps = job["steps"]
    guards = [x for x in steps if x.get("name", "").startswith("Authenticate immutable")]
    assert len(guards) == 1
    script = guards[0]["run"]
    for required in (APPROVED, BASE, "git diff --name-only", '[[ "$observed" == "$expected" ]]',
                     'git archive "$approved_head" | tar -x -C "$target_tree"',
                     'mkdir -p "$target_tree/documents/sources"',
                     '[[ "$(git rev-parse HEAD)" == "$GITHUB_SHA" ]]',
                     'test -f .github/actions/provision-original-sources/action.yml',
                     'git diff --no-renames --name-only "$approved_base" "$GITHUB_SHA"',
                     "comm -12", 'if [[ -n "$conflicting" ]]',
                     "Trusted main modified an immutable GPT3 release path",
                     "GPT3_APPROVED_TREE=$target_tree", "git status --porcelain"):
        assert required in script
    assert "git checkout --detach" not in script
    assert "tests/test_gpt3_lot16_original_nine_whole_retention.py" in script
    # Source is received only after unchanged code and dependencies are checked.
    source_index = next(i for i, x in enumerate(steps) if "ORIGINAL_SOURCES_TOKEN" in str(x))
    guard_index = steps.index(guards[0])
    build_index = next(i for i, x in enumerate(steps) if x.get("name", "").startswith("Build offline"))
    assert guard_index < build_index < source_index
    build_script = steps[build_index]["run"]
    assert 'deps_dir="$RUNNER_TEMP/gpt3-approved-deps"' in build_script
    assert 'cp -- "$GPT3_APPROVED_TREE/requirements.txt" "$GPT3_APPROVED_TREE/requirements-ci-v1228.txt" "$deps_dir/"' in build_script
    assert 'docker build -q -f "$dockerfile" -t "gpt3-offline:${{ matrix.python-version }}" "$deps_dir"' in build_script
    assert 'docker run' not in build_script
    assert "git checkout --detach" not in WORKFLOW.read_text(encoding="utf-8")
    secret = steps[source_index]
    assert secret["uses"] == "./.github/actions/provision-original-sources"
    assert secret["with"]["token"] == "${{ secrets.ORIGINAL_SOURCES_TOKEN }}"
    assert secret["with"]["allow-missing"] == "false"
    assert secret["with"]["names"].strip() == "1. Construction Plans - Lot 16 Power (REV E).pdf"
    assert sum("ORIGINAL_SOURCES_TOKEN" in str(x) for x in steps) == 1
    test_step = next(x for x in steps if x.get("name", "").startswith("Require two original"))
    assert steps.index(test_step) > source_index
    assert steps.index(test_step) == source_index + 1
    for required in ("tests/test_gpt3_lot16_original_nine_whole_retention.py",
                     '1 passed', 'skipped',
                     "docker run --rm --network none --read-only --cap-drop ALL",
                     "--security-opt no-new-privileges",
                     '--mount "type=bind,src=$GPT3_APPROVED_TREE,dst=/workspace,readonly"',
                     '--mount "type=bind,src=$GITHUB_WORKSPACE/documents/sources,dst=/workspace/documents/sources,readonly"',
                     "-e PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
                     '"-p", "no:cacheprovider"', "private details withheld"):
        assert required in test_step["run"]
    assert 'grep -E \'^(FAILED |ERROR )\'' not in test_step["run"]
    assert 'cat "$output"' not in test_step["run"]
    assert 'python -m pip install' not in test_step["run"]
    assert steps[-1]["if"] == "always()"
    assert 'rm -rf "$RUNNER_TEMP/gpt3-approved-candidate" "$RUNNER_TEMP/gpt3-approved-deps" documents/sources' in steps[-1]["run"]
    assert "gpt3-owner-original-positive.log" in steps[-1]["run"]
    assert "gpt3-offline.Dockerfile" in steps[-1]["run"]
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert "actions/upload-artifact" not in raw
    assert "github.event.inputs" not in raw
    assert re.search(r"\n\s+pull_request(?:_target)?:", raw) is None
    assert re.search(r"\n\s+workflow_call:", raw) is None


@pytest.mark.parametrize("replacement", [
    "on:\n  pull_request:",
    "on:\n  pull_request:\ntrue:\n  workflow_dispatch:",
    "on:\n  pull_request:\nyes:\n  workflow_dispatch:",
    "on:\n  workflow_dispatch:\non:\n  pull_request:",
    "true:\n  workflow_dispatch:",
    "on:\n  push:",
])
def test_untrusted_or_duplicate_trigger_cannot_be_parsed_as_owner_manual(replacement):
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert raw.count("on:\n  workflow_dispatch:") == 1
    with pytest.raises((yaml.YAMLError, AssertionError)):
        _parse(raw.replace("on:\n  workflow_dispatch:", replacement, 1))


def _isolated_private_source_contract(raw: str) -> bool:
    """Fail closed when a future edit weakens the trusted-main provisioner."""
    try:
        doc = _parse(raw)
        job = doc["jobs"]["original"]
        steps = job["steps"]
        assert job["if"] == OWNER_REPOSITORY_GUARD
        checkout, guard, build, provision, execute, cleanup = steps
        assert checkout["uses"] == "actions/checkout@v4"
        assert checkout["with"]["persist-credentials"] is False
        assert 'git archive "$approved_head"' in guard["run"]
        assert 'git diff --no-renames --name-only "$approved_base" "$GITHUB_SHA"' in guard["run"]
        assert "comm -12" in guard["run"]
        assert 'if [[ -n "$conflicting" ]]' in guard["run"]
        assert "Trusted main modified an immutable GPT3 release path" in guard["run"]
        assert "git checkout --detach" not in raw
        assert '[[ "$(git rev-parse HEAD)" == "$GITHUB_SHA" ]]' in guard["run"]
        assert 'deps_dir="$RUNNER_TEMP/gpt3-approved-deps"' in build["run"]
        assert 'cp -- "$GPT3_APPROVED_TREE/requirements.txt" "$GPT3_APPROVED_TREE/requirements-ci-v1228.txt" "$deps_dir/"' in build["run"]
        assert 'docker build -q -f "$dockerfile" -t "gpt3-offline:${{ matrix.python-version }}" "$deps_dir"' in build["run"]
        assert "ORIGINAL_SOURCES_TOKEN" not in str(build)
        assert provision["uses"] == "./.github/actions/provision-original-sources"
        assert provision["with"]["token"] == "${{ secrets.ORIGINAL_SOURCES_TOKEN }}"
        script = execute["run"]
        # The SAME immutable original pytest first reauthenticates the SHA/size
        # inside the source-mounted offline container, then runs both issuers.
        # The temporary duplicate preflight introduced a runtime regression.
        # This must stay ONE isolated read-only invocation, never a host run.
        assert script.count("docker run --rm") == 1
        prefix = "if ! docker run --rm "
        assert script.count(prefix) == 1
        run = script.split(prefix, 1)[1].split(' > "$output" 2>&1; then', 1)[0]
        assert run.startswith("--network none --read-only --cap-drop ALL")
        for required in (
            "--security-opt no-new-privileges",
            "--pids-limit 256",
            '--mount "type=bind,src=$GPT3_APPROVED_TREE,dst=/workspace,readonly"',
            '--mount "type=bind,src=$GITHUB_WORKSPACE/documents/sources,dst=/workspace/documents/sources,readonly"',
            "--workdir /workspace",
            '"gpt3-offline:${{ matrix.python-version }}"',
            "python -c '",
        ):
            assert run.count(required) == 1
        # Pinned test occurs in source read, traceback scope and pytest invocation.
        assert run.count("tests/test_gpt3_lot16_original_nine_whole_retention.py") == 3
        assert '"tests/test_gpt3_lot16_original_nine_whole_retention.py"])' in run
        assert "python -c 'import hashlib,json,fitz;" not in script
        assert "grep -Eq" in script and "skipped" in script
        assert "private details withheld" in script
        assert cleanup["if"] == "always()"
        assert 'rm -rf "$RUNNER_TEMP/gpt3-approved-candidate" "$RUNNER_TEMP/gpt3-approved-deps" documents/sources' in cleanup["run"]
    except (AssertionError, KeyError, TypeError, ValueError, yaml.YAMLError):
        return False
    return True


def test_private_source_token_never_reaches_candidate_tree_on_host():
    assert _isolated_private_source_contract(WORKFLOW.read_text(encoding="utf-8"))


@pytest.mark.parametrize(("old", "new"), [
    ('git archive "$approved_head"', 'git checkout --detach "$approved_head"'),
    ('--network none', '--network host'),
    ('--read-only --cap-drop ALL', '--cap-drop ALL'),
    ('dst=/workspace,readonly', 'dst=/workspace'),
    ('dst=/workspace/documents/sources,readonly', 'dst=/workspace/documents/sources'),
    ('github.actor == \'BryceCurran86\'', "github.actor == 'attacker'"),
    ("github.triggering_actor == 'BryceCurran86'",
     "github.triggering_actor == 'foreign-writer'"),
    ("github.triggering_actor == 'BryceCurran86'",
     "github.triggering_actor != 'foreign-writer'"),
    (" && github.triggering_actor ==", " || github.triggering_actor =="),
    (" && github.triggering_actor ==", " && true && github.triggering_actor =="),
    ("github.event_name == 'workflow_dispatch'",
     "github.event_name == 'pull_request'"),
    ("github.ref == 'refs/heads/main'",
     "github.ref == 'refs/heads/feature'"),
    ("github.repository == 'BryceCurran86/PlanReader-3D'",
     "github.repository == 'attacker/PlanReader-3D'"),
    ("github.repository == 'BryceCurran86/PlanReader-3D'",
     "github.repository != 'attacker/PlanReader-3D'"),
    ("&& github.repository ==", "|| github.repository =="),
    (" && github.repository == 'BryceCurran86/PlanReader-3D'", ""),
    ('persist-credentials: false', 'persist-credentials: true'),
    ('git diff --no-renames --name-only "$approved_base" "$GITHUB_SHA"',
     'git diff --name-only "$approved_base" "$GITHUB_SHA"'),
    ('cp -- "$GPT3_APPROVED_TREE/requirements.txt" "$GPT3_APPROVED_TREE/requirements-ci-v1228.txt" "$deps_dir/"',
     'cp -- requirements.txt requirements-ci-v1228.txt "$deps_dir/"'),
    ('docker build -q -f "$dockerfile" -t "gpt3-offline:${{ matrix.python-version }}" "$deps_dir"',
     'docker build -q -f "$dockerfile" -t "gpt3-offline:${{ matrix.python-version }}" .'),
    ('comm -12', 'comm -23'),
    ('if [[ -n "$conflicting" ]]', 'if [[ -z "$conflicting" ]]'),
    ('rm -rf "$RUNNER_TEMP/gpt3-approved-candidate" "$RUNNER_TEMP/gpt3-approved-deps" documents/sources',
     'rm -rf "$RUNNER_TEMP/gpt3-approved-candidate" documents/sources'),
])
def test_trust_boundary_mutations_cannot_certify_owner_source(old, new):
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert old in raw
    assert _isolated_private_source_contract(raw)
    assert not _isolated_private_source_contract(raw.replace(old, new, 1))


def test_git_rename_of_approved_source_path_remains_visible_to_overlap_veto(tmp_path):
    """Git's default rename detection hides an approved source path when moved.

    A rename away from an approved path is a MAIN incompatibility and must be
    present in the intersection of approved candidate paths with changed main.
    This is pure synthetic Git: no owner PDFs or benchmark truth are needed.
    """
    def git(*args):
        run = subprocess.run(
            ["git", *args], cwd=tmp_path, text=True,
            capture_output=True, check=True,
        )
        return run.stdout.strip()

    git("init", "-q")
    git("config", "user.name", "GPT3 source-neutral test")
    git("config", "user.email", "test@example.invalid")
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "approved.py").write_text(
        "def trusted():\n    return 'immutable'\n", encoding="utf-8",
    )
    git("add", ".")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD")
    git("mv", "tools/approved.py", "tools/renamed.py")
    git("commit", "-qm", "rename")
    final = git("rev-parse", "HEAD")
    default_paths = git("diff", "--name-only", base, final).splitlines()
    unchanged_path_dropped = "tools/approved.py" not in default_paths
    assert unchanged_path_dropped, default_paths
    original_and_destination = git(
        "diff", "--no-renames", "--name-only", base, final,
    ).splitlines()
    assert original_and_destination == ["tools/approved.py", "tools/renamed.py"]
    approved_paths = {"tools/approved.py"}
    assert approved_paths.intersection(original_and_destination)
    assert not approved_paths.intersection(default_paths)


def test_offline_image_dependencies_are_copied_from_approved_snapshot_not_main(tmp_path):
    """Exercise the workflow's actual shell copy with divergent main/candidate deps.

    No Docker, private originals, credentials, or benchmark files are required.
    The networked image builder must receive only immutable approved dependency
    inputs, never the independently mutable trusted-main dependency files.
    """
    main = tmp_path / "main"
    approved = tmp_path / "approved"
    deps = tmp_path / "image-context"
    for directory in (main, approved, deps):
        directory.mkdir()
    for filename in ("requirements.txt", "requirements-ci-v1228.txt"):
        (main / filename).write_text("main-only==99\n", encoding="utf-8")
        (approved / filename).write_text("approved-only==1\n", encoding="utf-8")
    (main / "private-original.pdf").write_bytes(b"DO NOT COPY")
    (approved / "candidate-code.py").write_text("pass\n", encoding="utf-8")

    steps = _load()["jobs"]["original"]["steps"]
    build = next(step["run"] for step in steps if step["name"].startswith("Build offline"))
    copy_line, = (line.strip() for line in build.splitlines()
                  if line.strip().startswith("cp -- "))
    env = os.environ.copy()
    env.update(GPT3_APPROVED_TREE=str(approved), deps_dir=str(deps))
    subprocess.run(["bash", "-c", "set -euo pipefail\n" + copy_line],
                   cwd=main, env=env, check=True, capture_output=True, text=True)
    assert sorted(path.name for path in deps.iterdir()) == [
        "requirements-ci-v1228.txt", "requirements.txt",
    ]
    for filename in ("requirements.txt", "requirements-ci-v1228.txt"):
        assert (deps / filename).read_bytes() == (approved / filename).read_bytes()
        assert (deps / filename).read_bytes() != (main / filename).read_bytes()


@pytest.mark.parametrize(("event", "ref", "dispatcher", "rerunner", "repository", "permitted"), [
    ("workflow_dispatch", "refs/heads/main", "BryceCurran86", "BryceCurran86", "BryceCurran86/PlanReader-3D", True),
    ("workflow_dispatch", "refs/heads/main", "BryceCurran86", "foreign-writer", "BryceCurran86/PlanReader-3D", False),
    ("workflow_dispatch", "refs/heads/main", "foreign-writer", "BryceCurran86", "BryceCurran86/PlanReader-3D", False),
    ("workflow_dispatch", "refs/heads/main", "BryceCurran86", "BryceCurran86", "other/PlanReader-3D", False),
    ("workflow_dispatch", "refs/heads/feature", "BryceCurran86", "BryceCurran86", "BryceCurran86/PlanReader-3D", False),
    ("pull_request", "refs/heads/main", "BryceCurran86", "BryceCurran86", "BryceCurran86/PlanReader-3D", False),
])
def test_owner_only_replay_requires_original_and_rerun_actor(
    event, ref, dispatcher, rerunner, repository, permitted,
):
    # The exact literal workflow expression is separately enforced by
    # OWNER_REPOSITORY_GUARD. This exercises its five intended predicates
    # without evaluating arbitrary expressions or exposing private sources.
    assert _load()["jobs"]["original"]["if"] == OWNER_REPOSITORY_GUARD
    assert all((
        event == "workflow_dispatch",
        ref == "refs/heads/main",
        dispatcher == "BryceCurran86",
        repository == "BryceCurran86/PlanReader-3D",
        rerunner == "BryceCurran86",
    )) is permitted

def _private_phase_diagnostic_is_source_safe(raw: str) -> bool:
    """No unreviewed private source, exception or traceback may reach Actions."""
    try:
        doc = _parse(raw)
        steps = doc["jobs"]["original"]["steps"]
        assert len(steps) == 6
        assert _isolated_private_source_contract(raw)
        execute = steps[4]["run"]
        assert execute.count(
            "docker run --rm --network none --read-only --cap-drop ALL"
        ) == 1
        assert execute.count("dst=/workspace/documents/sources,readonly") == 1
        assert "python -c 'import hashlib,json,fitz;" not in execute
        assert "Original Docker source mount or pinned PyMuPDF preflight FAILED" not in execute
        assert "python -c '" in execute and "status = pytest.main([" in execute
        # The private source mount must execute precisely the approved test.
        # A textual prefix check also matches pytest.main([]), which would
        # discover and run unintended tests with the protected PDF mounted.
        inline = _trusted_phase_probe_code(raw)
        pytest_calls = [
            node for node in ast.walk(ast.parse(inline))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "pytest"
            and node.func.attr == "main"
        ]
        assert len(pytest_calls) == 1
        assert len(pytest_calls[0].args) == 1 and not pytest_calls[0].keywords
        assert ast.literal_eval(pytest_calls[0].args[0]) == [
            "-q", "-p", "no:cacheprovider", "--tb=short",
            "--disable-warnings",
            "tests/test_gpt3_lot16_original_nine_whole_retention.py",
        ]
        assert '"--tb=short"' in execute
        assert '"-p", "no:cacheprovider"' in execute
        assert "sys.settrace(trace_call)" in execute
        assert "sys.settrace(None)" in execute
        assert 'print("GPT3_TRUSTED_PHASE=" + phase[0], flush=True)' in execute
        for phase_label in (
            "INSTRUMENTATION_ERROR", "COLLECTION_OR_SETUP",
            "SOURCE_AUTH", "DEFAULT_EIGHT", "EXPLICIT_NINE",
            "VERIFY_DEFAULT_CUSTOMER", "VERIFY_EXPLICIT_CUSTOMER",
            "ARCHIVED_EIGHT_RETENTION", "PHYSICAL_UNIQUENESS",
            "SNAPSHOT_IDENTITY",
        ):
            assert "GPT3_TRUSTED_PHASE=" + phase_label in execute or (
                phase_label in execute and "stages[hits[0]] = safe_label" in execute
            )
        assert 'tests/test_gpt3_lot16_original_nine_whole_retention.py' in execute
        assert execute.count(' > "$output" 2>&1; then') == 1
        assert "Original default-eight producer/seal/customer FAILED" in execute
        assert "Original explicit-nine producer/seal/customer FAILED" in execute
        assert "Original default-eight sealed/customer receipt verification FAILED" in execute
        assert "Original explicit-nine sealed/customer receipt verification FAILED" in execute
        assert "Original signed-eight archive/customer retention FAILED" in execute
        assert "Original new physical opening identity FAILED" in execute
        assert "Original old/new source snapshot identity FAILED" in execute
        assert "Original container/test stopped before trusted phase reporting" in execute
        assert 'cat "$output"' not in execute
        assert 'tee "$output"' not in execute
        assert "actions/upload-artifact" not in raw
        assert "github.event.inputs" not in raw
        assert 'rm -f "$RUNNER_TEMP/gpt3-owner-original-positive.log"' in steps[-1]["run"]
        assert 'echo "$output"' not in execute
        assert '$(<' not in execute
        return True
    except (AssertionError, KeyError, TypeError, yaml.YAMLError):
        return False


def test_original_private_first_failure_classifier_is_source_safe():
    assert _private_phase_diagnostic_is_source_safe(WORKFLOW.read_text(encoding="utf-8"))


@pytest.mark.parametrize(("old", "bad"), [
    ("--tb=short", "--tb=no"),
    ("--network none", "--network host"),
    ("status = pytest.main([", "status = pytest.NOTmain(["),
    # A syntax-valid empty-selection mutation preserves all tracing code.
    # Only the AST argument gate may reject it, not a string-prefix check.
    ('status = pytest.main(["-q", "-p", "no:cacheprovider", "--tb=short",\\n'
     '                                    "--disable-warnings",\\n'
     '                                    "tests/test_gpt3_lot16_original_nine_whole_retention.py"])',
     'status = pytest.main([])'),
    ('--mount "type=bind,src=$GITHUB_WORKSPACE/documents/sources,dst=/workspace/documents/sources,readonly"', '--mount "type=bind,src=/tmp/incorrect-source,dst=/workspace/documents/sources,readonly"'),
    (' > "$output" 2>&1; then', " 2>&1; then"),
    ('grep -Fxq', 'cat "$output"; grep -Fxq'),
    ('echo "::error::Original default-eight producer/seal/customer FAILED',
     'echo "$(<$output)"; echo "::error::Original default-eight producer/seal/customer FAILED'),
    ('rm -f "$RUNNER_TEMP/gpt3-owner-original-positive.log"',
     'echo "$(<$RUNNER_TEMP/gpt3-owner-original-positive.log)"'),
])
def test_private_first_failure_diagnostics_reject_unsafe_mutations(old, bad):
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert old in raw
    assert _private_phase_diagnostic_is_source_safe(raw)
    assert not _private_phase_diagnostic_is_source_safe(raw.replace(old, bad, 1))

def test_offline_original_replay_runs_immutable_approved_test_not_main_checkout():
    """Public CI may check the pinned runner path, not read PR-absent files."""
    steps = _load()["jobs"]["original"]["steps"]
    guarded = steps[1]["run"]
    execute = steps[4]["run"]
    assert f"approved_head={APPROVED}" in guarded
    assert f"approved_base={BASE}" in guarded
    assert 'git archive "$approved_head" | tar -x -C "$target_tree"' in guarded
    assert 'test -f "$target_tree/tests/test_gpt3_lot16_original_nine_whole_retention.py"' in guarded
    assert 'test -f "$target_tree/tools/run_gpt3_lot16_original_sealed_score_input.py"' in guarded
    assert 'cp -- "$GPT3_APPROVED_TREE/requirements.txt" "$GPT3_APPROVED_TREE/requirements-ci-v1228.txt" "$deps_dir/"' in steps[2]["run"]
    assert '--mount "type=bind,src=$GPT3_APPROVED_TREE,dst=/workspace,readonly"' in execute
    assert '--mount "type=bind,src=$GITHUB_WORKSPACE/documents/sources,dst=/workspace/documents/sources,readonly"' in execute
    assert "python -c '" in execute and "status = pytest.main([" in execute
    assert "tests/test_gpt3_lot16_original_nine_whole_retention.py" in execute
    assert _isolated_private_source_contract(WORKFLOW.read_text(encoding="utf-8"))


def _trusted_phase_probe_code(raw: str) -> str:
    """Parse the static trusted source-neutral Python phase tracer."""
    execute = _parse(raw)["jobs"]["original"]["steps"][4]["run"]
    prefix = "python -c '\n"
    suffix = "' > \"$output\" 2>&1; then"
    assert execute.count(prefix) == 1
    assert execute.count(suffix) == 1
    probe = execute.split(prefix, 1)[1].split(suffix, 1)[0].strip("\n")
    assert "sys.settrace(trace_call)" in probe
    assert "sys.settrace(None)" in probe
    assert "status = pytest.main([" in probe
    assert 'print("GPT3_TRUSTED_PHASE=" + phase[0], flush=True)' in probe
    compile(probe, "<trusted source-neutral phase probe>", "exec")
    return probe


@pytest.mark.parametrize(("failure_point", "expected"), [
    ("collection", "COLLECTION_OR_SETUP"),
    ("source", "SOURCE_AUTH"),
    ("default", "DEFAULT_EIGHT"),
])
def test_trusted_phase_tracer_classifies_synthetic_first_failure(
    tmp_path, failure_point, expected,
):
    """Exercise the actual trusted inline tracer without any private original."""
    probe = _trusted_phase_probe_code(WORKFLOW.read_text(encoding="utf-8"))
    tests = tmp_path / "tests"
    tests.mkdir()
    auth = (
        'raise ValueError("synthetic authentication failure")'
        if failure_point == "source" else 'return "SYNTHETIC"'
    )
    synthetic = f'''
SOURCE = object()
MANIFEST = object()
old_dir = object()
new_dir = object()
def _verify_original_source(source, manifest):
    {auth}
def run_original_lot16_sealed_handoff(source, directory):
    raise RuntimeError("synthetic default-eight issuer failure")
def _verified_production(directory, sha):
    return ({{}}, {{}})
def test_owner_original_lot16_nine_seals_and_preserves_eight_whole_customer_bodies():
    original_sha = _verify_original_source(SOURCE, MANIFEST)
    old_receipt = run_original_lot16_sealed_handoff(SOURCE, old_dir)
    new_receipt = run_original_lot16_sealed_handoff(
        SOURCE, new_dir, recover_additional_opening_areas=True,
    )
    old_signed, old_customer = _verified_production(old_dir, original_sha)
    new_signed, new_customer = _verified_production(new_dir, original_sha)
    digest_lines = (ARCHIVE.parent / "SHA256SUMS").read_text(encoding="ascii").splitlines()
    additional_ids = set(new_signed) - set(baseline_signed)
    physical_sources = _object(new_dir / "source_production_openings.json")
'''
    if failure_point == "collection":
        synthetic = 'raise RuntimeError("synthetic collection failure")\n' + synthetic
    (tests / "test_gpt3_lot16_original_nine_whole_retention.py").write_text(
        synthetic, encoding="utf-8",
    )
    env = os.environ.copy()
    env.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=tmp_path, env=env, capture_output=True, text=True,
        timeout=30, check=False,
    )
    assert result.returncode != 0
    assert f"GPT3_TRUSTED_PHASE={expected}" in result.stdout
    assert result.stdout.count("GPT3_TRUSTED_PHASE=") == 1
