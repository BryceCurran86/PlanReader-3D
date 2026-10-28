"""Fail closed on private-source token use in PR-head GPT3 workflow jobs.

The PR-focused synthetic checks still run; only source-token jobs are manual,
owner/main-only, and must not upload private original-derived artifacts.
"""
from pathlib import Path
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1] / ".github" / "workflows"
WORKFLOWS = ["test-gpt3-maryborough-original-floor-score-input.yml","test-gpt3-lot16-original-sealed-score-input.yml","test-gpt3-1215-paired-customer-retention.yml","gpt3-original-opening-customer-inventory.yml","diag-gpt3-maryborough-ft3-source-firstgate.yml","test-gpt3-original-scope-v1-consumer.yml","score-gpt3-lot16-1215-opening-local.yml","diag-gpt3-lot16-1215-identity-readiness.yml","diag-gpt3-lot16-internal-870-identity-readiness.yml","test-gpt3-source-frame-proof.yml","test-gpt3-raster-source-discovery.yml","test-gpt3-native-dimension-original-source-cache.yml","test-gpt3-1215-opening-local-retention.yml","test-gpt3-1215-room-face-owned-retention.yml","score-gpt3-selected-two-original-projects.yml"]
OWNER_GUARD = "${{ github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' && github.actor == 'BryceCurran86' }}"
RERUN_OWNER_GUARD = (
    OWNER_GUARD.removesuffix(" }}")
    + " && github.triggering_actor == 'BryceCurran86' }}"
)
TRUSTED_SHA = "${{ github.sha }}"


class UniqueMappingLoader(yaml.BaseLoader):
    pass


def unique_mapping(loader, node):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                None, None, "duplicate workflow key", key_node.start_mark
            )
        mapping[key] = loader.construct_object(value_node, deep=True)
    return mapping


UniqueMappingLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping
)


def validate_source_job(raw):
    doc = yaml.load(raw, Loader=UniqueMappingLoader)
    assert "pull_request" in doc["on"] and "workflow_dispatch" in doc["on"]
    token_jobs = [
        (name, job) for name, job in doc["jobs"].items()
        if "ORIGINAL_SOURCES_TOKEN" in str(job)
    ]
    assert 1 <= len(token_jobs) <= 2
    for name, job in token_jobs:
        assert job.get("if") in (OWNER_GUARD, RERUN_OWNER_GUARD), name
        steps = job["steps"]
        checkouts = [s for s in steps if s.get("uses", "").startswith("actions/checkout@")]
        assert len(checkouts) == 1
        checkout = checkouts[0]
        assert checkout["with"]["ref"] == TRUSTED_SHA
        assert checkout["with"]["persist-credentials"] == "false"
        provision = [s for s in steps if "ORIGINAL_SOURCES_TOKEN" in str(s)]
        assert len(provision) == 1
        assert provision[0]["with"]["token"] == "${{ secrets.ORIGINAL_SOURCES_TOKEN }}"
        assert steps.index(checkout) < steps.index(provision[0])
        assert "github.event.pull_request.head.sha" not in str(job)
        assert not any("actions/upload-artifact@" in str(s.get("uses", "")) for s in steps)
        assert steps[-1]["if"] == "always()"
        assert "rm -rf documents/sources artifacts" in steps[-1]["run"]
    for other_name, other in doc["jobs"].items():
        if other_name not in {name for name, _ in token_jobs}:
            assert "ORIGINAL_SOURCES_TOKEN" not in str(other)
    return doc

@pytest.mark.parametrize("filename", WORKFLOWS)
def test_private_original_is_never_run_on_pull_request_head(filename):
    validate_source_job((ROOT / filename).read_text(encoding="utf-8"))


@pytest.mark.parametrize("filename", WORKFLOWS)
def test_mutated_unsafe_guard_fails(filename):
    raw = (ROOT / filename).read_text(encoding="utf-8")
    guard = RERUN_OWNER_GUARD if RERUN_OWNER_GUARD in raw else OWNER_GUARD
    assert guard in raw
    with pytest.raises(AssertionError):
        validate_source_job(raw.replace(
            guard,
            guard.replace("workflow_dispatch", "pull_request"),
            1,
        ))


@pytest.mark.parametrize("filename", WORKFLOWS)
def test_untrusted_checkout_or_artifact_fails(filename):
    raw = (ROOT / filename).read_text(encoding="utf-8")
    assert "ref: " + TRUSTED_SHA in raw
    with pytest.raises(AssertionError):
        validate_source_job(raw.replace(
            "ref: " + TRUSTED_SHA,
            "ref: ${{ github.event.pull_request.head.sha }}",
            1,
        ))
    assert "      - name: Destroy private originals" in raw
    with pytest.raises(AssertionError):
        validate_source_job(raw.replace(
            "      - name: Destroy private originals",
            "      - uses: actions/upload-artifact@v4\n      - name: Destroy private originals",
            1,
        ))


@pytest.mark.parametrize("filename", WORKFLOWS)
def test_duplicate_event_key_fails_closed(filename):
    raw = (ROOT / filename).read_text(encoding="utf-8")
    assert "on:\n" in raw
    with pytest.raises(yaml.YAMLError):
        validate_source_job(raw.replace("on:\n", "on:\n  pull_request: {}\n", 1))


def test_owner_original_provision_smoke_is_not_an_untrusted_dispatch():
    raw = (ROOT / "provision-original-sources-smoke.yml").read_text(encoding="utf-8")
    doc = yaml.load(raw, Loader=UniqueMappingLoader)
    assert set(doc["on"]) == {"workflow_dispatch"}
    job = doc["jobs"]["provision"]
    assert job["if"] == OWNER_GUARD
    steps = job["steps"]
    checkout = next(x for x in steps if x.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"] == {"ref": TRUSTED_SHA, "persist-credentials": "false"}
    provision = next(x for x in steps if "ORIGINAL_SOURCES_TOKEN" in str(x))
    assert steps.index(checkout) < steps.index(provision)
    assert steps[-1]["if"] == "always()"
    assert "rm -rf documents/sources" in steps[-1]["run"]
    assert "upload-artifact" not in str(job)
    assert "pull_request.head.sha" not in str(job)


@pytest.mark.parametrize("filename", [
    "test-gpt3-maryborough-original-floor-score-input.yml",
    "test-gpt3-lot16-original-sealed-score-input.yml",
])
def test_stricter_owner_rerun_guard_rejects_foreign_or_injected_context(filename):
    raw = (ROOT / filename).read_text(encoding="utf-8")
    assert RERUN_OWNER_GUARD in raw
    assert validate_source_job(raw)
    for bad in (
        RERUN_OWNER_GUARD.replace("github.triggering_actor == 'BryceCurran86'",
                                  "github.triggering_actor == 'foreign-writer'"),
        RERUN_OWNER_GUARD.replace(" && github.triggering_actor ==",
                                  " || github.triggering_actor =="),
        RERUN_OWNER_GUARD.replace(" }}", " || true }}"),
        RERUN_OWNER_GUARD.replace("github.actor == 'BryceCurran86'",
                                  "github.actor == 'foreign-writer'"),
    ):
        with pytest.raises(AssertionError):
            validate_source_job(raw.replace(RERUN_OWNER_GUARD, bad, 1))
