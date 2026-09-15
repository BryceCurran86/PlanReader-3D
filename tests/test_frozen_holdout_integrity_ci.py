"""CI wiring for frozen holdout integrity verifier."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from scripts.check_benchmark_gold_separation import check_paths
from scripts.check_frozen_holdout_integrity import find_established_lock_rewrites
import pytest


_DEFINING_FILES = (
    "source_manifest.json",
    "benchmark_rules.json",
    "expected_project.json",
    "expected_boq_summary.json",
)


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=check,
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")


def _write_registered_holdout(holdout_dir: Path, *, project_id: str, digest: str) -> None:
    holdout_dir.mkdir(parents=True, exist_ok=True)
    for name in _DEFINING_FILES:
        (holdout_dir / name).write_text(
            json.dumps({"project_id": project_id, "file": name, "digest": digest}),
            encoding="utf-8",
        )
    (holdout_dir / ".holdout_lock.json").write_text(
        json.dumps(
            {
                "project_id": project_id,
                "source_manifest_sha256": digest,
                "benchmark_rules_sha256": digest,
                "expected_project_sha256": digest,
                "expected_boq_summary_sha256": digest,
            }
        ),
        encoding="utf-8",
    )


def test_frozen_holdout_integrity_script_exits_clean_when_no_registered_projects() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(".").resolve())
    # Local unit run has no PR base/head; rewrite check is skipped unless required.
    env.pop("REQUIRE_HOLDOUT_BASE_LOCK_CHECK", None)
    env.pop("BASE_SHA", None)
    env.pop("HEAD_SHA", None)
    completed = subprocess.run(
        [sys.executable, "scripts/check_frozen_holdout_integrity.py"],
        cwd=".",
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert completed.returncode == 0, completed.stderr


def test_holdout_lock_plus_production_fails_separation() -> None:
    with pytest.raises(SystemExit):
        check_paths(
            [
                "benchmarks/frozen_holdout/example/.holdout_lock.json",
                "pb_planreader_pdf_extractor.py",
            ]
        )


def test_established_lock_rewrite_with_matching_expected_edit_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Editing expected gold and regenerating the lock must not self-certify."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    holdout = repo / "benchmarks" / "frozen_holdout" / "proj_a"
    _write_registered_holdout(holdout, project_id="proj_a", digest="aaa")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base registered holdout")
    base_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()

    _write_registered_holdout(holdout, project_id="proj_a", digest="bbb")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "tamper expected and rewrite lock")
    head_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()

    monkeypatch.chdir(repo)
    failures = find_established_lock_rewrites(base_sha=base_sha, head_sha=head_sha)
    assert failures, "rewritten established lock must fail"
    assert any("rewritten" in f for f in failures)


def test_entire_registered_holdout_project_deletion_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deleting the whole registered project directory must fail at BASE enumeration."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    holdout = repo / "benchmarks" / "frozen_holdout" / "proj_a"
    _write_registered_holdout(holdout, project_id="proj_a", digest="aaa")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base registered holdout")
    base_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()

    # Remove entire project tree (including the lock).
    for path in sorted(holdout.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
    holdout.rmdir()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "delete entire registered holdout project")
    head_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()

    monkeypatch.chdir(repo)
    failures = find_established_lock_rewrites(base_sha=base_sha, head_sha=head_sha)
    assert failures, "deleted registered holdout project must fail"
    assert any("deleted" in f and "proj_a" in f for f in failures)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    env["BASE_SHA"] = base_sha
    env["HEAD_SHA"] = head_sha
    env["REQUIRE_HOLDOUT_BASE_LOCK_CHECK"] = "1"
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "check_frozen_holdout_integrity.py")],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    # Script imports pb_holdout from the real repo via PYTHONPATH; HEAD has no
    # registered projects, so checksum loop is empty, but BASE lock rewrite
    # check must still exit nonzero.
    assert completed.returncode != 0, completed.stdout + completed.stderr
    assert "proj_a" in (completed.stderr + completed.stdout)


def test_established_project_directory_renamed_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    root = repo / "benchmarks" / "frozen_holdout"
    _write_registered_holdout(root / "proj_a", project_id="proj_a", digest="aaa")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    base_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()

    (root / "proj_a").rename(root / "proj_a_renamed")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "rename registered holdout")
    head_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()

    monkeypatch.chdir(repo)
    failures = find_established_lock_rewrites(base_sha=base_sha, head_sha=head_sha)
    assert any("proj_a" in f and "deleted" in f for f in failures)


def test_established_project_deleted_and_recreated_under_other_name_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    root = repo / "benchmarks" / "frozen_holdout"
    _write_registered_holdout(root / "proj_a", project_id="proj_a", digest="aaa")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    base_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()

    for path in sorted((root / "proj_a").rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
    (root / "proj_a").rmdir()
    _write_registered_holdout(root / "proj_b", project_id="proj_b", digest="aaa")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "recreate under another name")
    head_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()

    monkeypatch.chdir(repo)
    failures = find_established_lock_rewrites(base_sha=base_sha, head_sha=head_sha)
    assert any("proj_a" in f and "deleted" in f for f in failures)


def test_unrelated_unregistered_directory_deletion_does_not_fail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    root = repo / "benchmarks" / "frozen_holdout"
    _write_registered_holdout(root / "proj_a", project_id="proj_a", digest="aaa")
    scratch = root / "scratch_unregistered"
    scratch.mkdir(parents=True)
    (scratch / "notes.md").write_text("not a registered holdout\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base with unregistered dir")
    base_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()

    for path in sorted(scratch.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
    scratch.rmdir()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "delete unregistered only")
    head_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()

    monkeypatch.chdir(repo)
    failures = find_established_lock_rewrites(base_sha=base_sha, head_sha=head_sha)
    assert failures == []


def test_first_time_registration_without_base_lock_is_allowed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    root = repo / "benchmarks" / "frozen_holdout"
    root.mkdir(parents=True)
    (root / "README.md").write_text("holdout root\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "empty holdout root")
    base_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()

    _write_registered_holdout(root / "proj_new", project_id="proj_new", digest="ccc")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "first-time registration")
    head_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()

    monkeypatch.chdir(repo)
    failures = find_established_lock_rewrites(base_sha=base_sha, head_sha=head_sha)
    assert failures == []
