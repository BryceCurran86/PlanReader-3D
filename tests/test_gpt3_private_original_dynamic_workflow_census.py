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
# A credentialed job may also require the exact trusted repository. This is a
# stricter conjunction, not a general expression parser: arbitrary OR clauses,
# extra interpolations and modified owner/main/manual predicates fail closed.
REPOSITORY_OWNER_GUARD = (
    OWNER_GUARD.removesuffix(" }}")
    + " && github.repository == 'BryceCurran86/PlanReader-3D' }}"
)
TRUSTED_SHA = SECURITY["TRUSTED_SHA"]
TOKEN = "${{ secrets.ORIGINAL_SOURCES_TOKEN }}"

# GitHub Actions permits both dot and quoted bracket secret expressions.
# A fixed text search would miss a newly authored bracket-style credential
# consumer and permit it to bypass the owner/manual/main CI trust boundary.
TOKEN_PATTERNS = (
    # A source secret can appear inside format/fallback/function expressions;
    # never require it to be the first token or the only expression member.
    re.compile(r"\$\{\{[^}]*\bsecrets\s*\.\s*ORIGINAL_SOURCES_TOKEN\b[^}]*\}\}"),
    re.compile(r"""\$\{\{[^}]*\bsecrets\s*\[\s*['"]ORIGINAL_SOURCES_TOKEN['"]\s*\][^}]*\}\}"""),
)


def _contains_source_token(value: object) -> bool:
    text = str(value)
    return any(pattern.search(text) is not None for pattern in TOKEN_PATTERNS)



def _token_jobs(raw: str):
    document = yaml.load(raw, Loader=Loader)
    assert type(document) is dict
    triggers = document.get("on")
    jobs = document.get("jobs")
    assert type(triggers) is dict and type(jobs) is dict
    matching = [
        (name, job)
        for name, job in jobs.items()
        if type(job) is dict and _contains_source_token(job)
    ]
    return document, matching


def _trusted_original_job_guard(value: object) -> bool:
    return type(value) is str and value in (OWNER_GUARD, REPOSITORY_OWNER_GUARD)


def check_original_token_boundary(raw: str) -> int:
    document, matches = _token_jobs(raw)
    assert matches, "a supposedly credentialed workflow does not consume the source token"
    assert "workflow_dispatch" in document["on"]
    assert "pull_request_target" not in document["on"]
    for name, job in matches:
        assert _trusted_original_job_guard(job.get("if")), name
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
        provision = [s for s in steps if _contains_source_token(s)]
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
        if _contains_source_token(raw):
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


@pytest.mark.parametrize("secret_reference", (
    "${{ secrets['ORIGINAL_SOURCES_TOKEN'] }}",
    '${{ secrets["ORIGINAL_SOURCES_TOKEN"] }}',
    "${{ secrets . ORIGINAL_SOURCES_TOKEN }}",
    "${{ secrets[ 'ORIGINAL_SOURCES_TOKEN' ] }}",
    "${{ secrets.ORIGINAL_SOURCES_TOKEN || '' }}",
    "${{ toJSON(secrets.ORIGINAL_SOURCES_TOKEN) }}",
    "${{ secrets['ORIGINAL_SOURCES_TOKEN'] || '' }}",
))
def test_alternative_token_expression_cannot_escape_dynamic_security_census(secret_reference):
    raw = _new_workflow().replace(TOKEN, secret_reference)
    assert _contains_source_token(raw)
    assert check_original_token_boundary(raw) == 1
    unsafe = raw.replace(OWNER_GUARD, "${{ github.event_name == 'pull_request' }}")
    with pytest.raises(AssertionError):
        check_original_token_boundary(unsafe)


def test_exact_trusted_repository_conjunction_is_accepted_without_weakening_owner_guard():
    # GPT1 #3758 has the same owner/main/manual guard plus an exact repository
    # restriction. Its private original job must not need a weaker condition
    # merely to pass GPT3's dynamic workflow census.
    raw = _new_workflow().replace(OWNER_GUARD, REPOSITORY_OWNER_GUARD)
    assert check_original_token_boundary(raw) == 1


@pytest.mark.parametrize(("old", "new"), (
    ("github.repository == 'BryceCurran86/PlanReader-3D'", "github.repository == 'other/repo'"),
    ("github.repository == 'BryceCurran86/PlanReader-3D'", "github.repository != 'other/repo'"),
    (" && github.repository ==", " || github.repository =="),
    ("github.event_name == 'workflow_dispatch'", "github.event_name == 'pull_request'"),
    ("github.ref == 'refs/heads/main'", "github.ref == 'refs/heads/dev'"),
    ("github.actor == 'BryceCurran86'", "github.actor != 'BryceCurran86'"),
    ("github.actor == 'BryceCurran86'", "github.actor == 'attacker'"),
    (" && github.repository ==", " && true && github.repository =="),
    (" && github.repository ==", " && !github.repository =="),
    (" }}", " || true }}"),
))
def test_trusted_repository_guard_rejects_unsafe_or_unrecognized_mutations(old, new):
    raw = _new_workflow().replace(OWNER_GUARD, REPOSITORY_OWNER_GUARD)
    assert old in raw
    with pytest.raises(AssertionError):
        check_original_token_boundary(raw.replace(old, new, 1))
