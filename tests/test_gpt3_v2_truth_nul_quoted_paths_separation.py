"""Real Git C-quoted paths must not bypass frozen V2 / production separation.

Synthetic temporary repositories only: no original PDFs, benchmark values,
signed quantities or customer payloads are read.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.check_v2_truth_separation import (
    _stdin_paths_from_bytes,
    find_separation_violation,
)

ROOT = Path(__file__).resolve().parents[1]
TRUTH_ROOT = "benchmarks/frozen_holdout/full_plan_v2/"
PRODUCTION = "pb_synthetic_release.py"


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True,
    ).stdout


def _write(repo: Path, name: str, content: str) -> None:
    target = repo / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "synthetic-git"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Synthetic Security Test")
    _git(repo, "config", "user.email", "synthetic@example.invalid")
    _git(repo, "config", "core.quotePath", "true")
    _write(repo, "README.md", "synthetic baseline\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "synthetic baseline")
    return repo


def _gate(payload: bytes) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_v2_truth_separation.py"), "--nul"],
        input=payload, capture_output=True, check=False,
    )


@pytest.mark.parametrize(
    "relative_truth",
    [
        "projects/café/metadata.json",
        "projects/with\ttab/metadata.json",
        "projects/with\nnewline/metadata.json",
    ],
)
def test_real_git_quoted_truth_path_cannot_hide_with_production_change(
    tmp_path: Path, relative_truth: str,
) -> None:
    repo = _repo(tmp_path)
    frozen_path = TRUTH_ROOT + relative_truth
    _write(repo, frozen_path, "synthetic benchmark file\n")
    _write(repo, PRODUCTION, "print('synthetic')\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "synthetic mixed authority change")

    # Git's normal name-only output C-quotes these valid filenames. The
    # historical line-based parser lost the frozen prefix, even with
    # --no-renames. Prove the failure mode without granting that input in CI.
    quoted = _git(repo, "diff", "--no-renames", "--name-only", "HEAD^", "HEAD")
    assert quoted.startswith(b'"benchmarks/')
    assert find_separation_violation(quoted.decode("utf-8").splitlines()) == ([], [])

    raw = _git(repo, "diff", "--no-renames", "--name-only", "-z", "HEAD^", "HEAD")
    assert raw.endswith(b"\x00")
    assert _stdin_paths_from_bytes(raw, require_nul=True) == [
        frozen_path, PRODUCTION,
    ]
    result = _gate(raw)
    assert result.returncode == 1
    assert b"separation gate failed" in result.stderr
    assert b"Full Plan V2 truth" in result.stderr


def test_lossless_nul_reader_keeps_whitespace_and_unicode_without_stripping() -> None:
    paths = [
        TRUTH_ROOT + "projects/café/trailing space ",
        "pb_synthetic_release.py",
    ]
    raw = b"\x00".join(path.encode("utf-8") for path in paths) + b"\x00"
    assert _stdin_paths_from_bytes(raw, require_nul=True) == paths
    assert find_separation_violation(paths) == (paths[:1], paths[1:])


@pytest.mark.parametrize(
    "payload",
    [
        b"pb_synthetic_release.py\n",
        b"pb_synthetic_release.py\x00benchmarks/frozen_holdout/full_plan_v2/x",
        b"\xff\x00",
    ],
)
def test_required_nul_mode_fails_closed_on_malformed_diff_stream(payload: bytes) -> None:
    result = _gate(payload)
    assert result.returncode != 0
    assert b"input invalid" in result.stderr
    assert b"separation gate passed" not in result.stdout


def test_empty_nul_diff_and_single_authority_class_remain_allowed() -> None:
    for payload in (
        b"",
        b"pb_synthetic_release.py\x00",
        (TRUTH_ROOT + "projects/café/metadata.json\x00").encode("utf-8"),
    ):
        result = _gate(payload)
        assert result.returncode == 0, result.stderr.decode("utf-8")
        assert b"separation gate passed" in result.stdout


def test_required_ci_uses_nul_paths_on_pr_and_push() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    command = (
        'git diff --no-renames --name-only -z "$BASE_SHA" "$HEAD_SHA" '
        '| python scripts/check_v2_truth_separation.py --nul'
    )
    assert workflow.count(command) == 2
    assert 'git diff --no-renames --name-only "$BASE_SHA" "$HEAD_SHA"' not in workflow


@pytest.mark.parametrize(
    "literal_root_code",
    [
        r"tests\\synthetic_release.py",
        r"docs\\synthetic_release.py",
        r"benchmarks\\synthetic_release.py",
    ],
)
def test_real_git_literal_backslash_root_code_cannot_hide_with_frozen_truth(
    tmp_path: Path, literal_root_code: str,
) -> None:
    """A Git backslash is part of a filename, not a POSIX directory boundary."""
    repo = _repo(tmp_path)
    frozen_path = TRUTH_ROOT + "manifest.json"
    _write(repo, frozen_path, "synthetic frozen metadata\\n")
    _write(repo, literal_root_code, "print('synthetic release')\\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "synthetic mixed literal-backslash change")

    raw = _git(repo, "diff", "--no-renames", "--name-only", "-z", "HEAD^", "HEAD")
    paths = _stdin_paths_from_bytes(raw, require_nul=True)
    assert sorted(paths) == sorted([frozen_path, literal_root_code])
    assert find_separation_violation(paths, git_path=True) == (
        [frozen_path], [literal_root_code],
    )
    result = _gate(raw)
    assert result.returncode == 1
    assert b"separation gate failed" in result.stderr
    assert b"separation gate passed" not in result.stdout


def test_git_literal_backslashes_do_not_invent_a_frozen_directory(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    literal_root_file = r"benchmarks\\frozen_holdout\\full_plan_v2\\manifest.json"
    _write(repo, literal_root_file, "synthetic unrelated root filename\\n")
    _write(repo, PRODUCTION, "print('synthetic release')\\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "synthetic production plus unrelated root filename")

    raw = _git(repo, "diff", "--no-renames", "--name-only", "-z", "HEAD^", "HEAD")
    paths = _stdin_paths_from_bytes(raw, require_nul=True)
    assert sorted(paths) == sorted([literal_root_file, PRODUCTION])
    assert find_separation_violation(paths, git_path=True) == ([], [])
    result = _gate(raw)
    assert result.returncode == 0, result.stderr.decode("utf-8")
    assert b"separation gate passed" in result.stdout
