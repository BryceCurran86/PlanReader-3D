"""Negative and positive contract tests for the single Q5446 original resolver."""
from __future__ import annotations

import hashlib
from pathlib import Path
import pytest

from tools.gpt3_original_source_preflight import SOURCE_BLOCKED, SOURCE_MISMATCH, SOURCE_PRESENT
from tests.original_source_q5446 import (
    ORIGINAL_NAME,
    ORIGINAL_SHA256,
    PATH_ENV_VARS,
    POLICY_ENV,
    PUBLIC_CI_POLICY,
    require_original_q5446,
    resolve_original_q5446,
)

FAILED = pytest.fail.Exception
SKIPPED = pytest.skip.Exception
PAYLOAD = b"%PDF-1.4\nsynthetic stand-in, not the original Q5446\n"
PAYLOAD_SHA = hashlib.sha256(PAYLOAD).hexdigest()


def outcome(**kwargs) -> str:
    try:
        require_original_q5446(**kwargs)
        return "returned"
    except FAILED as exc:
        return f"failed: {exc}"
    except SKIPPED as exc:
        return f"skipped: {exc}"


def provisioned_root(tmp_path: Path, payload: bytes = PAYLOAD) -> Path:
    target = tmp_path / "repo" / "documents" / "sources"
    target.mkdir(parents=True)
    (target / ORIGINAL_NAME).write_bytes(payload)
    return tmp_path / "repo"


def empty_root(tmp_path: Path) -> Path:
    (tmp_path / "empty").mkdir(parents=True, exist_ok=True)
    return tmp_path / "empty"


def test_q5446_absent_original_without_public_policy_fails_visibly(tmp_path):
    got = outcome(env={}, repo_root=empty_root(tmp_path))
    assert got.startswith("failed: ORIGINAL_SOURCE_UNAVAILABLE"), got


def test_q5446_absent_original_under_public_policy_is_explicit_not_run(tmp_path):
    got = outcome(env={POLICY_ENV: PUBLIC_CI_POLICY}, repo_root=empty_root(tmp_path))
    assert got.startswith("skipped: ORIGINAL_SOURCE_NOT_RUN"), got
    assert "not an original-source pass" in got


def test_q5446_named_path_missing_always_fails(tmp_path):
    for variable in PATH_ENV_VARS:
        env = {POLICY_ENV: PUBLIC_CI_POLICY, variable: str(tmp_path / "nonexistent.pdf")}
        got = outcome(env=env, repo_root=provisioned_root(tmp_path / f"r_{variable}"), expected_sha256=PAYLOAD_SHA)
        assert got.startswith("failed: ORIGINAL_SOURCE_UNAVAILABLE"), got


def test_q5446_digest_mismatch_fails_visibly(tmp_path):
    root = provisioned_root(tmp_path, payload=b"corrupted bytes")
    got = outcome(env={}, repo_root=root, expected_sha256=PAYLOAD_SHA)
    assert got.startswith("failed: ORIGINAL_SOURCE_MISMATCH"), got


def test_q5446_matching_digest_returns_path(tmp_path):
    root = provisioned_root(tmp_path, payload=PAYLOAD)
    got = outcome(env={}, repo_root=root, expected_sha256=PAYLOAD_SHA)
    assert got == "returned"
