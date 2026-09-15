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
    repo.mkdir()
    holdout = repo / "benchmarks" / "frozen_holdout" / "proj_a"
    holdout.mkdir(parents=True)

    def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            check=check,
        )

    _git("init")
    _git("config", "user.email", "test@example.com")
    _git("config", "user.name", "Test")

    expected = holdout / "expected_boq_summary.json"
    lock = holdout / ".holdout_lock.json"
    expected.write_text(json.dumps({"measurable_items_count": 1}), encoding="utf-8")
    lock.write_text(
        json.dumps({"project_id": "proj_a", "expected_boq_summary_sha256": "aaa"}),
        encoding="utf-8",
    )
    _git("add", ".")
    _git("commit", "-m", "base registered holdout")
    base_sha = _git("rev-parse", "HEAD").stdout.strip()

    expected.write_text(json.dumps({"measurable_items_count": 2}), encoding="utf-8")
    lock.write_text(
        json.dumps({"project_id": "proj_a", "expected_boq_summary_sha256": "bbb"}),
        encoding="utf-8",
    )
    _git("add", ".")
    _git("commit", "-m", "tamper expected and rewrite lock")
    head_sha = _git("rev-parse", "HEAD").stdout.strip()

    monkeypatch.chdir(repo)
    failures = find_established_lock_rewrites(base_sha=base_sha, head_sha=head_sha)
    assert failures, "rewritten established lock must fail"
    assert any("rewritten" in f for f in failures)
