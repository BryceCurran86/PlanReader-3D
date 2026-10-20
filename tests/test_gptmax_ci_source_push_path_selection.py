"""The six original-source diagnostics must not run for unrelated CANDIDATE modules.

This checks the checked-in GitHub Actions trigger selection (not the private
Maryborough drawing). Required global CI, source SHAs, original replay steps and
the signed eight are deliberately outside this test's modifications.
"""
from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
DIRECT = {
    "test-gpt2-native-compound-sheet-label.yml": (
        "pb_page_title_authority.py",
        "tests/test_gpt2_native_compound_sheet_labels.py",
    ),
    "test-gpt2-original-native-dimension-strokes.yml": (
        "pb_source_native_dimension_stroke_shadow.py",
        "tests/test_gpt2_source_native_dimension_stroke_shadow.py",
    ),
    "test-gpt2-original-ft2-ft3-source-rows.yml": (
        "tools/diag_original_native_finish_schedule_row_source_shadow.py",
        "tests/test_gpt2_original_ft2_ft3_sameblock_schedule_source.py",
    ),
    "test-gpt2-rcp-source-viewport-coverage.yml": (
        "tools/diag_source_viewport_coverage_shadow.py",
        "tests/test_gpt2_source_viewport_coverage_shadow.py",
    ),
    "diag-gpt2-original-mixed-amenities-insets.yml": (
        "tools/diag_gpt2_original_mixed_amenities_insets.py",
        "tests/test_gpt2_original_mixed_amenities_insets.py",
        "pb_page_title_authority.py",
        "pb_viewport_segmentation.py",
    ),
    "test-gpt2-a600-original-column-header.yml": (
        "pb_source_door_schedule_authority.py",
        "pb_source_visibility_authority.py",
        "tests/test_gpt2_a600_native_column_header_source_roles.py",
    ),
}


def _source(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def _event_block(name: str, event: str) -> str:
    # Parse just the stable two-space GitHub event-key indentation; this
    # avoids PyYAML 1.1's surprising conversion of YAML 'on' into bool True.
    text = _source(name).split("\njobs:\n", 1)[0]
    marker = f"  {event}:\n"
    assert text.count(marker) == 1, (name, event)
    following = text.split(marker, 1)[1]
    next_event = re.search(r"(?m)^  [a-z][a-z_]*:\s*$", following)
    return following[:next_event.start()] if next_event else following


def _paths(block: str) -> tuple[str, ...]:
    assert re.search(r"(?m)^    paths:\s*$", block), block
    return tuple(
        match.strip().strip("'\"")
        for match in re.findall(r"(?m)^      -\s+([^\n#]+)", block)
    )


@pytest.mark.parametrize("workflow,explicit", list(DIRECT.items()))
def test_related_source_and_own_workflow_keep_push_and_pull_request_triggers(
    workflow: str, explicit: tuple[str, ...]
) -> None:
    source = _source(workflow)
    assert re.search(r"(?m)^  workflow_dispatch:\s*$", source)
    push = _event_block(workflow, "push")
    assert re.search(r"(?m)^    branches:\s*\[main\]\s*$", push)
    push_paths = _paths(push)
    pr_paths = _paths(_event_block(workflow, "pull_request"))
    for path in (*explicit, f".github/workflows/{workflow}"):
        assert path in push_paths, (workflow, path)
        assert path in pr_paths, (workflow, path)


@pytest.mark.parametrize("workflow", sorted(DIRECT))
def test_unrelated_source_trade_never_starts_a_specialist_main_push(workflow: str) -> None:
    patterns = _paths(_event_block(workflow, "push"))
    assert "pb_*.py" not in patterns
    assert not any(
        fnmatchcase("pb_source_unrelated_trade_shadow.py", pattern)
        for pattern in patterns
    ), (workflow, patterns)
    assert not any(
        fnmatchcase("pb_source_unrelated_trade_shadow.py", pattern)
        for pattern in _paths(_event_block(workflow, "pull_request"))
    ), workflow


def test_global_required_ci_remains_full_and_unfiltered() -> None:
    # Explicitly keep this test coupled to the invariant from AGENTS.md:
    # the 6 specialist workflows are narrowed, but mandatory CI is NOT.
    ci = _source("ci.yml")
    for event in ("pull_request", "push"):
        block = _event_block("ci.yml", event)
        assert "branches: [main]" in block
        assert "paths:" not in block
    assert 'python-version: ["3.13", "3.14"]' in ci
    assert "check_private_original_source_additions.py" in ci
