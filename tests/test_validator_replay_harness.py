from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tools.validator_replay_harness import (
    IsolatedWorktree,
    LaneType,
    ReplayConfig,
    git_blob_sha,
    overlay_validator_changes,
    run_replay,
    scan_contract_file,
    worktree_blob_sha,
)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _temp_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "tests@example.com")
    _git(repo, "config", "user.name", "Harness Tests")
    (repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    return repo, _git(repo, "rev-parse", "HEAD")


def test_scanner_accepts_canonical_statuses_and_rejects_blocked(tmp_path: Path) -> None:
    path = tmp_path / "test_contract.py"
    path.write_text(
        "from pb_migration_contracts import EvidenceResolutionStatus\n"
        "a = EvidenceResolutionStatus.CORROBORATED\n"
        "b = EvidenceResolutionStatus.BLOCKED\n",
        encoding="utf-8",
    )
    result = scan_contract_file(path)
    assert result["invalid_enum_refs"] == [(3, "BLOCKED")]


def test_scanner_flags_direct_placeholder_but_not_conditional_raise(tmp_path: Path) -> None:
    direct = tmp_path / "direct.py"
    direct.write_text(
        "def test_x():\n    raise AssertionError('not implemented')\n",
        encoding="utf-8",
    )
    conditional = tmp_path / "conditional.py"
    conditional.write_text(
        "def test_x(flag):\n"
        "    if flag:\n"
        "        raise AssertionError('real branch failure')\n",
        encoding="utf-8",
    )
    assert scan_contract_file(direct)["placeholder_raises"]
    assert scan_contract_file(conditional)["placeholder_raises"] == []


def test_git_blob_sha_uses_real_git_object_identity(tmp_path: Path) -> None:
    repo, base = _temp_repo(tmp_path)
    expected = _git(repo, "rev-parse", f"{base}:app.py")
    assert len(expected) == 40
    assert git_blob_sha(repo, base, "app.py") == expected


def test_overlay_uses_validator_ref_and_preserves_exact_blob(tmp_path: Path) -> None:
    repo, base = _temp_repo(tmp_path)
    _git(repo, "checkout", "-b", "validator")
    (repo / "tests").mkdir()
    validator_path = repo / "tests" / "test_contract.py"
    validator_path.write_text(
        "def test_contract():\n    assert True\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "validator")
    validator = _git(repo, "rev-parse", "HEAD")
    expected_blob = _git(repo, "rev-parse", f"{validator}:tests/test_contract.py")

    _git(repo, "checkout", "-B", "production", base)
    (repo / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    _git(repo, "add", "app.py")
    _git(repo, "commit", "-m", "production")
    production = _git(repo, "rev-parse", "HEAD")

    holder: Path | None = None
    with IsolatedWorktree(repo, production, "overlay-test") as worktree:
        holder = worktree
        changed = overlay_validator_changes(
            repo,
            worktree,
            base_sha=base,
            validator_commit=validator,
        )
        assert "tests/test_contract.py" in changed
        assert (worktree / "tests/test_contract.py").exists()
        assert worktree_blob_sha(worktree, "tests/test_contract.py") == expected_blob
        assert (worktree / "app.py").read_text(encoding="utf-8") == "VALUE = 2\n"
    assert holder is not None
    assert not holder.exists()
    assert str(holder) not in _git(repo, "worktree", "list", "--porcelain")


def test_worktree_cleanup_occurs_even_after_exception(tmp_path: Path) -> None:
    repo, base = _temp_repo(tmp_path)
    holder: Path | None = None
    with pytest.raises(RuntimeError):
        with IsolatedWorktree(repo, base, "cleanup-test") as worktree:
            holder = worktree
            raise RuntimeError("boom")
    assert holder is not None
    assert not holder.exists()
    assert str(holder) not in _git(repo, "worktree", "list", "--porcelain")


def test_identity_validator_exact_head_smoke() -> None:
    repo = Path(__file__).resolve().parents[1]
    config = ReplayConfig(
        lane=LaneType.IDENTITY,
        repo_path=repo,
        production_sha="507c57db16be515e2432c695341bdea1e71b3fd7",
        base_sha="62a161519e617cdf9ce23069820dbf7c68aaf521",
        validator_ref="gpt2/opening-instance-identity-redteam-v1",
        validator_path="tests/test_opening_instance_identity_redteam_v1.py",
        expected_validator_blob_sha="b66fbc0701d498357642076688add4287f5e8a24",
    )
    report = run_replay(config)
    assert report.sha_match is True
    assert report.preflight.passed is True
    assert report.production_file_count == 0
    assert report.benchmark_touched is False
    assert report.gold_touched is False
    assert report.holdout_touched is False
    assert report.pytest_normal.passed == 24
    assert report.pytest_normal.failed == 0
    assert report.pytest_runxfail.passed == 24
    assert report.pytest_runxfail.failed == 0
    assert report.verdict == "validator_green"
