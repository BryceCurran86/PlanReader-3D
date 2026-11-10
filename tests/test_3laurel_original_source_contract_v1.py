"""Negative and positive contract tests for the single 3Laurel original resolver (no silent skip, no mismatch skip)."""
from __future__ import annotations

import ast
import hashlib
import os
from pathlib import Path

import pytest

from tools.gpt3_original_source_preflight import SOURCE_BLOCKED, SOURCE_MISMATCH, SOURCE_PRESENT
import tests.original_source_3laurel as src
from tests.original_source_3laurel import (
    ORIGINAL_NAME, ORIGINAL_SHA256, PATH_ENV_VARS, POLICY_ENV, PUBLIC_CI_POLICY, require_original_3laurel, resolve_original_3laurel,
)

FAILED = pytest.fail.Exception
SKIPPED = pytest.skip.Exception
PAYLOAD = b"%PDF-1.4\nsynthetic stand-in, not the original\n"
PAYLOAD_SHA = hashlib.sha256(PAYLOAD).hexdigest()


def outcome(**kwargs) -> str:
    """``returned``, ``failed: <text>`` or ``skipped: <text>``: a skip must never be mistaken for a failure or the reverse."""
    try:
        require_original_3laurel(**kwargs)
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
    (tmp_path / "empty").mkdir()
    return tmp_path / "empty"


# ------------------------------------------------------------------------------------------------ the original is absent
def test_absent_original_without_the_public_policy_fails_visibly(tmp_path):
    assert outcome(env={}, repo_root=empty_root(tmp_path)).startswith("failed: ORIGINAL_SOURCE_UNAVAILABLE")


def test_absent_original_under_the_public_policy_is_an_explicit_not_run_never_a_pass(tmp_path):
    text = outcome(env={POLICY_ENV: PUBLIC_CI_POLICY}, repo_root=empty_root(tmp_path))
    assert text.startswith("skipped: ORIGINAL_SOURCE_NOT_RUN") and "not an original-source pass" in text


def test_a_named_original_path_that_is_missing_always_fails_even_in_public_ci(tmp_path):
    for variable in PATH_ENV_VARS:
        env = {POLICY_ENV: PUBLIC_CI_POLICY, variable: str(tmp_path / "nowhere.pdf")}
        got = outcome(env=env, repo_root=provisioned_root(tmp_path / f"r{variable}"), expected_sha256=PAYLOAD_SHA)
        assert got.startswith("failed: ORIGINAL_SOURCE_UNAVAILABLE"), got


def test_a_named_path_never_falls_back_to_the_default_location(tmp_path):
    root = provisioned_root(tmp_path)                        # a good file at the default location
    env = {PATH_ENV_VARS[0]: str(tmp_path / "nowhere.pdf")}
    result = resolve_original_3laurel(env=env, repo_root=root, expected_sha256=PAYLOAD_SHA)
    assert result.status == SOURCE_BLOCKED and result.explicit and result.reason == src.REASON_EXPLICIT_PATH_ABSENT
    assert outcome(env=env, repo_root=root, expected_sha256=PAYLOAD_SHA).startswith("failed: ")


# ------------------------------------------------------------------------------------------------ the original is wrong
@pytest.mark.parametrize("policy", ["", PUBLIC_CI_POLICY])
def test_a_present_file_with_other_bytes_always_fails_and_is_never_skipped(tmp_path, policy):
    root = provisioned_root(tmp_path, payload=PAYLOAD + b"altered")
    env = {POLICY_ENV: policy} if policy else {}
    got = outcome(env=env, repo_root=root, expected_sha256=PAYLOAD_SHA)
    assert got.startswith("failed: ORIGINAL_SOURCE_MISMATCH") and "never skipped" in got


def test_a_wrong_file_at_a_named_path_fails_too(tmp_path):
    wrong = tmp_path / "wrong.pdf"
    wrong.write_bytes(b"%PDF-1.4\nsomething else\n")
    for variable in PATH_ENV_VARS:
        assert outcome(env={POLICY_ENV: PUBLIC_CI_POLICY, variable: str(wrong)}, expected_sha256=PAYLOAD_SHA).startswith("failed: ORIGINAL_SOURCE_MISMATCH")


