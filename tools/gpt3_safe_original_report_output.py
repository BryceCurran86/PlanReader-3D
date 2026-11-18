"""Create-only original-source diagnostic publication.

A source-authenticated report is never permission to overwrite another report,
customer output, sealed run, source PDF or frozen benchmark file. Keep all
existing bytes unchanged, including in a competing-writer race.
"""
from __future__ import annotations

import os
from pathlib import Path
from stat import S_ISREG
import sys
import tempfile
from typing import Callable, Iterable


def preflight_new_diagnostic(
    output: Path, *, protected_roots: Iterable[Path | None],
) -> None:
    """Reject ambiguous output ownership before original PDFs are read."""
    if not isinstance(output, Path):
        raise TypeError("diagnostic output must be a Path")
    destination = output.resolve()
    if output.is_symlink():
        raise FileExistsError("original-source diagnostic output must be a new path")
    if not output.name or output.name in (".", ".."):
        raise ValueError("original-source diagnostic output name is missing")
    for root in protected_roots:
        if root is None:
            continue
        source = Path(root).resolve()
        if destination == source or destination.is_relative_to(source):
            raise ValueError("original-source diagnostic may not overwrite protected evidence")
    if output.exists():
        raise FileExistsError("original-source diagnostic output must be a new path")



def publish_staged_file(staged_path: Path, output: Path) -> None:
    """Publish a complete same-directory file without replacing a destination."""
    if os.name == "nt":
        os.rename(staged_path, output)
    else:
        os.link(staged_path, output)


def _assert_published_report_unchanged(
    output: Path, staged_path: Path | None, staged: os.stat_result, expected_bytes: bytes,
) -> None:
    """Bind the published path, opened descriptor and bytes to one stable inode.

    A separate samefile() followed by Path.read_bytes() permits a same-byte
    path replacement between those operations to masquerade as our report.
    Do not follow a raced symlink or trust a byte match from another inode.

    Windows can report different ctime values via path and handle APIs for
    the same unchanged NTFS file. Keep each API's ctime stable independently;
    all other identity/content fields must still agree across both APIs.
    POSIX also retains cross-API ctime equality.
    """
    fields = ("st_dev", "st_ino", "st_mode", "st_nlink",
              "st_size", "st_mtime_ns")
    try:
        before = output.lstat()
        if not S_ISREG(staged.st_mode) or not S_ISREG(before.st_mode):
            raise ValueError("original-source diagnostic output changed during publication")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        with os.fdopen(os.open(output, flags), "rb") as stream:
            opened = os.fstat(stream.fileno())
            if not S_ISREG(opened.st_mode):
                raise ValueError("original-source diagnostic output changed during publication")
            actual = stream.read(len(expected_bytes) + 1)
            completed = os.fstat(stream.fileno())
        after = output.lstat()
        path_snapshots = (before, after)
        if staged_path is not None:
            path_snapshots += (staged_path.lstat(),)
    except OSError as exc:
        raise ValueError("original-source diagnostic output changed during publication") from exc
    stable_path_ctime = all(
        snapshot.st_ctime_ns == staged.st_ctime_ns
        for snapshot in path_snapshots
    )
    stable_descriptor_ctime = opened.st_ctime_ns == completed.st_ctime_ns
    comparable_ctime = (
        sys.platform == "win32" or opened.st_ctime_ns == staged.st_ctime_ns
    )
    if not staged.st_ino or actual != expected_bytes or not (
        stable_path_ctime and stable_descriptor_ctime and comparable_ctime
    ) or any(
        getattr(snapshot, field) != getattr(staged, field)
        for snapshot in (*path_snapshots, opened, completed)
        for field in fields
    ):
        raise ValueError("original-source diagnostic output changed during publication")


def write_new_diagnostic(
    output: Path, encoded: str, *, protected_roots: Iterable[Path | None],
    verify_inputs: Callable[[], None] | None = None,
) -> None:
    """Stage and fsync the report before create-only publication.

    A competing writer may claim the target after preflight. Publication
    preserves that target and no private document bytes are copied to it.
    """
    protected = tuple(protected_roots)
    preflight_new_diagnostic(output, protected_roots=protected)
    if type(encoded) is not str:
        raise TypeError("diagnostic payload must be a Unicode string")
    output.parent.mkdir(parents=True, exist_ok=True)
    temp: Path | None = None
    staged: os.stat_result | None = None
    our_output_created = False
    try:
        with tempfile.NamedTemporaryFile(
            "w", dir=output.parent, encoding="utf-8", newline="\n",
            prefix=".gpt3-original-report-", suffix=".tmp", delete=False,
        ) as stream:
            temp = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        preflight_new_diagnostic(output, protected_roots=protected)
        # Exact source/customer/frozen-input receipts must remain stable
        # through output staging, not just while the report was calculated.
        if verify_inputs is not None:
            verify_inputs()
        staged = temp.lstat()
        if not S_ISREG(staged.st_mode) or not staged.st_ino:
            raise ValueError("original-source diagnostic output changed during publication")
        publish_staged_file(temp, output)
        our_output_created = True
        # POSIX hard-link publication changes the original link count and
        # ctime. Windows rename leaves no staging path to re-stat.
        staged_path = None if os.name == "nt" else temp
        if staged_path is not None:
            published_stage = staged_path.lstat()
            if not os.path.samestat(staged, published_stage):
                raise ValueError("original-source diagnostic staging identity changed")
            staged = published_stage
        if verify_inputs is not None:
            verify_inputs()
        # Attest path identity and exact bytes through the SAME no-follow
        # descriptor; two independent path operations can accept a same-byte
        # replacement between their identity and content checks.
        _assert_published_report_unchanged(output, staged_path, staged, encoded.encode("utf-8"))
    except BaseException:
        if our_output_created and staged is not None:
            # A different output inode belongs to the competing writer.
            try:
                still_ours = os.path.samestat(output.lstat(), staged)
            except OSError:
                still_ours = False
            if still_ours:
                output.unlink(missing_ok=True)
        raise
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
