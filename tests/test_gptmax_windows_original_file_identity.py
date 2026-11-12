"""Windows original-source identity: tolerate volatile ctime, never tolerate file swaps."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from tools.gpt3_original_source_preflight import (
    _same_original_file_stat,
    _source_identity_fields,
)


def _snapshot(**changes):
    values = dict(
        st_mode=0o100644,
        st_dev=123,
        st_ino=456789,
        st_size=2024,
        st_mtime_ns=12345678901234,
        st_ctime_ns=12345678901234,
    )
    values.update(changes)
    return SimpleNamespace(**values)


def test_windows_ignores_only_ctime_disagreement_on_same_file():
    before = _snapshot()
    opened = _snapshot(st_ctime_ns=before.st_ctime_ns + 1_000_000)
    assert _source_identity_fields("nt") == ("st_dev", "st_ino", "st_size", "st_mtime_ns")
    assert _same_original_file_stat(before, opened, platform_name="nt")
    assert not _same_original_file_stat(before, opened, platform_name="posix")
    assert "st_ctime_ns" in _source_identity_fields("posix")


@pytest.mark.parametrize("field", ("st_dev", "st_ino", "st_size", "st_mtime_ns"))
@pytest.mark.parametrize("platform", ("nt", "posix"))
def test_real_file_identity_and_content_fields_never_ignored(platform, field):
    before = _snapshot()
    different = _snapshot(**{field: getattr(before, field) + 1})
    assert not _same_original_file_stat(before, different, platform_name=platform)


def test_windows_unknown_file_id_fails_closed():
    assert not _same_original_file_stat(
        _snapshot(st_ino=0), _snapshot(st_ino=0), platform_name="nt",
    )
    assert not _same_original_file_stat(
        _snapshot(), _snapshot(st_ino=0), platform_name="nt",
    )


def test_native_platform_selection_is_explicit_and_deterministic():
    from os import name
    assert _source_identity_fields() == _source_identity_fields(name)
    assert _same_original_file_stat(_snapshot(), _snapshot())


def test_actual_native_reader_consumes_the_preflight_identity_without_shape_drift(tmp_path):
    import hashlib
    from tools.gpt3_native_source_execution_coverage import _original_bytes
    from tools.gpt3_original_source_preflight import _stable_original_digest

    payload = b"unchanged original-source reader regression"
    path = tmp_path / "original.bin"
    path.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    observed, identity = _original_bytes(path, digest)
    assert observed == payload
    assert identity == _stable_original_digest(path)[1]
