"""Classify private GPT2 offline pytest failures without disclosing source text.

A classification is a NON-AUTHORITATIVE release diagnostic, never an original
source proof, a geometry result, or a FIRM construction quantity. Arbitrary
pytest/Docker output is untrusted: this module emits only literal reason codes.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re

# A deliberate, closed public vocabulary. Do not include log fragments,
# source filenames, assertions, exception messages or exception arguments.
CONTAINER_START_FAILURE = "gpt2_container_start_failure"
CONTAINER_EXEC_FAILURE = "gpt2_container_exec_failure"
SOURCE_MOUNT_INACCESSIBLE = "gpt2_source_mount_inaccessible"
DEPENDENCY_IMPORT_FAILURE = "gpt2_dependency_import_failure"
PYTEST_COLLECTION_FAILURE = "gpt2_pytest_collection_or_config_failure"
SOURCE_TEST_ASSERTION_FAILURE = "gpt2_source_test_assertion_failure"
UNCLASSIFIED_FAILURE = "gpt2_isolated_source_test_failure_unclassified"
NO_FAILURE = "gpt2_no_failure_classified"

PUBLIC_REASON_CODES = frozenset({
    CONTAINER_START_FAILURE, CONTAINER_EXEC_FAILURE,
    SOURCE_MOUNT_INACCESSIBLE, DEPENDENCY_IMPORT_FAILURE,
    PYTEST_COLLECTION_FAILURE, SOURCE_TEST_ASSERTION_FAILURE,
    UNCLASSIFIED_FAILURE, NO_FAILURE,
})

# Patterns are only classification hints. A malicious test can deliberately
# print matching text, so no pattern ever grants source/FIRM/score authority.
_SOURCE_ACCESS = re.compile(
    r"(?:FileNotFoundError|PermissionError|Errno\s*(?:2|13))"
    r".{0,320}(?:documents/sources|PLANREADER_MARYBOROUGH_ORIGINAL_PDF)",
    re.IGNORECASE | re.DOTALL,
)
_MISSING_IMPORT = re.compile(
    r"(?:ModuleNotFoundError|ImportError|No module named|"
    r"cannot import name|undefined symbol)",
    re.IGNORECASE,
)
_PYTEST_USAGE = re.compile(
    r"(?:ERROR collecting |ERROR: not found:|pytest: error:|"
    r"unrecognized arguments:|no tests ran|collected 0 items)",
    re.IGNORECASE,
)
_ASSERTION = re.compile(
    r"(?:^FAILED\s+|^E\s+AssertionError|"
    r"\b[1-9][0-9]* failed\b|\bAssertionError\b)",
    re.IGNORECASE | re.MULTILINE,
)


def classify_private_failure(process_exit_code: int, private_log: str) -> str:
    """Return one safe literal diagnostic category, never the private log.

    Exit 125, 126, 127 refer to Docker transport/runtime, not pytest.
    Non-Docker failures are best-effort hints; all remain release-blocking.
    """
    if type(process_exit_code) is not int or process_exit_code < 0:
        raise ValueError("invalid process exit code")
    if type(private_log) is not str:
        raise TypeError("private log must be text")
    if process_exit_code == 0:
        return NO_FAILURE
    if process_exit_code == 125:
        return CONTAINER_START_FAILURE
    if process_exit_code in (126, 127):
        return CONTAINER_EXEC_FAILURE
    # Bounded analysis; never allocate a large attacker-controlled line.
    observed = private_log[-2_000_000:]
    if _SOURCE_ACCESS.search(observed):
        return SOURCE_MOUNT_INACCESSIBLE
    if _MISSING_IMPORT.search(observed):
        return DEPENDENCY_IMPORT_FAILURE
    if _PYTEST_USAGE.search(observed):
        return PYTEST_COLLECTION_FAILURE
    if _ASSERTION.search(observed):
        return SOURCE_TEST_ASSERTION_FAILURE
    return UNCLASSIFIED_FAILURE


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit safe GPT2 offline failure code")
    parser.add_argument("--private-log", type=Path, required=True)
    parser.add_argument("--exit-code", type=int, required=True)
    args = parser.parse_args(argv)
    # No stack traces or private text are written by this CLI, even on an
    # unreadable/missing private log. Do not interpolate exception details.
    try:
        raw = args.private_log.read_text(encoding="utf-8", errors="replace")
        result = classify_private_failure(args.exit_code, raw)
    except (OSError, ValueError, TypeError):
        result = UNCLASSIFIED_FAILURE
    assert result in PUBLIC_REASON_CODES
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
