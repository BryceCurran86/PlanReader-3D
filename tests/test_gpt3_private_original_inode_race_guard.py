"""Fail-closed original-byte source guard against worktree inode substitution.

Synthetic files only. No client PDF, frozen gold, secrets or quantity issuer.
"""
from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path

import pytest

from scripts import check_private_original_source_additions as guard


_BYTES = b"synthetic confidential-original fixture; not a customer drawing"


def _pinned():
    return guard.PinnedOriginals(
        names=frozenset({"named_original.pdf"}),
        sha256_by_size={len(_BYTES): frozenset({sha256(_BYTES).hexdigest()})},
    )


def test_unchanged_regular_original_bytes_still_blocked(tmp_path):
    source = tmp_path / "renamed.pdf"
    source.write_bytes(_BYTES)
    assert guard._is_pinned_original_bytes(source, _pinned()) is True
    assert guard.blocked_source_additions(
        ["renamed.pdf"], pinned=_pinned(), root=tmp_path, git_path=True,
    ) == ("renamed.pdf",)


def test_different_bytes_or_absent_path_do_not_masquerade_as_original(tmp_path):
    source = tmp_path / "renamed.pdf"
    source.write_bytes(b"public synthetic sample of the same length plus padding")
    assert guard._is_pinned_original_bytes(source, _pinned()) is False
    assert guard._is_pinned_original_bytes(tmp_path / "missing.pdf", _pinned()) is False


def test_initial_symlink_is_not_followed(tmp_path):
    source = tmp_path / "renamed.pdf"
    target = tmp_path / "target.pdf"
    target.write_bytes(_BYTES)
    try:
        source.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("runner cannot create symlinks")
    assert guard._is_pinned_original_bytes(source, _pinned()) is False


def test_same_byte_different_inode_swap_during_size_to_hash_fails_closed(
    tmp_path, monkeypatch,
):
    source = tmp_path / "renamed.pdf"
    source.write_bytes(_BYTES)
    original_hash = guard._file_sha256

    def swap_before_hash(path: Path):
        replacement = tmp_path / "replacement"
        replacement.write_bytes(_BYTES)  # Equal content, different inode.
        os.replace(replacement, source)
        return original_hash(path)

    monkeypatch.setattr(guard, "_file_sha256", swap_before_hash)
    with pytest.raises(ValueError, match="changed source file identity"):
        guard.source_addition_findings(
            ["renamed.pdf"], pinned=_pinned(), root=tmp_path, git_path=True,
        )


def test_symlink_swap_after_size_check_cannot_follow_original(tmp_path, monkeypatch):
    if not hasattr(os, "O_NOFOLLOW"):
        pytest.skip("no-follow flag unavailable")
    source = tmp_path / "renamed.pdf"
    target = tmp_path / "target.pdf"
    source.write_bytes(_BYTES)
    target.write_bytes(_BYTES)
    original_hash = guard._file_sha256

    def switch_to_symlink(path: Path):
        source.unlink()
        source.symlink_to(target)
        return original_hash(path)

    monkeypatch.setattr(guard, "_file_sha256", switch_to_symlink)
    with pytest.raises(ValueError, match="changed source file identity"):
        guard._is_pinned_original_bytes(source, _pinned())


def test_swap_between_path_lstat_and_descriptor_open_fails_closed(tmp_path, monkeypatch):
    source = tmp_path / "renamed.pdf"
    source.write_bytes(_BYTES)
    original_open = os.open
    changed = False

    def replace_at_open(path, flags, *args, **kwargs):
        nonlocal changed
        if Path(path) == source and not changed:
            changed = True
            replacement = tmp_path / "replacement"
            replacement.write_bytes(b"Z" * len(_BYTES))
            os.replace(replacement, source)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(guard.os, "open", replace_at_open)
    with pytest.raises(ValueError, match="changed source file identity"):
        guard._is_pinned_original_bytes(source, _pinned())
    assert changed


def test_disappearing_regular_worktree_file_fails_closed(tmp_path, monkeypatch):
    source = tmp_path / "renamed.pdf"
    source.write_bytes(_BYTES)
    original_hash = guard._file_sha256

    def disappear(path: Path):
        source.unlink()
        return original_hash(path)

    monkeypatch.setattr(guard, "_file_sha256", disappear)
    with pytest.raises(ValueError, match="changed source file identity"):
        guard._is_pinned_original_bytes(source, _pinned())
