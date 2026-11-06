"""Source-neutral GPT3 process cleanup tests; no private PDF is needed.

The original source-role runner's MEMORY_LIMIT and TIMEOUT must never leave
an OCR/PDF child alive to contaminate the next separately authenticated role.
"""
from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from tools import four_job_windows_launcher as launcher


def _still_running(pid: int) -> bool:
    """A reparented zombie is dead even if /proc still has a PID entry."""
    try:
        stat = (Path("/proc") / str(pid) / "stat").read_text()
    except (FileNotFoundError, ProcessLookupError):
        return False
    return stat.rsplit(")", 1)[1].split()[0] not in {"Z", "X"}


@pytest.mark.skipif(os.name == "nt" or not Path("/proc").exists(),
                    reason="POSIX /proc process-group cleanup")
@pytest.mark.parametrize("guard", ("timeout", "memory"))
def test_source_role_abort_reaps_child_and_parent(tmp_path, monkeypatch, guard):
    child_pid_file = tmp_path / "worker.pid"
    code = (
        "from pathlib import Path; import subprocess, sys, time; "
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
        "Path(sys.argv[1]).write_text(str(p.pid)); "
        "time.sleep(60)"
    )
    kwargs = {"timeout_s": 0.8, "poll_s": 0.35}
    if guard == "memory":
        # Trigger the resource stop deterministically, not by consuming GB.
        monkeypatch.setattr(launcher, "sample_memory_kb",
                            lambda _pid: (2048, 2048, None))
        kwargs.update({"timeout_s": 20, "max_private_mb": 1})
    pid = None
    try:
        rc, status, _usage = launcher.run_logged(
            [sys.executable, "-c", code, str(child_pid_file)],
            tmp_path, tmp_path / (guard + ".log"), **kwargs,
        )
        assert (rc, status) == (
            None, "MEMORY_LIMIT" if guard == "memory" else "TIMEOUT"
        )
        assert child_pid_file.is_file(), "test worker failed to spawn child"
        pid = int(child_pid_file.read_text())
        deadline = time.monotonic() + 3
        while _still_running(pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not _still_running(pid), "source child survived parent abort"
    finally:
        # Keep CI clean even when the regression reappears.
        if pid is None and child_pid_file.is_file():
            pid = int(child_pid_file.read_text())
        if pid is not None and _still_running(pid):
            os.kill(pid, signal.SIGKILL)


@pytest.mark.skipif(os.name == "nt" or not Path("/proc").exists(),
                    reason="POSIX /proc process-group cleanup")
def test_source_abort_does_not_kill_unrelated_process_group(tmp_path):
    independent = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        start_new_session=True,
    )
    try:
        rc, status, _ = launcher.run_logged(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            tmp_path, tmp_path / "bounded.log", timeout_s=0.5, poll_s=0.25,
        )
        assert (rc, status) == (None, "TIMEOUT")
        assert independent.poll() is None
    finally:
        independent.kill()
        independent.wait()
