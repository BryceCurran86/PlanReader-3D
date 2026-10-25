"""Census ALL GitHub Actions that consume private construction originals.

Unlike fixed workflow allowlists, a newly added token-bearing YAML is
automatically subject to owner/main-only conditions. Source-neutral tests
never provision private PDFs, run a producer, or touch the frozen benchmark.
"""
from pathlib import Path
from runpy import run_path
import re

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
SECURITY = run_path(str(ROOT / "tests" / "test_gpt3_private_original_workflow_manual_trust.py"))
Loader = SECURITY["UniqueMappingLoader"]
OWNER_GUARD = SECURITY["OWNER_GUARD"]
TRUSTED_SHA = SECURITY["TRUSTED_SHA"]
TOKEN = "${{ secrets.ORIGINAL_SOURCES_TOKEN }}"


def _token_jobs(raw: str):
    document = yaml.load(raw, Loader=Loader)
    assert type(document) is dict
    triggers = document.get("on")
    jobs = document.get("jobs")
    assert type(triggers) is dict and type(jobs) is dict
    matching = [
        (name, job)
        for name, job in jobs.items()
        if type(job) is dict and TOKEN in str(job)
    ]
    return document, matching


def check_original_token_boundary(raw: str) -> int:
    document, matches = _token_jobs(raw)
    assert matches, "a supposedly credentialed workflow does not consume the source token"
    assert "workflow_dispatch" in document["on"]
    assert "pull_request_target" not in document["on"]
    for name, job in matches:
        assert job.get("if") == OWNER_GUARD, name
        steps = job.get("steps")
        assert type(steps) is list and steps
        checkouts = [
            s for s in steps
            if type(s) is dict and str(s.get("uses", "")).startswith("actions/checkout@")
        ]
        assert len(checkouts) == 1, name
        checkout = checkouts[0]
        args = checkout.get("with", {})
        assert type(args) is dict
        # On owner-dispatched main, default checkout resolves triggering main
        # sha. An explicit ref must be that same SHA, never a PR/head variable.
        assert args.get("ref") in (None, TRUSTED_SHA)
        assert args.get("persist-credentials") == "false"
        provision = [s for s in steps if TOKEN in str(s)]
        assert len(provision) == 1
        assert steps.index(checkout) < steps.index(provision[0])
        assert "github.event.pull_request.head.sha" not in str(job)
        assert "actions/upload-artifact@" not in str(job)
        assert any(
            s.get("if") == "always()"
            and re.search(r"(?m)^\s*rm\s+-rf\s+[^\n]*\bdocuments/sources(?:\s|$)", str(s.get("run", "")))
            for s in steps if type(s) is dict
        ), name
    return len(matches)


def _discovered():
    sources = []
    for path in sorted(WORKFLOWS.glob("*")):
        if path.suffix not in (".yml", ".yaml"):
            continue
        raw = path.read_text(encoding="utf-8")
        # Look for an actual GitHub secret reference, not a comment or
        # a variable named ORIGINAL_SOURCES_TOKEN in a harmless test step.
        if TOKEN in raw:
            sources.append((path.name, raw))
    return sources


def test_every_token_workflow_is_guarded_even_if_added_tomorrow():
    discovered = _discovered()
    checked = set()
    for name, raw in discovered:
        assert name not in checked
        checked.add(name)
        assert check_original_token_boundary(raw) >= 1
    required = set(SECURITY["WORKFLOWS"]) | {
        "provision-original-sources-smoke.yml",
        "gpt2-trusted-original-source-replay-manual.yml",
        "gptmax-trusted-original-opening-replay-manual.yml",
        "gpt3-trusted-original-nine-replay-manual.yml",
        "test-gpt3-max-area-review-source-issuer.yml",
    }
    assert required <= checked, sorted(required - checked)


def _new_workflow():
    return (
        "name: Unregistered owner-original job\n"
        "on:\n  pull_request:\n    branches: [main]\n"
        "  workflow_dispatch:\njobs:\n"
        "  source:\n"
        "    if: " + OWNER_GUARD + "\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "        with:\n"
        "          ref: " + TRUSTED_SHA + "\n"
        "          persist-credentials: false\n"
        "      - uses: ./.github/actions/provision-original-sources\n"
        "        with:\n"
        "          token: " + TOKEN + "\n"
        "      - name: Cleanup\n"
        "        if: always()\n"
        "        run: rm -rf documents/sources artifacts\n"
    )


@pytest.mark.parametrize("unsafe", (
    "pr_only", "remove_actor", "wrong_branch", "untrusted_head",
    "persist_credentials", "upload", "no_cleanup", "duplicate_on",
))
def test_newly_added_unsafe_source_job_is_rejected_without_static_allowlist(unsafe):
    raw = _new_workflow()
    mutations = {
        "pr_only": ("workflow_dispatch", "pull_request"),
        "remove_actor": (OWNER_GUARD, "${{ github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' }}"),
        "wrong_branch": (OWNER_GUARD, OWNER_GUARD.replace("refs/heads/main", "refs/heads/dev")),
        "untrusted_head": (TRUSTED_SHA, "${{ github.event.pull_request.head.sha }}"),
        "persist_credentials": ("persist-credentials: false", "persist-credentials: true"),
        "upload": ("      - name: Cleanup", "      - uses: actions/upload-artifact@v4\n      - name: Cleanup"),
        "no_cleanup": ("rm -rf documents/sources artifacts", "echo no-cleanup"),
        "duplicate_on": ("on:\n", "on:\n  pull_request: {}\n"),
    }
    before, after = mutations[unsafe]
    assert before in raw
    with pytest.raises((AssertionError, yaml.YAMLError)):
        check_original_token_boundary(raw.replace(before, after, 1))


def test_safe_new_credentialed_workflow_is_discovered_without_filename():
    assert check_original_token_boundary(_new_workflow()) == 1
