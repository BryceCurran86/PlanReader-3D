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
                     "git checkout --detach", "git rev-parse HEAD", "git status --porcelain"):
        assert required in script
    assert "tests/test_gpt3_lot16_original_nine_whole_retention.py" in script
    # Source is received only after unchanged code and dependencies are checked.
    source_index = next(i for i, x in enumerate(steps) if "ORIGINAL_SOURCES_TOKEN" in str(x))
    guard_index = steps.index(guards[0])
    assert guard_index < source_index
    secret = steps[source_index]
    assert secret["uses"] == "./.github/actions/provision-original-sources"
    assert secret["with"]["token"] == "${{ secrets.ORIGINAL_SOURCES_TOKEN }}"
    assert secret["with"]["allow-missing"] == "false"
    assert secret["with"]["names"].strip() == "1. Construction Plans - Lot 16 Power (REV E).pdf"
    assert sum("ORIGINAL_SOURCES_TOKEN" in str(x) for x in steps) == 1
    test_step = next(x for x in steps if x.get("name", "").startswith("Require two original"))
    assert steps.index(test_step) > source_index
    for required in ("tests/test_gpt3_lot16_original_nine_whole_retention.py",
                     '1 passed', 'skipped', "source-to-customer retention test FAILED"):
        assert required in test_step["run"]
    assert steps[-1]["if"] == "always()"
    assert "rm -rf documents/sources" in steps[-1]["run"]
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