def test_a_directory_is_never_an_original(tmp_path):
    folder = tmp_path / "root" / "documents" / "sources" / ORIGINAL_NAME
    folder.mkdir(parents=True)
    result = resolve_original_3laurel(env={}, repo_root=tmp_path / "root", expected_sha256=PAYLOAD_SHA)
    assert result.status == SOURCE_MISMATCH and result.reason == src.REASON_UNSAFE_PATH
    assert outcome(env={POLICY_ENV: PUBLIC_CI_POLICY}, repo_root=tmp_path / "root", expected_sha256=PAYLOAD_SHA).startswith("failed: ORIGINAL_SOURCE_MISMATCH")


def test_a_symlink_is_never_an_original(tmp_path):
    good = tmp_path / "good.pdf"
    good.write_bytes(PAYLOAD)
    link = tmp_path / "link.pdf"
    try:
        os.symlink(good, link)
    except (OSError, NotImplementedError):
        pytest.skip("SYMLINK_UNSUPPORTED: this platform or account cannot create a symlink (not an original-source test)")
    result = resolve_original_3laurel(env={PATH_ENV_VARS[0]: str(link)}, expected_sha256=PAYLOAD_SHA)
    assert result.status == SOURCE_MISMATCH and result.reason == src.REASON_UNSAFE_PATH
    dangling = tmp_path / "dangling.pdf"
    os.symlink(tmp_path / "nowhere.pdf", dangling)
    assert resolve_original_3laurel(env={PATH_ENV_VARS[0]: str(dangling)}, expected_sha256=PAYLOAD_SHA).status == SOURCE_MISMATCH


def _stat_like(mode: int) -> os.stat_result:
    return os.stat_result((mode, 1, 1, 1, 0, 0, 10, 0, 0, 0))


def test_a_non_regular_file_mode_is_refused_even_when_the_bytes_would_match(tmp_path, monkeypatch):
    good = tmp_path / "good.pdf"
    good.write_bytes(PAYLOAD)
    real_lstat = Path.lstat
    monkeypatch.setattr(Path, "lstat", lambda self, *a, **k: _stat_like(0o120777) if self == good else real_lstat(self, *a, **k))   # S_IFLNK
    result = resolve_original_3laurel(env={PATH_ENV_VARS[0]: str(good)}, expected_sha256=PAYLOAD_SHA)
    assert result.status == SOURCE_MISMATCH and result.reason == src.REASON_UNSAFE_PATH and result.original_source_verified is False


def test_an_unreadable_path_is_a_failure_never_an_absence(tmp_path, monkeypatch):
    good = tmp_path / "good.pdf"
    good.write_bytes(PAYLOAD)
    real_lstat, real_read = Path.lstat, Path.read_bytes

    def denied_lstat(self, *a, **k):
        if self == good:
            raise PermissionError("denied")
        return real_lstat(self, *a, **k)
    monkeypatch.setattr(Path, "lstat", denied_lstat)
    result = resolve_original_3laurel(env={PATH_ENV_VARS[0]: str(good)}, expected_sha256=PAYLOAD_SHA)
    assert result.status == SOURCE_MISMATCH and result.reason == src.REASON_UNSAFE_PATH
    monkeypatch.setattr(Path, "lstat", real_lstat)

    def denied_read(self, *a, **k):
        if self == good:
            raise PermissionError("denied")
        return real_read(self, *a, **k)
    monkeypatch.setattr(Path, "read_bytes", denied_read)
    result = resolve_original_3laurel(env={PATH_ENV_VARS[0]: str(good)}, expected_sha256=PAYLOAD_SHA)
    assert result.status == SOURCE_MISMATCH and result.reason == src.REASON_UNSAFE_PATH
    assert outcome(env={POLICY_ENV: PUBLIC_CI_POLICY, PATH_ENV_VARS[0]: str(good)}, expected_sha256=PAYLOAD_SHA).startswith("failed: ORIGINAL_SOURCE_MISMATCH")


def test_the_default_root_is_the_repository_not_the_current_directory(tmp_path, monkeypatch):
    (tmp_path / "documents" / "sources").mkdir(parents=True)
    (tmp_path / "documents" / "sources" / ORIGINAL_NAME).write_bytes(PAYLOAD)
    monkeypatch.chdir(tmp_path)
    # no repo_root given: a good file in the current directory must not be picked up
    assert resolve_original_3laurel(env={}, expected_sha256=PAYLOAD_SHA).status != SOURCE_PRESENT


def test_an_unknown_policy_value_fails():
    for bad in ("skip", "SKIP_MISSING_IN_PUBLIC_CI", "true", " "):
        assert outcome(env={POLICY_ENV: bad}) == "failed: invalid_private_original_source_ci_policy"


