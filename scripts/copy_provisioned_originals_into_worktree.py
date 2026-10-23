"""Copy already-provisioned original PDFs into a historical git worktree.

The companion-source action writes into the GitHub workspace. Detached
worktrees of older commits do not contain those untracked files. This tool
copies named files only. It never fetches, downloads, or invents PDF bytes.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Sequence

SOURCE_BLOCKED = 2
ORIGINAL_PDF_ABSENT = "original_pdf_absent"


def copy_provisioned_originals_into_worktree(
    workspace_root: Path,
    worktree_root: Path,
    names: Sequence[str],
) -> None:
    if not isinstance(workspace_root, Path) or not isinstance(worktree_root, Path):
        raise TypeError("workspace_root and worktree_root must be Path")
    if not names:
        raise ValueError("at least one original name is required")
    src_dir = workspace_root / "documents" / "sources"
    dst_dir = worktree_root / "documents" / "sources"
    for name in names:
        if Path(name).name != name or "/" in name.replace("\\", "/"):
            raise ValueError(f"name must be a basename, got {name!r}")
        src = src_dir / name
        if not src.is_file():
            raise FileNotFoundError(src)
        dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst_dir / name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--name", action="append", required=True)
    args = parser.parse_args(argv)
    try:
        copy_provisioned_originals_into_worktree(args.workspace, args.worktree, args.name)
    except FileNotFoundError as exc:
        sys.stderr.write(f"SOURCE_BLOCKED {ORIGINAL_PDF_ABSENT} {exc}\n")
        return SOURCE_BLOCKED
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
