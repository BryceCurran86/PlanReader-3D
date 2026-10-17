"""The symlink helper skips only when the OS refuses to create a symlink.

Every other error must propagate, so a symlink-attack test can never pass
silently because its setup broke for an unrelated reason.
"""
from __future__ import annotations

import errno
import os

import pytest

from tests.symlink_test_support import symlink_or_skip


def _refusing_symlink(exc):
    def _symlink(*_args, **_kwargs):
        raise exc
    return _symlink


def _windows_privilege_not_held():
    # Shape of the real error on Windows without the symlink privilege:
    # errno EINVAL, winerror 1314 (ERROR_PRIVILEGE_NOT_HELD).
    exc = OSError(errno.EINVAL, "A required privilege is not held by the client")
    exc.winerror = 1314
    return exc


@pytest.mark.parametrize("make_exc", [
    _windows_privilege_not_held,
    lambda: PermissionError(errno.EPERM, "Operation not permitted"),
    lambda: OSError(errno.ENOTSUP, "Operation not supported"),
    lambda: OSError(errno.EOPNOTSUPP, "Operation not supported on socket"),
    lambda: NotImplementedError("symlink unavailable on this platform"),
], ids=["winerror_1314", "EPERM", "ENOTSUP", "EOPNOTSUPP", "not_implemented"])
def test_os_refusal_skips_with_the_os_error_as_reason(tmp_path, monkeypatch, make_exc):
    exc = make_exc()
    monkeypatch.setattr(os, "symlink", _refusing_symlink(exc))
    with pytest.raises(pytest.skip.Exception) as skipped:
        symlink_or_skip(tmp_path / "link", tmp_path / "target")
    assert "OS refused to create symlink" in skipped.value.msg
    assert str(exc) in skipped.value.msg


@pytest.mark.parametrize("make_exc", [
    lambda: FileExistsError(errno.EEXIST, "File exists"),
    lambda: FileNotFoundError(errno.ENOENT, "No such file or directory"),
    lambda: OSError(errno.EINVAL, "Invalid argument"),
    lambda: PermissionError(errno.EACCES, "Permission denied"),
    lambda: ValueError("unrelated failure"),
], ids=["EEXIST", "ENOENT", "EINVAL_without_winerror", "EACCES", "ValueError"])
def test_unrelated_errors_propagate(tmp_path, monkeypatch, make_exc):
    exc = make_exc()
    monkeypatch.setattr(os, "symlink", _refusing_symlink(exc))
    with pytest.raises(type(exc)) as raised:
        try:
            symlink_or_skip(tmp_path / "link", tmp_path / "target")
        except pytest.skip.Exception as skipped:
            # A skip would hide the broken setup; report it as a failure.
            pytest.fail(f"unrelated error was turned into a skip: {skipped.msg}")
    assert raised.value is exc


@pytest.mark.parametrize("target_is_directory", [False, True])
def test_successful_symlink_is_created_with_link_target_order(
    tmp_path, monkeypatch, target_is_directory,
):
    calls = []
    monkeypatch.setattr(
        os, "symlink",
        lambda src, dst, target_is_directory=False: calls.append(
            (src, dst, target_is_directory)
        ),
    )
    link, target = tmp_path / "link", tmp_path / "target"
    symlink_or_skip(link, target, target_is_directory=target_is_directory)
    assert calls == [(target, link, target_is_directory)]


def test_real_symlink_exists_and_points_at_target(tmp_path):
    target = tmp_path / "target.json"
    target.write_text("original", encoding="utf-8")
    link = tmp_path / "alias.json"
    symlink_or_skip(link, target)
    assert link.is_symlink()
    assert link.read_text(encoding="utf-8") == "original"
