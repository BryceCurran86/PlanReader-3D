"""Verify registered frozen holdout projects remain untouched.

Two checks are required:

1. Current holdout defining files must still match the current lock
   (ordinary tampering).
2. An *already-registered* lock at the repository base/merge-base must not be
   rewritten or deleted at HEAD. Regenerating ``.holdout_lock.json`` after
   editing expected files must not self-certify the change.

First-time registration (no lock at base, lock created at HEAD) is allowed by
this script, but CI gold/production separation still forbids bundling that
registration with production extraction/scoring changes.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from pb_holdout_suite_registry import (
    list_registered_holdout_projects,
    verify_holdout_untouched,
)

_LOCK_NAME = ".holdout_lock.json"
_HOLDOUT_ROOT = Path("benchmarks/frozen_holdout")


def _git_show(sha: str, path: str) -> str | None:
    """Return file contents at ``sha:path``, or None if absent."""
    completed = subprocess.run(
        ["git", "show", f"{sha}:{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout


def _normalize(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def find_established_lock_rewrites(
    *,
    base_sha: str,
    head_sha: str,
    holdout_root: Path = _HOLDOUT_ROOT,
) -> list[str]:
    """Fail when an established base lock is changed or deleted at HEAD."""
    if not holdout_root.is_dir():
        return []

    failures: list[str] = []
    for child in sorted(holdout_root.iterdir()):
        if not child.is_dir():
            continue
        project_id = child.name
        lock_rel = _normalize(str(child / _LOCK_NAME))
        base_lock = _git_show(base_sha, lock_rel)
        if base_lock is None:
            # First-time registration path — no established lock to protect.
            continue
        head_lock = _git_show(head_sha, lock_rel)
        if head_lock is None:
            failures.append(
                f"{project_id}: established {_LOCK_NAME} deleted between "
                f"{base_sha[:12]} and {head_sha[:12]}"
            )
            continue
        if head_lock != base_lock:
            failures.append(
                f"{project_id}: established {_LOCK_NAME} rewritten between "
                f"{base_sha[:12]} and {head_sha[:12]} "
                "(lock must not self-certify holdout gold edits)"
            )
    return failures


def main(argv: list[str] | None = None) -> int:
    del argv  # reserved for future CLI flags
    holdout_root = _HOLDOUT_ROOT
    failures: list[str] = []

    registered = list_registered_holdout_projects(holdout_root)
    for project_id in registered:
        result = verify_holdout_untouched(holdout_root / project_id)
        if not result.is_untouched:
            failures.append(
                f"{project_id}: " + "; ".join(result.mismatches or ["unknown mismatch"])
            )

    base_sha = os.environ.get("BASE_SHA", "").strip()
    head_sha = os.environ.get("HEAD_SHA", "").strip()
    if base_sha and head_sha:
        failures.extend(
            find_established_lock_rewrites(base_sha=base_sha, head_sha=head_sha)
        )
    elif os.environ.get("REQUIRE_HOLDOUT_BASE_LOCK_CHECK", "").strip() == "1":
        print(
            "Frozen holdout integrity requires BASE_SHA and HEAD_SHA.",
            file=sys.stderr,
        )
        return 1

    if failures:
        print("Frozen holdout integrity check failed:", file=sys.stderr)
        for line in failures:
            print(f"  - {line}", file=sys.stderr)
        return 1

    if registered:
        print(f"Verified {len(registered)} registered frozen holdout project(s).")
    else:
        print("No registered frozen holdout projects to verify.")
    if base_sha and head_sha:
        print(
            f"Established lock rewrite check passed "
            f"({base_sha[:12]}..{head_sha[:12]})."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
