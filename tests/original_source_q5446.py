"""One resolver for the private Q5446 original in tests: never a silent skip, never a hash-mismatch skip.
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

ORIGINAL_NAME = "Q5446_Standard_Plans_V1_20220320.pdf"
ORIGINAL_SHA256 = "5f29aa0122d72e2cc8886b3f19239ff32865c8d705eee99f785c389ca27fb7f0"
PATH_ENV_VARS = (
    "PLANREADER_Q5446_ORIGINAL_PDF",
    "Q5446_ARCH_ORIGINAL",
    "PLANREADER_ORIGINAL_Q5446_STANDARD_PLANS",
)
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
    if not S_ISREG(mode):
        return OriginalSource(SOURCE_MISMATCH, REASON_UNSAFE_PATH, path, explicit)
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return OriginalSource(SOURCE_MISMATCH, REASON_UNSAFE_PATH, path, explicit)
    if digest != expected_sha256:
        return OriginalSource(SOURCE_MISMATCH, REASON_DIGEST_MISMATCH, path, explicit)
    return OriginalSource(SOURCE_PRESENT, REASON_MATCH, path, explicit, original_source_verified=True)


def resolve_original_q5446(
    *, env: Optional[Mapping[str, str]] = None, repo_root: Optional[Path] = None, expected_sha256: str = ORIGINAL_SHA256,
) -> OriginalSource:
    """Classify the original without raising and without reading anything but one file's bytes."""
    env = os.environ if env is None else env
    for variable in PATH_ENV_VARS:
        value = str(env.get(variable, "")).strip()
        if value:
            return _classify(Path(value), expected_sha256, explicit=True)
    if repo_root is not None:
        primary = Path(repo_root) / "documents" / "sources" / ORIGINAL_NAME
        return _classify(primary, expected_sha256, explicit=False)

    root = _repo_root()
    primary = root / "documents" / "sources" / ORIGINAL_NAME
    if primary.is_file():
        return _classify(primary, expected_sha256, explicit=False)

    candidate_paths = (
        Path.home() / "OneDrive" / "Desktop" / "documents" / "sources" / "Q5446" / ORIGINAL_NAME,
        Path.home() / "OneDrive" / "Desktop" / "documents" / "sources" / ORIGINAL_NAME,
        Path.home() / "Downloads" / "PlanReader_verified_private_sources" / "documents" / "sources" / ORIGINAL_NAME,
        Path.home() / "Downloads" / "PlanReader_All_Four_10GB_PRIVATE_READY_TO_RUN" / "sources" / "au_qld_q5446_armstrong32_harlequin" / ORIGINAL_NAME,
    )
    for candidate in candidate_paths:
        if candidate.is_file():
            return _classify(candidate, expected_sha256, explicit=False)

    return _classify(primary, expected_sha256, explicit=False)


def require_original_q5446(
    *, env: Optional[Mapping[str, str]] = None, repo_root: Optional[Path] = None, expected_sha256: str = ORIGINAL_SHA256,
) -> Path:
    """The verified original's path, or a visible failure/NOT_RUN skip as described in the module contract."""
    env = os.environ if env is None else env
    policy = str(env.get(POLICY_ENV, ""))
    if policy not in ("", PUBLIC_CI_POLICY):
        pytest.fail("invalid_private_original_source_ci_policy", pytrace=False)
    source = resolve_original_q5446(env=env, repo_root=repo_root, expected_sha256=expected_sha256)
    if source.status == SOURCE_PRESENT:
        assert source.path is not None
        return source.path
    if source.status == SOURCE_MISMATCH:
        pytest.fail(f"ORIGINAL_SOURCE_MISMATCH: {source.reason}; a wrong or altered original is never skipped", pytrace=False)
    if policy == PUBLIC_CI_POLICY and not source.explicit:
        pytest.skip("ORIGINAL_SOURCE_NOT_RUN: private Q5446 original not provisioned; this is not an original-source pass")
    pytest.fail(f"ORIGINAL_SOURCE_UNAVAILABLE: {source.reason}; an original-source test must not pass or skip without the original",
                pytrace=False)


__all__ = [
    "ORIGINAL_NAME", "ORIGINAL_SHA256", "OriginalSource", "PATH_ENV_VARS", "POLICY_ENV", "PUBLIC_CI_POLICY",
    "require_original_q5446", "resolve_original_q5446",
]
