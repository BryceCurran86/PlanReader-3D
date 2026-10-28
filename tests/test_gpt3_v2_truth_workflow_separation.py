"""Frozen V2 truth cannot be edited alongside the code that releases or scores it.

These are path-only synthetic controls. They neither inspect frozen expected
quantities nor grant original-source, signed/customer or scoring authority.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.check_v2_truth_separation import (
    check_paths,
    find_separation_violation,
    is_benchmark_defining_file,
    is_production_code_file,
)

ROOT = Path(__file__).resolve().parents[1]
TRUTH = "benchmarks/frozen_holdout/full_plan_v2/manifest.json"
ORIGINAL = "documents/sources/example.pdf"


@pytest.mark.parametrize(
    "release_path",
    [
        ".github/workflows/ci.yml",
        ".github/workflows/trusted-source.yaml",
        ".github/actions/provision-original-sources/action.yml",
        ".github/actions/provision-original-sources/scripts/entrypoint.sh",
        ".github/actions/provision-original-sources/Dockerfile",
    ],
)
@pytest.mark.parametrize("benchmark_path", [TRUTH, ORIGINAL])
def test_frozen_source_and_release_execution_controls_cannot_share_a_change(
    release_path: str, benchmark_path: str,
) -> None:
    assert is_benchmark_defining_file(benchmark_path)
    assert is_production_code_file(release_path)
    assert find_separation_violation([benchmark_path, release_path]) == (
        [benchmark_path], [release_path],
    )
    with pytest.raises(SystemExit, match="Full Plan V2 truth / production separation"):
        check_paths([release_path, benchmark_path])


def test_deduplicated_sorted_release_paths_are_order_independent() -> None:
    paths = [
        ".github/workflows/ci.yml",
        TRUTH,
        ".github/actions/provision-original-sources/action.yml",
        ".github/workflows/ci.yml",
        TRUTH,
    ]
    expected = (
        [TRUTH],
        [".github/actions/provision-original-sources/action.yml", ".github/workflows/ci.yml"],
    )
    assert find_separation_violation(paths) == expected
    assert find_separation_violation(list(reversed(paths))) == expected


@pytest.mark.parametrize(
    "changed",
    [
        [TRUTH],
        [".github/workflows/ci.yml"],
        [".github/actions/provision-original-sources/action.yml"],
        [TRUTH, "docs/release.md", "tests/test_release.py"],
        [TRUTH, ".github/ISSUE_TEMPLATE/bug.yml"],
        [TRUTH, ".github/workflows/notes.txt"],
    ],
)
def test_truth_only_release_only_and_nonexecuting_docs_are_not_blocked(changed: list[str]) -> None:
    assert find_separation_violation(changed) == ([], [])
    check_paths(changed)


def test_existing_production_code_separation_is_unchanged() -> None:
    assert find_separation_violation([TRUTH, "pb_customer_output_verification.py"]) == (
        [TRUTH], ["pb_customer_output_verification.py"],
    )
    assert find_separation_violation([TRUTH, "tests/test_only.py"]) == ([], [])


def test_windows_path_separator_cannot_hide_release_workflow() -> None:
    assert is_production_code_file(r".github\workflows\ci.yml")
    assert is_production_code_file(r".github\actions\provision-original-sources\action.yml")


def test_actual_stdin_ci_entrypoint_fails_closed_and_keeps_details_private() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_v2_truth_separation.py")],
        input=f"{TRUTH}\n.github/workflows/ci.yml\n",
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert TRUTH in result.stderr
    assert ".github/workflows/ci.yml" in result.stderr
    assert result.stdout == ""
    assert "Full Plan V2 truth / production separation gate failed" in result.stderr
