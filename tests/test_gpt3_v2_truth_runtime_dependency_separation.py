"""Dependency/runtime manifests cannot change with frozen V2 truth.

Source-neutral path checks only: no original PDF, signed quantity, benchmark
expected value, or production authority is read by these tests.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.check_v2_truth_separation import (
    check_paths,
    find_separation_violation,
    is_production_code_file,
)

ROOT = Path(__file__).resolve().parents[1]
TRUTH = "benchmarks/frozen_holdout/full_plan_v2/manifest.json"
SOURCE = "documents/sources/example.pdf"
RUNTIME = [
    "requirements.txt",
    "requirements-ci-v1228.txt",
    "requirements-original-source.txt",
    "pyproject.toml",
    "setup.cfg",
    "Pipfile",
    "Pipfile.lock",
    "poetry.lock",
    "uv.lock",
]


@pytest.mark.parametrize("runtime", RUNTIME)
@pytest.mark.parametrize("benchmark", [TRUTH, SOURCE])
def test_root_runtime_manifest_and_frozen_source_cannot_cochange(
    runtime: str, benchmark: str,
) -> None:
    assert is_production_code_file(runtime)
    assert find_separation_violation([benchmark, runtime]) == (
        [benchmark], [runtime],
    )
    with pytest.raises(SystemExit, match="Full Plan V2 truth / production separation"):
        check_paths([benchmark, runtime])


def test_runtime_manifest_classification_does_not_depend_on_order_or_duplicates() -> None:
    paths = [
        "requirements.txt",
        SOURCE,
        "requirements-ci-v1228.txt",
        TRUTH,
        "requirements.txt",
    ]
    expected = (
        sorted([SOURCE, TRUTH]),
        ["requirements-ci-v1228.txt", "requirements.txt"],
    )
    assert find_separation_violation(paths) == expected
    assert find_separation_violation(list(reversed(paths))) == expected


@pytest.mark.parametrize(
    "path",
    [
        "docs/requirements.txt",
        "tests/requirements-ci-v1228.txt",
        "benchmarks/requirements.txt",
        "docs/pyproject.toml",
        "tools/pyproject.toml",
        ".github/ISSUE_TEMPLATE/requirements.txt",
        "requirements.txt.bak",
        "requirements.md",
    ],
)
def test_non_runtime_files_do_not_gain_production_authority(path: str) -> None:
    assert not is_production_code_file(path)
    assert find_separation_violation([TRUTH, path]) == ([], [])
    check_paths([TRUTH, path])


@pytest.mark.parametrize("runtime", RUNTIME)
def test_runtime_only_change_is_allowed(runtime: str) -> None:
    assert find_separation_violation([runtime]) == ([], [])
    check_paths([runtime])


def test_windows_style_root_requirement_path_is_protected() -> None:
    assert is_production_code_file(r".\requirements-ci-v1228.txt")
    assert find_separation_violation(
        [TRUTH, r".\requirements-ci-v1228.txt"],
    ) == ([TRUTH], [r".\requirements-ci-v1228.txt"])


def test_real_ci_stdin_gate_rejects_dependency_and_truth_cochange() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_v2_truth_separation.py")],
        input=f"{TRUTH}\nrequirements.txt\n",
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert "Full Plan V2 truth / production separation gate failed" in result.stderr
    assert TRUTH in result.stderr
    assert "requirements.txt" in result.stderr
    assert result.stdout == ""


def test_real_ci_stdin_gate_accepts_dependency_without_truth() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_v2_truth_separation.py")],
        input="requirements.txt\nrequirements-ci-v1228.txt\n",
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert "separation gate passed" in result.stdout
    assert result.stderr == ""
