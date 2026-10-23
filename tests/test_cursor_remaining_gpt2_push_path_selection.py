"""Remaining GPT2 specialist diagnostics must not run for unrelated CANDIDATE modules.

Follow-up to tests/test_gptmax_ci_source_push_path_selection.py after #3727.
This checks checked-in GitHub Actions trigger selection only. Required global CI,
GPT3 signed-replay path lists, source SHAs, and the signed eight are outside
this test's modifications.
"""
from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
DIRECT = {
    "diag-gpt2-ft3-native-wall-pairs.yml": (
        "tools/diag_gpt2_ft3_cross_sheet_native_wall_pairs.py",
        "tests/test_gpt2_ft3_cross_sheet_native_wall_pairs.py",
        "tools/diag_ft3_p11_p7_floor_correspondence.py",
    ),
    "test-gpt2-a120-f07-real-table-whatif.yml": (
        "tools/diag_gpt2_a120_multipath_frame_whatif_shadow.py",
        "tests/test_gpt2_a120_multipath_frame_whatif_shadow.py",
    ),
    "test-gpt2-a120-native-opposed-wall-ink.yml": (
        "tools/diag_native_opposed_source_wall_ink_shadow.py",
        "tests/test_gpt2_a120_opposed_source_wall_ink.py",
    ),
    "test-gpt2-a120-semantic-frame-acceptance.yml": (
        "tools/diag_gpt2_semantic_frame_acceptance_shadow.py",
        "tests/test_gpt2_semantic_frame_acceptance_shadow.py",
    ),
    "test-gpt2-a503-stepped-partition.yml": (
        "tools/diag_native_stepped_partition_source_shadow.py",
        "tests/test_gpt2_native_a503_stepped_partition_shadow.py",
    ),
    "test-gpt2-original-crosssheet-native-ink.yml": (
        "tools/diag_original_crosssheet_native_ink_registration_shadow.py",
        "tests/test_gpt2_original_crosssheet_native_ink_registration.py",
    ),
    "test-gpt2-original-multipath-cad-grid.yml": (
        "tools/diag_native_multipath_cad_grid_source_shadow.py",
        "tests/test_gpt2_native_multipath_cad_grid_source_shadow.py",
    ),
    "test-gpt2-original-native-named-plan-captions.yml": (
        "pb_source_native_named_plan_caption_shadow.py",
        "tests/test_gpt2_native_named_plan_caption_shadow.py",
    ),
    "test-gpt2-original-rotated-text-first-gate.yml": (
        "tools/diag_original_rotated_text_first_gate_delta_shadow.py",
        "tests/test_gpt2_original_rotated_text_first_gate_delta_shadow.py",
    ),
    "test-gpt2-original-semantic-cell-connectivity.yml": (
        "tools/diag_source_connected_semantic_cell_shadow.py",
        "tests/test_gpt2_source_connected_semantic_cell_shadow.py",
    ),
    "test-gpt2-original-window-elevation-identity.yml": (
        "tools/diag_original_window_elevation_title_lineage_shadow.py",
        "tests/test_gpt2_original_window_elevation_title_lineage.py",
    ),
    "test-gpt2-pwd-dimension-face-competitors.yml": (
        "tools/diag_source_dimension_face_competitors_shadow.py",
        "tests/test_gpt2_source_dimension_face_competitors_shadow.py",
    ),
    "test-gpt2-pwd-original-witness-chain.yml": (
        "tools/diag_source_figure_wall_witness_chain_shadow.py",
        "tests/test_gpt2_pwd_native_figure_wall_witness_chain.py",
    ),
    "test-gpt2-rotated-original-clip-parity.yml": (
        "tools/diag_pdf_rotated_native_clip_parity_shadow.py",
        "tests/test_gpt2_pdf_rotated_native_clip_parity_shadow.py",
    ),
    "test-gpt2-six-native-source-gates.yml": (
        "tools/diag_gpt2_six_source_scope_firstgates.py",
        "tests/test_gpt2_six_original_native_source_gates.py",
    ),
    "test-gpt2-symbol-font-source-byte-chain.yml": (
        "tools/diag_pdf_symbol_byte_glyph_shadow.py",
        "tests/test_gpt2_symbol_font_source_code_shadow.py",
    ),
}

GPT3_SIGNED_REPLAY_KEEP_WILDCARD = (
    "test-gpt3-maryborough-original-floor-score-input.yml",
    "score-gpt3-lot16-1215-opening-local.yml",
)


def _source(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def _event_block(name: str, event: str) -> str:
    text = _source(name).split("\njobs:\n", 1)[0]
    marker = f"  {event}:\n"
    assert text.count(marker) == 1, (name, event)
    following = text.split(marker, 1)[1]
    next_event = re.search(r"(?m)^  [a-z][a-z_]*:\s*$", following)
    return following[: next_event.start()] if next_event else following


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
    ci = _source("ci.yml")
    for event in ("pull_request", "push"):
        block = _event_block("ci.yml", event)
        assert "branches: [main]" in block
        assert "paths:" not in block
    assert 'python-version: ["3.13", "3.14"]' in ci
    assert "check_private_original_source_additions.py" in ci


def test_gpt3_signed_replay_path_lists_keep_production_chain_wildcard() -> None:
    for workflow in GPT3_SIGNED_REPLAY_KEEP_WILDCARD:
        assert "pb_*.py" in _paths(_event_block(workflow, "pull_request"))
