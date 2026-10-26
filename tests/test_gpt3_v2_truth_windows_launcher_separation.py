"""Protect the shipped Windows application launcher from frozen V2 cochanges.

The gate classifies execution paths, not source measurements; all synthetic
benchmark/source paths here are names only and never open private originals.
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
LAUNCHER = "RUN_PLANREADER_WINDOWS.bat"
TRUTH = "benchmarks/frozen_holdout/full_plan_v2/manifest.json"
SOURCE = "documents/sources/example.pdf"


def test_actual_windows_launcher_installs_and_starts_the_commercial_app() -> None:
    launcher = (ROOT / LAUNCHER).read_text(encoding="utf-8")
    assert "pip install -r requirements.txt" in launcher
    assert "streamlit run pb_planreader_v133_app.py" in launcher


@pytest.mark.parametrize("source", [TRUTH, SOURCE])
def test_windows_launcher_and_frozen_inputs_must_be_separate(source: str) -> None:
    assert is_production_code_file(LAUNCHER)
    assert find_separation_violation([source, LAUNCHER]) == (
        [source], [LAUNCHER],
    )
    with pytest.raises(SystemExit, match="Full Plan V2 truth / production separation"):
        check_paths([source, LAUNCHER])


@pytest.mark.parametrize("other", [
    "docs/RUN_PLANREADER_WINDOWS.bat",
    "tests/RUN_PLANREADER_WINDOWS.bat",
    "benchmarks/RUN_PLANREADER_WINDOWS.bat",
    "RUN_PLANREADER_WINDOWS.bat.bak",
    "RUN_PLANREADER_WINDOWS.md",
    "other_launcher.bat",
])
def test_non_shipped_batch_files_are_not_automatically_execution_controls(
    other: str,
) -> None:
    assert not is_production_code_file(other)
    assert find_separation_violation([TRUTH, other]) == ([], [])
    check_paths([TRUTH, other])


def test_windows_launcher_path_classification_is_order_and_duplicate_invariant() -> None:
    paths = [LAUNCHER, SOURCE, LAUNCHER, TRUTH, SOURCE]
    expected = (sorted([TRUTH, SOURCE]), [LAUNCHER])
    assert find_separation_violation(paths) == expected
    assert find_separation_violation(list(reversed(paths))) == expected


def test_actual_ci_nul_stdin_rejects_windows_launcher_and_frozen_truth() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_v2_truth_separation.py"), "--nul"],
        input=(TRUTH + "\0" + LAUNCHER + "\0").encode("utf-8"),
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert b"Full Plan V2 truth / production separation gate failed" in result.stderr
    assert TRUTH.encode("utf-8") in result.stderr
    assert LAUNCHER.encode("utf-8") in result.stderr
    assert result.stdout == b""


def test_actual_ci_nul_stdin_allows_launcher_only() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_v2_truth_separation.py"), "--nul"],
        input=(LAUNCHER + "\0").encode("utf-8"),
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert b"separation gate passed" in result.stdout
    assert result.stderr == b""


def test_windows_path_spelling_keeps_exact_root_launcher_protection() -> None:
    assert is_production_code_file(r".\RUN_PLANREADER_WINDOWS.bat")
    assert find_separation_violation([TRUTH, r".\RUN_PLANREADER_WINDOWS.bat"]) == (
        [TRUTH], [r".\RUN_PLANREADER_WINDOWS.bat"],
    )
