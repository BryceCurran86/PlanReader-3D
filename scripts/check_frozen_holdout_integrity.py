"""Verify registered frozen holdout projects remain untouched.

Registered holdouts under ``benchmarks/frozen_holdout/`` must keep their
benchmark-defining JSON checksums stable. This script is CI-safe: projects
without a ``.holdout_lock.json`` are excluded (sealed/pending transcription).
"""
from __future__ import annotations

from pathlib import Path
import sys

from pb_holdout_suite_registry import (
    list_registered_holdout_projects,
    verify_holdout_untouched,
)


def main() -> int:
    holdout_root = Path("benchmarks/frozen_holdout")
    registered = list_registered_holdout_projects(holdout_root)
    if not registered:
        print("No registered frozen holdout projects to verify.")
        return 0

    failures: list[str] = []
    for project_id in registered:
        result = verify_holdout_untouched(holdout_root / project_id)
        if not result.is_untouched:
            failures.append(
                f"{project_id}: " + "; ".join(result.mismatches or ["unknown mismatch"])
            )

    if failures:
        print("Frozen holdout integrity check failed:", file=sys.stderr)
        for line in failures:
            print(f"  - {line}", file=sys.stderr)
        return 1

    print(f"Verified {len(registered)} registered frozen holdout project(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
