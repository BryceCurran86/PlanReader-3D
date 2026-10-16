"""Keep the signed fixture guard testing merged PR code, never an old PR head.

An older pull-request branch may legitimately predate the immutable V1
fixture. GitHub Actions' normal pull_request checkout uses the synthetic
merge commit, where the proposed changes and current main coexist.
"""
from __future__ import annotations

from pathlib import Path
import re

import pytest

WORKFLOW_PATH = (
    Path(__file__).resolve().parents[1]
    / ".github/workflows/test-gpt3-sealed-fixture-guard-shadow.yml"
)


def _checks_integration_tree(source: str) -> bool:
    """Validate checkout wiring using plain text, without new YAML dependencies."""
    if "  pull_request:\n    branches: [main," not in source:
        return False
    if "  push:\n    branches: [main," not in source:
        return False
    matches = list(re.finditer(r"(?m)^      - uses: actions/checkout@v4\s*$", source))
    if len(matches) != 1:
        return False
    checkout_end = matches[0].end()
    next_step = re.search(r"(?m)^      - (?:uses|name|run):", source[checkout_end:])
    checkout_body = (
        source[checkout_end:checkout_end + next_step.start()]
        if next_step is not None else source[checkout_end:]
    )
    # Using github.sha (the PR merge commit for a PR event) is the default.
    # An explicit head SHA, fixed main ref, or other checkout override is unsafe.
    if re.search(r"(?m)^\s+ref\s*:", checkout_body):
        return False
    return "github.event.pull_request.head.sha" not in source


def test_original_immutable_fixture_guard_targets_current_pr_merge_tree():
    source = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert _checks_integration_tree(source)


@pytest.mark.parametrize(
    "change",
    (
        "stale_head_override",
        "explicit_main_override",
        "head_only_override",
        "remove_main_pull_request",
        "remove_main_push",
        "delete_checkout",
        "duplicate_checkout",
    ),
)
def test_dangerous_github_actions_checkout_mutation_is_refused(change: str):
    source = WORKFLOW_PATH.read_text(encoding="utf-8")
    checkout = "      - uses: actions/checkout@v4"
    if change == "stale_head_override":
        source = source.replace(
            checkout,
            checkout
            + "\n        with:\n"
            + "          ref: ${{ github.event.pull_request.head.sha || github.sha }}",
            1,
        )
    elif change == "head_only_override":
        source = source.replace(
            checkout,
            checkout
            + "\n        with:\n"
            + "          ref: ${{ github.event.pull_request.head.sha }}",
            1,
        )
    elif change == "explicit_main_override":
        source = source.replace(
            checkout,
            checkout + "\n        with:\n          ref: refs/heads/main",
            1,
        )
    elif change == "remove_main_pull_request":
        source = source.replace(
            "  pull_request:\n    branches: [main,",
            "  pull_request:\n    branches: [gpt3/",
            1,
        )
    elif change == "remove_main_push":
        source = source.replace(
            "  push:\n    branches: [main,",
            "  push:\n    branches: [gpt3/",
            1,
        )
    elif change == "delete_checkout":
        source = source.replace(checkout, "      # missing checkout", 1)
    elif change == "duplicate_checkout":
        source = source.replace(checkout, checkout + "\n" + checkout, 1)
    else:
        raise AssertionError(change)
    assert not _checks_integration_tree(source)
