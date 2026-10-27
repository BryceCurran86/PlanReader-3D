"""Deployed Docker/Render entrypoints cannot cochange with frozen V2 inputs.

This is a path-only release-security check. No benchmark values, private PDF,
customer payload or signed production quantity is loaded.
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
DEPLOYMENT_CONTROLS = ("Dockerfile", "render.yaml")


@pytest.mark.parametrize("deployment", DEPLOYMENT_CONTROLS)
@pytest.mark.parametrize("source", [TRUTH, SOURCE])
def test_deployed_runtime_and_frozen_source_must_be_separate(
    deployment: str, source: str,
) -> None:
    assert is_production_code_file(deployment)
    assert find_separation_violation([source, deployment]) == (
        [source], [deployment],
    )
    with pytest.raises(SystemExit, match="Full Plan V2 truth / production separation"):
        check_paths([source, deployment])


def test_actual_render_service_uses_the_root_dockerfile() -> None:
    """Exercise the real deployed file names, not a hypothetical config."""
    render = (ROOT / "render.yaml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "runtime: docker" in render
    assert "dockerfilePath: ./Dockerfile" in render
    assert "FROM python:" in dockerfile
    assert "pb_planreader_v133_app.py" in dockerfile


@pytest.mark.parametrize(
    "path",
    [
        "docs/Dockerfile",
        "tests/Dockerfile",
        "benchmarks/Dockerfile",
        "docs/render.yaml",
        ".github/ISSUE_TEMPLATE/render.yaml",
        "Dockerfile.example",
        "render.yaml.bak",
    ],
)
def test_non_deployment_names_do_not_gain_production_authority(path: str) -> None:
    assert not is_production_code_file(path)
    assert find_separation_violation([TRUTH, path]) == ([], [])
    check_paths([TRUTH, path])


def test_deployment_only_or_frozen_only_changes_remain_allowed() -> None:
    check_paths(list(DEPLOYMENT_CONTROLS))
    check_paths([TRUTH, SOURCE, "docs/release-notes.md", "tests/test_only.py"])


def test_deployment_separation_is_order_and_duplicate_invariant() -> None:
    paths = [TRUTH, "Dockerfile", SOURCE, "render.yaml", "Dockerfile", TRUTH]
    expected = (sorted([SOURCE, TRUTH]), sorted(DEPLOYMENT_CONTROLS))
    assert find_separation_violation(paths) == expected
    assert find_separation_violation(list(reversed(paths))) == expected


@pytest.mark.parametrize("deployment", DEPLOYMENT_CONTROLS)
def test_actual_ci_stdin_entrypoint_rejects_deployment_and_truth(
    deployment: str,
) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_v2_truth_separation.py")],
        input=f"{TRUTH}\n{deployment}\n",
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert "Full Plan V2 truth / production separation gate failed" in result.stderr
    assert TRUTH in result.stderr
    assert deployment in result.stderr
    assert result.stdout == ""


@pytest.mark.parametrize("deployment", DEPLOYMENT_CONTROLS)
def test_actual_ci_stdin_entrypoint_allows_deployment_only(
    deployment: str,
) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_v2_truth_separation.py")],
        input=f"{deployment}\n",
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert "separation gate passed" in result.stdout
    assert result.stderr == ""
