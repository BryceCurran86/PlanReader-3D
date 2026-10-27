"""Fail CI when active Full Plan V2 truth and production code change together."""
from __future__ import annotations

import argparse
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
_SOURCE_PDF_ROOT = "documents/sources/"
_PRODUCTION_SUFFIXES = {".py", ".js", ".html"}
_PRODUCTION_EXCLUDED_PREFIXES = (
    "tests/",
    "benchmarks/",
    "docs/",
)
# Workflow YAML and every local composite/Docker action input can change how
# source-positive and signed/customer acceptance is executed. They are
# production release controls, not benchmark truth, and must be kept in a
# separate PR from any frozen V2 source/evaluator change.
_WORKFLOW_ROOT = ".github/workflows/"
_WORKFLOW_SUFFIXES = {".yml", ".yaml"}
_LOCAL_ACTION_ROOT = ".github/actions/"
# Pytest discovers these configuration files from the repository root or the
# explicitly targeted tests/ directory. addopts can silently omit signed or
# original-source tests; config changes are release-execution controls.
_PYTEST_CONFIG_PATHS = frozenset({
    "pytest.ini", "tox.ini", "tests/pytest.ini", "tests/tox.ini",
})
# These root manifests select the interpreter's package/runtime environment for
# both public CI and the trusted original-source replay. Changing one alongside
# frozen benchmark inputs is a production-execution change even without a .py
# diff; do not let a dependency-only edit bypass the separation gate.
_ROOT_RUNTIME_MANIFESTS = frozenset({
    "pyproject.toml",
    "setup.cfg",
    "Pipfile",
    "Pipfile.lock",
    "poetry.lock",
    "uv.lock",
    # The deployed Render service selects this root Dockerfile to install
    # dependencies and launch the commercial application. Both files control
    # production execution, even though neither has a Python/JS suffix.
    "Dockerfile",
    "render.yaml",
    # The shipped Windows entrypoint installs runtime dependencies and starts
    # the same commercial Streamlit app. It is executable release control,
    # not a documentation-only batch file.
    "RUN_PLANREADER_WINDOWS.bat",
})


def _is_root_runtime_manifest(path: str) -> bool:
    candidate = PurePosixPath(path)
    if len(candidate.parts) != 1:
        return False
    name = candidate.name
    return name in _ROOT_RUNTIME_MANIFESTS or (
        name.startswith("requirements") and name.endswith(".txt")
    )


def _normalize(path: str, *, git_path: bool = False) -> str:
    # Git -z emits repository-relative POSIX paths. A backslash in one of
    # those paths is a literal filename character, NOT a directory separator.
    # Retain historical Windows-path support for non-Git helper callers.
    normalized = path if git_path else path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def is_v2_truth_file(path: str, *, git_path: bool = False) -> bool:
    normalized = _normalize(path, git_path=git_path)
    if not normalized.startswith(_V2_ROOT):
        return False
    return PurePosixPath(normalized).name in _V2_TRUTH_FILENAMES


def is_benchmark_defining_file(path: str, *, git_path: bool = False) -> bool:
    """Everything that defines or feeds the frozen benchmark: the named truth files, ANY other file in the V2 tree
    (evaluators, reconcilers, identity maps, runners) and the original source PDFs.

    ``is_v2_truth_file`` stays the narrow predicate for the six truth filenames; this wider one is what the separation gate uses, so
    scorer code, tolerances or a source PDF cannot change in the same PR as production code.
    """
    normalized = _normalize(path, git_path=git_path)
    if is_v2_truth_file(normalized, git_path=git_path) or normalized.startswith(_V2_ROOT):
        return True
    lowered = normalized.lower()
    return lowered.startswith(_SOURCE_PDF_ROOT) and PurePosixPath(lowered).suffix == ".pdf"


def is_production_code_file(path: str, *, git_path: bool = False) -> bool:
    normalized = _normalize(path, git_path=git_path)
    # Pytest loads every tests/**/conftest.py as executable collection policy.
    # Unlike ordinary test modules, it can skip or xfail source/signed checks,
    # so it is a release acceptance control when frozen truth also changes.
    if normalized.startswith("tests/") and PurePosixPath(normalized).name == "conftest.py":
        return True
    if normalized in _PYTEST_CONFIG_PATHS:
        return True
    if normalized.startswith(_PRODUCTION_EXCLUDED_PREFIXES):
        return False
    if _is_root_runtime_manifest(normalized):
        return True
    if normalized.startswith(_LOCAL_ACTION_ROOT):
        return True
    if normalized.startswith(_WORKFLOW_ROOT) and PurePosixPath(normalized).suffix.lower() in _WORKFLOW_SUFFIXES:
        return True
    return PurePosixPath(normalized).suffix.lower() in _PRODUCTION_SUFFIXES


def find_separation_violation(
    changed_paths: Sequence[str], *, git_path: bool = False,
) -> tuple[list[str], list[str]]:
    truth_files = sorted({
        p for p in changed_paths if is_benchmark_defining_file(p, git_path=git_path)
    })
    production_files = sorted({
        p for p in changed_paths if is_production_code_file(p, git_path=git_path)
    })
    if truth_files and production_files:
        return truth_files, production_files
    return [], []


def check_paths(changed_paths: Sequence[str], *, git_path: bool = False) -> None:
    truth_files, production_files = find_separation_violation(
        changed_paths, git_path=git_path,
    )
    if not truth_files:
        return
    raise SystemExit(
        "\n".join(
            [
                "Full Plan V2 truth / production separation gate failed.",
                "Source-closed V2 truth and production code must be changed in separate PRs.",
                "",
                "V2 truth / benchmark-defining / source-PDF files:",
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


def _stdin_paths_from_bytes(payload: bytes, *, require_nul: bool = False) -> list[str]:
    """Parse Git -z paths losslessly; preserve the legacy newline CLI for audits.

    Git's ordinary --name-only output C-quotes non-ASCII, tab and newline
    filenames, so splitting its text output can conceal a frozen V2 path.
    CI MUST pass --nul and git diff -z; reject malformed nonempty streams.
    """
    if not payload:
        return []
    if b"\x00" not in payload:
        if require_nul:
            raise ValueError("V2 separation requires NUL-delimited git diff -z paths")
        return _stdin_paths(payload.decode("utf-8").splitlines())
    if not payload.endswith(b"\x00"):
        raise ValueError("Incomplete NUL-delimited V2 changed-path stream")
    return [part.decode("utf-8") for part in payload.split(b"\x00")[:-1] if part]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--nul", action="store_true",
        help="require lossless NUL-delimited git diff -z input (mandatory in CI)",
    )
    args = parser.parse_args(argv)
    try:
        changed_paths = _stdin_paths_from_bytes(
            sys.stdin.buffer.read(), require_nul=args.nul,
        )
        check_paths(changed_paths, git_path=args.nul)
    except (ValueError, UnicodeError) as exc:
        print(f"Full Plan V2 truth / production separation input invalid: {exc}", file=sys.stderr)
        return 1
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("Full Plan V2 truth / production separation gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
