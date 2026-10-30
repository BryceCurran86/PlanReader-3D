"""Static fail-closed original-PDF GitHub Actions trust boundary tests."""
import re
from pathlib import Path
import pytest
import yaml

F = Path(__file__).resolve().parents[1] / ".github" / "workflows"
JOBS = {
    "test-gpt3-maryborough-original-floor-score-input.yml":"original-source",
    "test-gpt3-lot16-original-sealed-score-input.yml":"original-lot16-real-seal",
    "test-gpt3-1215-paired-customer-retention.yml":"original-paired-source-customer",
    "gpt3-original-opening-customer-inventory.yml":"original-source",
    "diag-gpt3-maryborough-ft3-source-firstgate.yml":"original-source",
    "test-gpt3-original-scope-v1-consumer.yml":"original-lot16",
    "score-gpt3-lot16-1215-opening-local.yml":"original-source-score",
}
GUARD = "${{ github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' && github.actor == 'BryceCurran86' }}"
RERUN_GUARD = GUARD.removesuffix(" }}") + " && github.triggering_actor == 'BryceCurran86' }}"

class Loader(yaml.SafeLoader):
    pass

Loader.yaml_implicit_resolvers = {
    key: [(tag, rx) for tag, rx in values if tag != "tag:yaml.org,2002:bool"]
    for key, values in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
Loader.add_implicit_resolver("tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF"))

def unique(loader, node, deep=False):
    seen = set()
    for keynode, _ in node.value:
        key = loader.construct_object(keynode, deep=True)
        if type(key) is not str or key in seen:
            raise yaml.constructor.ConstructorError(None, None,
                "duplicate or invalid YAML key", keynode.start_mark)
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)

Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique)

def read(name):
    raw = (F/name).read_text(encoding="utf-8")
    data = yaml.load(raw, Loader=Loader)
    assert type(data) is dict
    assert set(data["on"]) == {"pull_request", "workflow_dispatch"}
    return data, raw

def safe(job):
    checkouts = [s for s in job.get("steps", []) if s.get("uses", "").startswith("actions/checkout@")]
    if len(checkouts) != 1:
        return False
    opts = checkouts[0].get("with", {})
    return (job.get("if") in (GUARD, RERUN_GUARD) and opts.get("ref") == "${{ github.sha }}"
            and opts.get("persist-credentials") is False
            and "github.event.pull_request.head.sha" not in str(job)
            and "secrets.ORIGINAL_SOURCES_TOKEN" in str(job))

@pytest.mark.parametrize("name, ownerjob", JOBS.items())
def test_original_secret_never_runs_pr_head(name, ownerjob):
    data, raw = read(name)
    assert "\n  pull_request:" in raw and "\n  workflow_dispatch:" in raw
    assert "pull_request_target:" not in raw
    assert safe(data["jobs"][ownerjob])
    assert sum("secrets.ORIGINAL_SOURCES_TOKEN" in str(j) for j in data["jobs"].values()) == 1
    assert all("secrets.ORIGINAL_SOURCES_TOKEN" not in str(j)
        for k,j in data["jobs"].items() if k != ownerjob)

@pytest.mark.parametrize("name, ownerjob", JOBS.items())
def test_unsafe_event_and_checkout_mutations_rejected(name, ownerjob):
    data, _ = read(name)
    job = data["jobs"][ownerjob]
    assert safe(job)
    for weak in ("${{ github.event_name == 'pull_request' }}",
                 "${{ github.ref == 'refs/heads/main' }}",
                 "${{ github.actor == 'BryceCurran86' }}",
                 "${{ github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' }}"):
        assert not safe(dict(job, **{"if": weak}))
    steps = [dict(x) for x in job["steps"]]
    for x in steps:
        if x.get("uses", "").startswith("actions/checkout@"):
            x["with"] = dict(x["with"], ref="${{ github.event.pull_request.head.sha || github.sha }}")
    assert not safe(dict(job, steps=steps))

@pytest.mark.parametrize("name", JOBS)
def test_duplicate_trigger_key_rejected(name):
    _, raw = read(name)
    with pytest.raises((yaml.YAMLError, AssertionError)):
        yaml.load(raw.replace("\non:\n", "\non:\n  push:\non:\n", 1), Loader=Loader)


@pytest.mark.parametrize("name", [
    "test-gpt3-maryborough-original-floor-score-input.yml",
    "test-gpt3-lot16-original-sealed-score-input.yml",
])
def test_stricter_rerun_owner_guard_rejects_foreign_writer_or_bypass(name):
    data, _ = read(name)
    job = data["jobs"][JOBS[name]]
    assert job["if"] == RERUN_GUARD
    assert safe(job)
    for bad in (
        RERUN_GUARD.replace("github.triggering_actor == 'BryceCurran86'",
                            "github.triggering_actor == 'foreign-writer'"),
        RERUN_GUARD.replace(" && github.triggering_actor ==",
                            " || github.triggering_actor =="),
        RERUN_GUARD.replace("github.actor == 'BryceCurran86'",
                            "github.actor == 'foreign-writer'"),
        RERUN_GUARD.replace(" }}", " || true }}"),
    ):
        assert not safe(dict(job, **{"if": bad}))
