"""Safety contract for owner-initiated, SHA-pinned private source replays."""
from pathlib import Path
import re
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / ".github/workflows/gpt2-trusted-original-source-replay-manual.yml"
SOURCE = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
HEADS = {
    "a600": "91cc96a445d6441a640547ce089cd756b56873b3",
    "freezer": "f424c6c16fca7c83d4b7a8425faaa1172afd5045",
    "d15": "37ed51dd024db1979bf4a114c656c6985519aa8b",
    "rcp": "bf26820aa89d0c911448dd67d1f4bb2ef226eaf0",
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
    assert '[[ "$(git rev-parse HEAD)" == "$GITHUB_SHA" ]]' in script
    assert '[[ -f "$target_tree/$test_path" ]]' in script
    assert 'GPT2_APPROVED_TREE=$target_tree' in script
    assert "expected_paths=" in script
    assert "github.event.inputs" not in FILE.read_text(encoding="utf8")


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
    assert len(steps[provision + 1:-1]) == 1
    guard = next(s for s in steps if s.get("name", "").startswith("Validate immutable"))
    assert steps.index(guard) < build
    assert 'git checkout --detach' not in guard["run"]
    assert 'git archive "$approved_head"' in guard["run"]
    assert steps[provision]["uses"] == "./.github/actions/provision-original-sources"
    script = steps[isolated]["run"]
    for required in ("docker run --rm --network none --read-only --cap-drop ALL",
                     "--security-opt no-new-privileges", "dst=/workspace,readonly",
                     "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1", "run_test source-positive",
                     "run_test full-module", "grep -Eq", "details withheld to protect source"):
        assert required in script
    assert '--mount "type=bind,src=$GPT2_APPROVED_TREE,dst=/workspace,readonly"' in script
    assert '--mount "type=bind,src=$GITHUB_WORKSPACE/documents/sources,dst=/workspace/documents/sources,readonly"' in script
    assert '--mount "type=bind,src=$PWD,dst=/workspace,readonly"' not in script
    assert "grep -E '^FAILED" not in script
    assert "cat \"$output\"" not in script
    assert "docker build" not in script
    assert SOURCE == steps[isolated]["env"]["PLANREADER_MARYBOROUGH_SOURCE_SHA256"]
    assert steps[-1]["if"] == "always()"
    assert 'rm -rf "$RUNNER_TEMP/gpt2-approved-target" documents/sources' in steps[-1]["run"]
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
