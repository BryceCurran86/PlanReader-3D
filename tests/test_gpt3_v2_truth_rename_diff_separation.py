"""The CI V2 separation diff must expose both sides of Git renames.

Source-neutral temporary Git repositories prove the actual CLI input shape.
No frozen expected value, private original, signer, or customer output is read.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.check_v2_truth_separation import (
    check_paths,
    find_separation_violation,
)

ROOT = Path(__file__).resolve().parents[1]
TRUTH = "benchmarks/frozen_holdout/full_plan_v2/manifest.json"
RELEASE = "pb_example_release.py"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _write(repo: Path, name: str, value: str) -> None:
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "synthetic-git"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Synthetic CI Test")
    _git(repo, "config", "user.email", "synthetic@example.invalid")
    return repo


def _commit(repo: Path, message: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)


def _changed(repo: Path, *, disable_renames: bool) -> list[str]:
    args = ["-c", "diff.renames=true", "diff"]
    if disable_renames:
        args.append("--no-renames")
    args.extend(["--name-only", "HEAD^", "HEAD"])
    return _git(repo, *args).splitlines()


@pytest.mark.parametrize("direction", ["truth_to_docs", "production_to_truth"])
def test_rename_source_and_destination_are_both_visible_to_real_gate(
    tmp_path: Path, direction: str,
) -> None:
    repo = _repo(tmp_path)
    if direction == "truth_to_docs":
        _write(repo, TRUTH, "synthetic immutable benchmark input\n")
        _write(repo, RELEASE, "print('before')\n")
        _commit(repo, "synthetic baseline")
        (repo / "docs").mkdir()
        _git(repo, "mv", TRUTH, "docs/moved_manifest.json")
        _write(repo, RELEASE, "print('after')\n")
        expected_truth = [TRUTH]
        expected_production = [RELEASE]
    else:
        _write(repo, RELEASE, "print('synthetic release control')\n")
        _commit(repo, "synthetic baseline")
        (repo / TRUTH).parent.mkdir(parents=True)
        _git(repo, "mv", RELEASE, TRUTH)
        expected_truth = [TRUTH]
        expected_production = [RELEASE]
    _commit(repo, "rename and potentially conceal one protected side")

    rename_collapsed = _changed(repo, disable_renames=False)
    assert find_separation_violation(rename_collapsed) == ([], [])

    visible = _changed(repo, disable_renames=True)
    assert find_separation_violation(visible) == (
        expected_truth, expected_production,
    )
    with pytest.raises(SystemExit, match="Full Plan V2 truth / production separation"):
        check_paths(visible)

    actual_cli = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_v2_truth_separation.py")],
        input="\n".join(visible) + "\n",
        text=True,
        capture_output=True,
        check=False,
    )
    assert actual_cli.returncode == 1
    assert "separation gate failed" in actual_cli.stderr
    assert all(path in actual_cli.stderr for path in expected_truth + expected_production)
    assert actual_cli.stdout == ""


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("docs/old.txt", "docs/new.txt"),
        (TRUTH, "benchmarks/frozen_holdout/full_plan_v2/renamed_manifest.json"),
        ("pb_old.py", "pb_new.py"),
    ],
)
def test_single_authority_class_rename_remains_permitted(
    tmp_path: Path, before: str, after: str,
) -> None:
    repo = _repo(tmp_path)
    _write(repo, before, "synthetic fixture bytes\n")
    _commit(repo, "synthetic baseline")
    (repo / after).parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "mv", before, after)
    _commit(repo, "single authority class rename")
    changed = _changed(repo, disable_renames=True)
    assert sorted(changed) == sorted([before, after])
    assert find_separation_violation(changed) == ([], [])
    check_paths(changed)


def test_required_ci_uses_no_rename_detection_in_both_v2_diff_pipelines() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    fixed = (
        'git diff --no-renames --name-only -z "$BASE_SHA" "$HEAD_SHA" '
        '| python scripts/check_v2_truth_separation.py --nul'
    )
    unsafe = (
        'git diff --name-only "$BASE_SHA" "$HEAD_SHA" '
        '| python scripts/check_v2_truth_separation.py --nul'
    )
    assert workflow.count(fixed) == 2
    assert unsafe not in workflow
    assert "Enforce Full Plan V2 truth / production separation (pull request)" in workflow
    assert "Enforce Full Plan V2 truth / production separation (push)" in workflow
