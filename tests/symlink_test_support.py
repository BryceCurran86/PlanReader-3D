"""Create a test symlink, skipping only when the OS refuses symlinks.

Symlink-attack tests need a real link in their setup. Windows without the
"Create symbolic links" privilege raises OSError winerror 1314
(ERROR_PRIVILEGE_NOT_HELD, errno EINVAL); filesystems without symlink support
raise EPERM/ENOTSUP/EOPNOTSUPP; a platform without ``os.symlink`` raises
NotImplementedError. Only those refusals become an explicit skip naming the OS
error. Every other error propagates, and every assertion after the link exists
runs unchanged wherever symlinks are allowed (Linux CI).
"""
from __future__ import annotations

import errno
import os

import pytest

_ERROR_PRIVILEGE_NOT_HELD = 1314
_REFUSED_ERRNOS = frozenset({errno.EPERM, errno.ENOTSUP, errno.EOPNOTSUPP})


def _os_refused_symlink(exc: BaseException) -> bool:
    if isinstance(exc, NotImplementedError):
        return True
    if getattr(exc, "winerror", None) == _ERROR_PRIVILEGE_NOT_HELD:
        return True
    return isinstance(exc, OSError) and exc.errno in _REFUSED_ERRNOS


def symlink_or_skip(link, target, *, target_is_directory: bool = False) -> None:
    """Make ``link`` point at ``target`` (``Path.symlink_to`` argument order)."""
    try:
        os.symlink(target, link, target_is_directory=target_is_directory)
    except (OSError, NotImplementedError) as exc:
        if not _os_refused_symlink(exc):
            raise
        pytest.skip(f"OS refused to create symlink {link}: {exc}")
