"""Fail-closed static security contract for owner-only source-positive GPT3 replay.

No benchmark, original PDF, secrets or producer authority is used by this test.
"""
from pathlib import Path
import re

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/gpt3-trusted-original-nine-replay-manual.yml"
APPROVED = "31439c9e4137d7f210488877cc0ab868ed7ffecb"
BASE = "c491c5fb2a155a54825d639ef277218707b76327"


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
    for fragment in ("github.event_name == 'workflow_dispatch'", "github.ref == 'refs/heads/main'",
                     "github.actor == 'BryceCurran86'"):
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
                     'git diff --name-only "$approved_base" "$GITHUB_SHA"',
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
    assert 'docker build -q' in steps[build_index]["run"]
    assert 'docker run' not in steps[build_index]["run"]
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
                     "-p no:cacheprovider", "private details withheld"):
        assert required in test_step["run"]
    assert 'grep -E \'^(FAILED |ERROR )\'' not in test_step["run"]
    assert 'cat "$output"' not in test_step["run"]
    assert 'python -m pip install' not in test_step["run"]
    assert steps[-1]["if"] == "always()"
    assert 'rm -rf "$RUNNER_TEMP/gpt3-approved-candidate" documents/sources' in steps[-1]["run"]
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
        assert job["if"] == (
            "${{ github.event_name == 'workflow_dispatch' && "
            "github.ref == 'refs/heads/main' && github.actor == 'BryceCurran86' }}"
        )
        checkout, guard, build, provision, execute, cleanup = steps
        assert checkout["uses"] == "actions/checkout@v4"
        assert checkout["with"]["persist-credentials"] is False
        assert 'git archive "$approved_head"' in guard["run"]
        assert 'git diff --name-only "$approved_base" "$GITHUB_SHA"' in guard["run"]
        assert "comm -12" in guard["run"]
        assert 'if [[ -n "$conflicting" ]]' in guard["run"]
        assert "Trusted main modified an immutable GPT3 release path" in guard["run"]
        assert "git checkout --detach" not in raw
        assert '[[ "$(git rev-parse HEAD)" == "$GITHUB_SHA" ]]' in guard["run"]
        assert 'docker build -q' in build["run"]
        assert "ORIGINAL_SOURCES_TOKEN" not in str(build)
        assert provision["uses"] == "./.github/actions/provision-original-sources"
        assert provision["with"]["token"] == "${{ secrets.ORIGINAL_SOURCES_TOKEN }}"
        script = execute["run"]
        assert "docker run --rm --network none --read-only --cap-drop ALL" in script
        assert '--mount "type=bind,src=$GPT3_APPROVED_TREE,dst=/workspace,readonly"' in script
        assert '--mount "type=bind,src=$GITHUB_WORKSPACE/documents/sources,dst=/workspace/documents/sources,readonly"' in script
        assert "python -m pytest" in script
        assert "grep -Eq" in script and "skipped" in script
        assert "private details withheld" in script
        assert cleanup["if"] == "always()"
        assert 'rm -rf "$RUNNER_TEMP/gpt3-approved-candidate" documents/sources' in cleanup["run"]
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
    ('persist-credentials: false', 'persist-credentials: true'),
    ('comm -12', 'comm -23'),
    ('if [[ -n "$conflicting" ]]', 'if [[ -z "$conflicting" ]]'),
    ('rm -rf "$RUNNER_TEMP/gpt3-approved-candidate" documents/sources',
     'rm -rf "$RUNNER_TEMP/gpt3-approved-candidate"'),
])
def test_trust_boundary_mutations_cannot_certify_owner_source(old, new):
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert old in raw
    assert _isolated_private_source_contract(raw)
    assert not _isolated_private_source_contract(raw.replace(old, new, 1))