# ------------------------------------------------------------------------------------------------ the original is present
def test_a_verified_original_is_returned_in_every_mode(tmp_path):
    root = provisioned_root(tmp_path)
    for env in ({}, {POLICY_ENV: PUBLIC_CI_POLICY}):
        path = require_original_3laurel(env=env, repo_root=root, expected_sha256=PAYLOAD_SHA)
        assert path == root / "documents" / "sources" / ORIGINAL_NAME
    result = resolve_original_3laurel(env={}, repo_root=root, expected_sha256=PAYLOAD_SHA)
    assert result.status == SOURCE_PRESENT and result.original_source_verified is True and result.reason == src.REASON_MATCH


def test_a_named_path_is_used_and_the_first_variable_wins(tmp_path):
    first, second = tmp_path / "first.pdf", tmp_path / "second.pdf"
    first.write_bytes(PAYLOAD)
    second.write_bytes(b"%PDF-1.4\nother\n")
    env = {PATH_ENV_VARS[0]: str(first), PATH_ENV_VARS[1]: str(second)}
    assert require_original_3laurel(env=env, expected_sha256=PAYLOAD_SHA) == first
    assert require_original_3laurel(env={PATH_ENV_VARS[1]: str(first)}, expected_sha256=PAYLOAD_SHA) == first     # the legacy name still works
    assert outcome(env={PATH_ENV_VARS[0]: str(second), PATH_ENV_VARS[1]: str(first)}, expected_sha256=PAYLOAD_SHA).startswith("failed: ORIGINAL_SOURCE_MISMATCH")


def test_the_default_location_is_under_the_repository_root_not_the_working_directory(tmp_path, monkeypatch):
    elsewhere = tmp_path / "cwd"
    (elsewhere / "documents" / "sources").mkdir(parents=True)
    (elsewhere / "documents" / "sources" / ORIGINAL_NAME).write_bytes(PAYLOAD)     # a good file in the cwd only
    monkeypatch.chdir(elsewhere)
    result = resolve_original_3laurel(env={}, repo_root=empty_root(tmp_path), expected_sha256=PAYLOAD_SHA)
    assert result.status == SOURCE_BLOCKED and result.original_source_verified is False
    root = provisioned_root(tmp_path / "other")
    assert resolve_original_3laurel(env={}, repo_root=root, expected_sha256=PAYLOAD_SHA).status == SOURCE_PRESENT


def test_the_resolver_never_claims_verification_without_a_matching_digest(tmp_path):
    for root, expected in ((empty_root(tmp_path), PAYLOAD_SHA), (provisioned_root(tmp_path / "bad", PAYLOAD + b"x"), PAYLOAD_SHA)):
        assert resolve_original_3laurel(env={}, repo_root=root, expected_sha256=expected).original_source_verified is False


def test_the_frozen_hash_matches_the_manifest():
    import json
    manifest = json.loads(Path("benchmarks/frozen_holdout/full_plan_v2/projects/au_qld_3laurel/source_manifest.json").read_text(encoding="utf-8"))
    (document,) = manifest["source_documents"]
    assert document["sha256"] == ORIGINAL_SHA256 and document["name"] == ORIGINAL_NAME


# ------------------------------------------------------------------------------------------------ nobody else skips on the original
def _skip_calls(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "skip" \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "pytest":
            yield node


def test_no_test_that_reads_the_3laurel_original_skips_for_it_on_its_own():
    here = Path(__file__).resolve().parent
    offenders = []
    for path in sorted(here.rglob("*.py")):
        if path.name in {"original_source_3laurel.py", Path(__file__).name}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if ORIGINAL_SHA256 not in text and ORIGINAL_NAME not in text and "THREELAUREL_ARCH_ORIGINAL" not in text:
            continue
        for call in _skip_calls(ast.parse(text)):
            message = " ".join(str(getattr(a, "value", "")) for a in ast.walk(call) if isinstance(a, ast.Constant)).lower()
            if "original" in message or "private" in message or "source" in message:
                offenders.append(f"{path.name}:{call.lineno}")
    assert offenders == [], offenders


def test_the_four_formerly_silent_tests_use_the_resolver():
    names = ("test_antigravity_3laurel_host_binding.py", "test_gpt1_original_3laurel_asw_candidates.py",
             "test_gptmax_native_filled_scale_shadow.py", "test_elevation_door_vertical_witness_shadow_v1.py")
    here = Path(__file__).resolve().parent
    for name in names:
        assert "require_original_3laurel" in (here / name).read_text(encoding="utf-8"), name
