"""One resolver for the private 3Laurel original in tests: never a silent skip, never a hash-mismatch skip.

Contract (owner priority 2026-11-10, #4135 comment 6759058490):

* The original is found at ``PLANREADER_3LAUREL_ORIGINAL_PDF`` (or the legacy ``THREELAUREL_ARCH_ORIGINAL``), else at
  ``documents/sources/<name>`` under the repository root (never relative to the current directory).
* ``SOURCE_PRESENT``: a regular, non-symlink file whose SHA-256 equals the frozen manifest hash. The test runs.
* ``SOURCE_MISMATCH`` (a file exists with other bytes, or the path is not a plain regular file): the test FAILS in every
  mode. A wrong or altered original is an error, never a skip and never NOT_RUN.
* ``SOURCE_BLOCKED`` (nothing at the default path, or at an explicitly named path): under the public policy
  ``PLANREADER_PRIVATE_ORIGINAL_POLICY=skip_missing_in_public_ci`` the test is skipped with an explicit
  ``ORIGINAL_SOURCE_NOT_RUN`` reason that says it is not an original-source pass; in any other mode (the protected
  original-SHA workflows never set the policy) it FAILS. An explicitly named path that is missing always FAILS: naming a
  path says the original was meant to be provisioned.
* An unknown policy value fails.

The statuses are the ones of ``tools.gpt3_original_source_preflight`` (SOURCE_PRESENT, SOURCE_BLOCKED, SOURCE_MISMATCH).
The digest here is a plain read of one regular file: the preflight's stable-inode check compares ``lstat`` with ``fstat``
and reports a false change on Windows, so it cannot gate a local run.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from stat import S_ISREG
from typing import Mapping, Optional

import pytest

from tools.gpt3_original_source_preflight import SOURCE_BLOCKED, SOURCE_MISMATCH, SOURCE_PRESENT

ORIGINAL_NAME = "3LAUREL - Construction Plan Set Rev3 08.05.26.pdf"
ORIGINAL_SHA256 = "014e9f68b377bef4fb556de61b83a94388792dfa4bfb8ea981644f9c323e9e2e"
PATH_ENV_VARS = ("PLANREADER_3LAUREL_ORIGINAL_PDF", "THREELAUREL_ARCH_ORIGINAL")
POLICY_ENV = "PLANREADER_PRIVATE_ORIGINAL_POLICY"
PUBLIC_CI_POLICY = "skip_missing_in_public_ci"

REASON_ABSENT = "original_pdf_absent"
REASON_EXPLICIT_PATH_ABSENT = "explicit_original_path_absent"
REASON_DIGEST_MISMATCH = "original_pdf_digest_mismatch"
REASON_UNSAFE_PATH = "original_path_not_a_plain_regular_file"
REASON_MATCH = "original_pdf_digest_matches"


@dataclass(frozen=True)
class OriginalSource:
    status: str
    reason: str
    path: Optional[Path]
    explicit: bool
    original_source_verified: bool = False


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _classify(path: Path, expected_sha256: str, *, explicit: bool) -> OriginalSource:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return OriginalSource(SOURCE_BLOCKED, REASON_EXPLICIT_PATH_ABSENT if explicit else REASON_ABSENT, path, explicit)
    except OSError:
        return OriginalSource(SOURCE_MISMATCH, REASON_UNSAFE_PATH, path, explicit)
    if not S_ISREG(mode):                                  # a symlink, a directory or a device is never an original
        return OriginalSource(SOURCE_MISMATCH, REASON_UNSAFE_PATH, path, explicit)
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return OriginalSource(SOURCE_MISMATCH, REASON_UNSAFE_PATH, path, explicit)
    if digest != expected_sha256:
        return OriginalSource(SOURCE_MISMATCH, REASON_DIGEST_MISMATCH, path, explicit)
    return OriginalSource(SOURCE_PRESENT, REASON_MATCH, path, explicit, original_source_verified=True)


def resolve_original_3laurel(
    *, env: Optional[Mapping[str, str]] = None, repo_root: Optional[Path] = None, expected_sha256: str = ORIGINAL_SHA256,
) -> OriginalSource:
    """Classify the original without raising and without reading anything but one file's bytes."""
    env = os.environ if env is None else env
    for variable in PATH_ENV_VARS:
        value = str(env.get(variable, "")).strip()
        if value:
            return _classify(Path(value), expected_sha256, explicit=True)       # a named path is the only candidate
    root = _repo_root() if repo_root is None else Path(repo_root)
    return _classify(root / "documents" / "sources" / ORIGINAL_NAME, expected_sha256, explicit=False)


def require_original_3laurel(
    *, env: Optional[Mapping[str, str]] = None, repo_root: Optional[Path] = None, expected_sha256: str = ORIGINAL_SHA256,
) -> Path:
    """The verified original's path, or a visible failure/NOT_RUN skip as described in the module contract."""
    env = os.environ if env is None else env
    policy = str(env.get(POLICY_ENV, ""))
    if policy not in ("", PUBLIC_CI_POLICY):
        pytest.fail("invalid_private_original_source_ci_policy", pytrace=False)
    source = resolve_original_3laurel(env=env, repo_root=repo_root, expected_sha256=expected_sha256)
    if source.status == SOURCE_PRESENT:
        assert source.path is not None
        return source.path
    if source.status == SOURCE_MISMATCH:
        pytest.fail(f"ORIGINAL_SOURCE_MISMATCH: {source.reason}; a wrong or altered original is never skipped", pytrace=False)
    if policy == PUBLIC_CI_POLICY and not source.explicit:
        pytest.skip("ORIGINAL_SOURCE_NOT_RUN: private 3Laurel original not provisioned; this is not an original-source pass")
    pytest.fail(f"ORIGINAL_SOURCE_UNAVAILABLE: {source.reason}; an original-source test must not pass or skip without the original",
                pytrace=False)


__all__ = [
    "ORIGINAL_NAME", "ORIGINAL_SHA256", "OriginalSource", "PATH_ENV_VARS", "POLICY_ENV", "PUBLIC_CI_POLICY",
    "require_original_3laurel", "resolve_original_3laurel",
]
