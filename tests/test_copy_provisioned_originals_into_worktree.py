"""Provisioned originals copy into worktrees; missing files stay SOURCE_BLOCKED."""
from __future__ import annotations

from pathlib import Path

from scripts.copy_provisioned_originals_into_worktree import (
    SOURCE_BLOCKED,
    copy_provisioned_originals_into_worktree,
    main,
)

NAME = "1. Construction Plans - Lot 16 Power (REV E).pdf"


def test_missing_workspace_original_is_source_blocked(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    worktree = tmp_path / "worktree"
    (workspace / "documents" / "sources").mkdir(parents=True)
    worktree.mkdir()
    try:
        copy_provisioned_originals_into_worktree(workspace, worktree, [NAME])
        raise AssertionError("missing original must not copy")
    except FileNotFoundError:
        pass
    assert main(["--workspace", str(workspace), "--worktree", str(worktree), "--name", NAME]) == SOURCE_BLOCKED


def test_named_original_is_copied_bytes_identical(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    worktree = tmp_path / "worktree"
    src_dir = workspace / "documents" / "sources"
    src_dir.mkdir(parents=True)
    worktree.mkdir()
    payload = b"%PDF-1.4 provisioned-original"
    (src_dir / NAME).write_bytes(payload)
    assert main(["--workspace", str(workspace), "--worktree", str(worktree), "--name", NAME]) == 0
    copied = worktree / "documents" / "sources" / NAME
    assert copied.read_bytes() == payload


def test_path_separator_in_name_is_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    worktree = tmp_path / "worktree"
    workspace.mkdir()
    worktree.mkdir()
    try:
        copy_provisioned_originals_into_worktree(workspace, worktree, ["subdir/" + NAME])
    except ValueError:
        return
    raise AssertionError("path-shaped names must be rejected")
