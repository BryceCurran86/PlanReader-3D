"""Run integrity imports in child processes, preserving other tests' modules."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

_ROOT = Path(__file__).resolve().parents[1]


def _child_case(case: str, operation: str, directory: str) -> None:
    # Full-suite collectors may install unrelated benchmark probes. This import
    # belongs only to a new interpreter; no parent sys.modules entries are removed.
    sys.path.insert(0, str(_ROOT))
    from scripts import check_full_plan_v2_integrity as gate

    fields = gate._cross_descriptor_identity_fields()
    assert {"st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns"} <= set(fields)
    assert ("st_ctime_ns" not in fields) == (os.name == "nt")
    path = Path(directory) / "frozen.json"
    raw = b'{"value":1}'
    path.write_bytes(raw)
    read = gate._json if operation == "json" else gate._present_source_digest
    original_lstat, original_fstat = Path.lstat, os.fstat
    path_reads = 0
    descriptor_reads = 0

    def changed_path(self: Path):
        nonlocal path_reads
        result = original_lstat(self)
        if self != path:
            return result
        path_reads += 1
        values = {field: getattr(result, field) for field in gate._SOURCE_IDENTITY_FIELDS}
        if case == "zero_inode":
            values["st_ino"] = 0
        if path_reads >= 2:
            if case == "changed_inode":
                values["st_ino"] += 1
            elif case == "path_ctime":
                values["st_ctime_ns"] += 100000
        return SimpleNamespace(**values)

    def changed_descriptor(fd: int):
        nonlocal descriptor_reads
        descriptor_reads += 1
        result = original_fstat(fd)
        values = {field: getattr(result, field) for field in gate._SOURCE_IDENTITY_FIELDS}
        if case == "zero_inode":
            values["st_ino"] = 0
        if case == "cross_api_ctime" or (case == "descriptor_ctime" and descriptor_reads >= 2):
            values["st_ctime_ns"] += 100000
        return SimpleNamespace(**values)

    with patch.object(Path, "lstat", changed_path), patch.object(os, "fstat", changed_descriptor):
        rejected = case not in {"real_file", "cross_api_ctime"} or (
            case == "cross_api_ctime" and os.name != "nt"
        )
        if rejected:
            try:
                read(path)
            except ValueError as exc:
                assert "changed" in str(exc)
            else:
                raise AssertionError("Changed or unauthenticated file identity was accepted")
        elif operation == "json":
            assert read(path) == {"value": 1}
        else:
            assert read(path) == (hashlib.sha256(raw).hexdigest(), len(raw))


@pytest.mark.parametrize("operation", ["json", "source"])
@pytest.mark.parametrize(
    "case",
    [
        "real_file",
        "changed_inode",
        "path_ctime",
        "descriptor_ctime",
        "cross_api_ctime",
        "zero_inode",
    ],
)
def test_integrity_identity_in_isolated_interpreter(case, operation, tmp_path):
    before = {
        name: module
        for name, module in sys.modules.items()
        if name == "benchmarks" or name.startswith("benchmarks.")
    }
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), case, operation, str(tmp_path)],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert all(sys.modules.get(name) is module for name, module in before.items())


if __name__ == "__main__":
    _child_case(*sys.argv[1:])
