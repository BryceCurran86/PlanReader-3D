"""Memory guards must sample the actual child, never a foreign namespace PID."""
from pathlib import Path
import os

import pytest

from tools import four_job_windows_launcher as launcher

pytestmark = pytest.mark.skipif(os.name == "nt", reason="Linux procfs PID namespace monitor")


def process(root: Path, outer, inner, *, parent=1, rss=100, namespace="pid:[42]"):
    p = root / str(outer)
    (p / "ns").mkdir(parents=True)
    (p / "ns" / "pid").symlink_to(namespace)
    (p / "status").write_text(f"Pid:\t{outer}\nNSpid:\t{outer}\t{inner}\nVmRSS:\t{rss} kB\n")
    (p / "stat").write_text(f"{outer} (worker (with spaces)) S {parent} 0 0")


@pytest.fixture
def procfs(tmp_path, monkeypatch):
    root = tmp_path / "proc"
    (root / "self" / "ns").mkdir(parents=True)
    (root / "self" / "ns" / "pid").symlink_to("pid:[42]")
    (root / "meminfo").write_text("MemAvailable: 9000 kB\nSwapFree: 1000 kB\n")
    monkeypatch.setattr(launcher, "_PROC_ROOT", root)
    return root


def test_host_procfs_maps_namespace_pid_and_sums_its_actual_descendants(procfs):
    process(procfs, 7, 7, rss=999999, namespace="pid:[foreign]")
    process(procfs, 101, 7, rss=300)
    process(procfs, 102, 8, parent=101, rss=200)
    process(procfs, 103, 7, rss=888888, namespace="pid:[another]")
    assert launcher._procfs_pid_for_namespace_pid(7) == 101
    assert launcher.sample_memory_kb(7) == (500, 500, 10000)


def test_normal_same_namespace_procfs_keeps_direct_pid(procfs):
    process(procfs, 7, 7, rss=300)
    assert launcher._procfs_pid_for_namespace_pid(7) == 7
    assert launcher.sample_memory_kb(7) == (300, 300, 10000)


def test_foreign_matching_numeric_pid_is_unavailable_not_zero_as_a_real_child(procfs):
    process(procfs, 7, 7, rss=999999, namespace="pid:[foreign]")
    assert launcher._procfs_pid_for_namespace_pid(7) is None
    assert launcher.sample_memory_kb(7) == (0, 0, None)


def test_ambiguous_mapping_never_elects_first_process(procfs):
    process(procfs, 101, 7)
    process(procfs, 102, 7)
    assert launcher._procfs_pid_for_namespace_pid(7) is None


@pytest.mark.parametrize("pid", [True, False, "7", 0, -1])
def test_noncanonical_pid_cannot_sample_another_process(procfs, pid):
    assert launcher.sample_memory_kb(pid) == (0, 0, None)


def test_absent_namespace_or_invalid_source_metadata_is_unavailable(procfs):
    process(procfs, 101, 7)
    (procfs / "101" / "status").write_text("NSpid: invalid\nVmRSS: 1000 kB\n")
    assert launcher.sample_memory_kb(7) == (0, 0, None)
    (procfs / "self" / "ns" / "pid").unlink()
    assert launcher.sample_memory_kb(7) == (0, 0, None)
