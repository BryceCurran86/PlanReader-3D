"""Frozen V2 truth cannot be paired with pytest collection-policy changes.

Synthetic path-only security checks; no benchmark expected values, original
source bytes, signed/customer receipts or measurement authority are read.
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
SOURCE = "documents/sources/synthetic-original.pdf"


@pytest.mark.parametrize("harness", [
    "tests/conftest.py",
    "tests/unit/conftest.py",
    "tests/unit/nested/conftest.py",
])
@pytest.mark.parametrize("benchmark", [TRUTH, SOURCE])
def test_pytest_collection_policy_is_release_execution_control(harness, benchmark):
    assert is_production_code_file(harness)
    assert find_separation_violation([benchmark, harness]) == (
        [benchmark], [harness],
    )
    with pytest.raises(SystemExit, match="Full Plan V2 truth / production separation"):
        check_paths([harness, benchmark])


@pytest.mark.parametrize("config", [
    "pytest.ini", "tox.ini", "tests/pytest.ini", "tests/tox.ini",
])
@pytest.mark.parametrize("benchmark", [TRUTH, SOURCE])
def test_pytest_config_is_release_execution_control(config, benchmark):
    assert is_production_code_file(config)
    assert find_separation_violation([benchmark, config]) == (
        [benchmark], [config],
    )
    with pytest.raises(SystemExit, match="Full Plan V2 truth / production separation"):
        check_paths([config, benchmark])


@pytest.mark.parametrize("ordinary", [
    "tests/test_quantity.py",
    "tests/unit/test_quantity.py",
    "tests/conftest.py.bak",
    "tests/test_conftest.py",
    "docs/conftest.py",
    "benchmarks/conftest.py",
    "docs/pytest.ini",
    "docs/tox.ini",
    "tests/unit/pytest.ini",
    "tests/unit/tox.ini",
    "tests/pytest.ini.bak",
])
def test_ordinary_tests_and_nonexecuting_conftest_names_remain_excluded(ordinary):
    assert not is_production_code_file(ordinary)
    assert find_separation_violation([TRUTH, ordinary]) == ([], [])
    check_paths([TRUTH, ordinary])


def test_harness_only_and_truth_only_changes_still_pass():
    check_paths(["tests/conftest.py", "tests/unit/conftest.py"])
    check_paths([TRUTH, "tests/test_quantity.py"])


def test_windows_helper_path_is_detected_without_reinterpreting_git_backslashes():
    windows = r"tests\unit\conftest.py"
    assert is_production_code_file(windows)
    assert find_separation_violation([TRUTH, windows]) == ([TRUTH], [windows])
    # Git -z uses POSIX separators. A literal backslash does not create a
    # tests/ subdirectory; the root-level .py suffix is independently code.
    assert is_production_code_file(windows, git_path=True)


def test_cli_nul_delimited_git_paths_fail_closed_on_frozen_truth_cochange():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_v2_truth_separation.py"), "--nul"],
        input=(TRUTH + "\0tests/unit/conftest.py\0").encode("utf-8"),
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert b"Full Plan V2 truth / production separation gate failed" in result.stderr
    assert b"tests/unit/conftest.py" in result.stderr
    assert b"separation gate passed" not in result.stdout


@pytest.mark.parametrize("config", [
    "pytest.ini", "tox.ini", "tests/pytest.ini", "tests/tox.ini",
])
@pytest.mark.parametrize("benchmark", [TRUTH, SOURCE])
def test_cli_nul_delimited_pytest_config_cochange_fails_closed(config, benchmark):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_v2_truth_separation.py"), "--nul"],
        input=(benchmark + "\0" + config + "\0").encode("utf-8"),
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert b"Full Plan V2 truth / production separation gate failed" in result.stderr
    assert config.encode("utf-8") in result.stderr


def test_cli_nul_delimited_pytest_config_only_remains_allowed():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_v2_truth_separation.py"), "--nul"],
        input=b"pytest.ini\0tests/tox.ini\0",
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert b"separation gate passed" in result.stdout
    assert result.stderr == b""


def test_cli_nul_delimited_ordinary_test_cochange_remains_allowed():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_v2_truth_separation.py"), "--nul"],
        input=(TRUTH + "\0tests/unit/test_quantity.py\0").encode("utf-8"),
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert b"separation gate passed" in result.stdout
    assert result.stderr == b""
