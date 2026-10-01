"""Fail CI when active Full Plan V2 truth and production code change together."""
from __future__ import annotations

from pathlib import PurePosixPath
import sys
from typing import Iterable, Sequence

_V2_ROOT = "benchmarks/frozen_holdout/full_plan_v2/"
_V2_TRUTH_FILENAMES = {
    "manifest.json",
    "source_manifest.json",
    "reference_takeoff.json",
    "object_universe.json",
    "verification_report.json",
    "unresolved_items.json",
}
_PRODUCTION_SUFFIXES = {".py", ".js", ".html"}
_PRODUCTION_EXCLUDED_PREFIXES = (
    "tests/",
    "benchmarks/",
    "docs/",
)


def _normalize(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def is_v2_truth_file(path: str) -> bool:
    normalized = _normalize(path)
    if not normalized.startswith(_V2_ROOT):
        return False
    return PurePosixPath(normalized).name in _V2_TRUTH_FILENAMES


def is_production_code_file(path: str) -> bool:
    normalized = _normalize(path)
    if normalized.startswith(_PRODUCTION_EXCLUDED_PREFIXES):
        return False
    return PurePosixPath(normalized).suffix.lower() in _PRODUCTION_SUFFIXES


def find_separation_violation(changed_paths: Sequence[str]) -> tuple[list[str], list[str]]:
    truth_files = sorted({p for p in changed_paths if is_v2_truth_file(p)})
    production_files = sorted({p for p in changed_paths if is_production_code_file(p)})
    if truth_files and production_files:
        return truth_files, production_files
    return [], []


def check_paths(changed_paths: Sequence[str]) -> None:
    truth_files, production_files = find_separation_violation(changed_paths)
    if not truth_files:
        return
    raise SystemExit(
        "\n".join(
            [
                "Full Plan V2 truth / production separation gate failed.",
                "Source-closed V2 truth and production code must be changed in separate PRs.",
                "",
                "V2 truth files:",
                *[f"  - {p}" for p in truth_files],
                "",
                "Production-code files:",
                *[f"  - {p}" for p in production_files],
                "",
                "Split this into an independently evidenced V2 truth PR and a production-code PR.",
            ]
        )
    )


def _stdin_paths(lines: Iterable[str]) -> list[str]:
    return [line.strip() for line in lines if line.strip()]


def main() -> int:
    changed_paths = _stdin_paths(sys.stdin)
    try:
        check_paths(changed_paths)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("Full Plan V2 truth / production separation gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
