"""CI must send Git type changes to the private-original source guard."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
GUARD = ROOT / "scripts" / "check_private_original_source_additions.py"
SYNTHETIC_BYTES = b"%PDF-1.7 synthetic stand-in, never an original source\n" * 12


def _git(repo: Path, *args: str, capture: bool = False) -> bytes:
    result = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=capture,
    )
    return result.stdout if capture else b""


def test_pr_and_push_ci_both_include_type_changed_paths():
    text = WORKFLOW.read_text(encoding="utf-8")
    # Both PR and push must feed the same complete NUL-delimited Git path set.
    assert text.count("git diff --diff-filter=AMRCT --name-only -z") == 2
    assert "git diff --diff-filter=AMRC --name-only -z" not in text
    assert text.count("| python scripts/check_private_original_source_additions.py") == 2


@pytest.mark.skipif(sys.platform == "win32", reason="requires POSIX symlink semantics")
def test_real_git_symlink_to_pinned_original_type_change_reaches_guard(tmp_path):
    """An unrelated tracked symlink can become an exact-byte original PDF."""
    repo = tmp_path
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Synthetic CI Test")
    _git(repo, "config", "user.email", "ci-test@example.invalid")

    manifest_dir = (
        repo / "benchmarks" / "frozen_holdout" / "full_plan_v2"
        / "projects" / "synthetic"
    )
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "source_manifest.json").write_text(
        json.dumps({"source_documents": [{
            "name": "Private-Source-Standin.pdf",
            "size_bytes": len(SYNTHETIC_BYTES),
            "sha256": hashlib.sha256(SYNTHETIC_BYTES).hexdigest(),
        }]}),
        encoding="utf-8",
    )
    (repo / "target.txt").write_text("harmless synthetic link target", encoding="utf-8")
    alias = repo / "innocuous-alias.pdf"
    alias.symlink_to("target.txt")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "baseline with symlink")

    alias.unlink()
    alias.write_bytes(SYNTHETIC_BYTES)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "type change to pinned synthetic bytes")

    old_filter = _git(
        repo, "diff", "--diff-filter=AMRC", "--name-only", "-z",
        "HEAD^", "HEAD", capture=True,
    )
    changed = _git(
        repo, "diff", "--diff-filter=AMRCT", "--name-only", "-z",
        "HEAD^", "HEAD", capture=True,
    )
    assert old_filter == b""  # The actual bypass on prior main.
    assert changed == b"innocuous-alias.pdf\x00"
    result = subprocess.run(
        [sys.executable, str(GUARD), "--root", str(repo)],
        input=changed, capture_output=True,
    )
    assert result.returncode == 1
    assert b"bytes of a pinned original source document" in result.stderr
    assert alias.read_bytes() == SYNTHETIC_BYTES
