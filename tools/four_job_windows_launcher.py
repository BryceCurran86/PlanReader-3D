"""Owner-side, source-byte-preserving PlanReader Full Plan V2 diagnostic launcher (v2).

Runs on the owner's Windows machine next to a private ``sources/`` folder and a
``LOCAL_SOURCE_INVENTORY.json``. It never copies, edits or uploads a source PDF,
never pushes to GitHub, never edits benchmark truth, and never publishes a score.
All producer outputs go to a separate private directory.

Changes from v1 (each one is a failure observed on the first owner run):

* v1 never refreshed its dedicated repository snapshot, so a merged fix could not
  reach the run. v2 fetches ``origin`` into the dedicated snapshot (detached
  checkout, nothing else modified) and records the exact commit; ``--ref`` pins one.
* v1 gave every project the same fixed 30 minute limit and wrote its status file
  only at the very end, so a timeout produced an empty log and lost the earlier
  results. v2 writes ``BENCHMARK_DIAGNOSTIC_STATUS.json`` after every project,
  takes ``--timeout-min`` per project, and dumps the Python stacks every
  ``--stack-dump-min`` minutes so a timeout names the stage that was running.
* v2 samples the memory of the whole project process tree (a Windows virtual environment's python.exe is only
  a launcher; the real interpreter is its child) and records the peak working set and private memory. It
  stops a project that commits more than ``--max-private-gb`` (MEMORY_LIMIT) or that pushes the machine's free
  commit below ``--min-free-commit-gb`` (SYSTEM_MEMORY_GUARD) so one project cannot make the owner's other
  programs fail; both are recorded as negative evidence.
* ``--with-ocr`` (default off) installs the optional OCR extras into the isolated environment and records whether they
  were installed, because most text on subset-font CAD exports is untrusted without raster corroboration.
* v2 writes ``SHARE_SAFE_STATUS.json`` with no local paths, so it can be pasted
  into the coordination issue without exposing the owner's folder names.

It is a diagnostic harness. A completed single-document handoff is not a complete
source-closed project, not a signed quantity and not an official score.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import signal
import shutil
import subprocess
import sys
import time
import venv
from ctypes import wintypes
from pathlib import Path

PROJECTS = (
    "au_qld_lot16_power",
    "au_qld_3laurel",
    "au_qld_maryborough_service_station",
    "au_qld_q5446_armstrong32_harlequin",
)
PRIMARY_PDF = {
    "au_qld_lot16_power": "1. Construction Plans - Lot 16 Power (REV E).pdf",
    "au_qld_3laurel": "3LAUREL - Construction Plan Set Rev3 08.05.26.pdf",
    "au_qld_maryborough_service_station": "Arch_Combined_Maryborough_Service_Station.pdf",
    "au_qld_q5446_armstrong32_harlequin": "Q5446_Standard_Plans_V1_20220320.pdf",
}
REPO_URL = "https://github.com/BryceCurran86/PlanReader-3D.git"
# SHA-256 of the sorted [project, filename, size, SHA-256] rows from the
# unchanged Full Plan V2 source manifests. The kit inventory cannot supply
# the authority used to verify its own source files.
_FROZEN_SOURCE_ROSTER_SHA256 = "6229de79e33200a723da9ec30593aead904f96ae41b8f82274a2fb6641dfde83"


def note(message: str) -> None:
    print(message, flush=True)


def output_report(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


_PROC_ROOT = Path("/proc")


def _procfs_pid_for_namespace_pid(pid: int) -> int | None:
    """Translate our namespace PID before reading a possibly host-mounted /proc.

    A numeric /proc directory may belong to an unrelated process when procfs
    was mounted outside this PID namespace. Match both the namespace inode and
    its innermost NSpid; never sample the first numerically matching directory.
    """
    if type(pid) is not int or pid <= 0:
        return None
    try:
        namespace = os.readlink(_PROC_ROOT / "self" / "ns" / "pid")
    except OSError:
        return None

    def matches(entry: Path) -> bool:
        try:
            if os.readlink(entry / "ns" / "pid") != namespace:
                return False
            for line in (entry / "status").read_text().splitlines():
                if line.startswith("NSpid:"):
                    ids = tuple(int(value) for value in line.split()[1:])
                    return bool(ids) and ids[-1] == pid
        except (OSError, ValueError):
            return False
        return False

    direct = _PROC_ROOT / str(pid)
    if matches(direct):
        return pid
    matches_in_namespace = [int(entry.name) for entry in _PROC_ROOT.iterdir()
                            if entry.name.isdigit() and matches(entry)]
    return matches_in_namespace[0] if len(matches_in_namespace) == 1 else None


def _children_by_parent() -> dict[int, list[int]]:
    """POSIX only: parent pid -> child pids, read from /proc."""
    children: dict[int, list[int]] = {}
    for entry in _PROC_ROOT.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text(encoding="utf-8", errors="replace")
            ppid = int(stat.rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            continue
        children.setdefault(ppid, []).append(int(entry.name))
    return children


def _windows_worker_pids(pid: int) -> tuple[int, ...]:
    """Read the owned worker's descendant IDs from one native process snapshot."""
    class ProcessEntry(ctypes.Structure):
        _fields_ = [
            ("size", wintypes.DWORD), ("usage", wintypes.DWORD), ("pid", wintypes.DWORD),
            ("heap_id", ctypes.c_size_t), ("module_id", wintypes.DWORD),
            ("thread_count", wintypes.DWORD), ("parent_pid", wintypes.DWORD),
            ("base_priority", wintypes.LONG), ("flags", wintypes.DWORD),
            ("executable_name", wintypes.WCHAR * 260),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateToolhelp32Snapshot
    create.argtypes = (wintypes.DWORD, wintypes.DWORD)
    create.restype = wintypes.HANDLE
    first, next_entry = kernel.Process32FirstW, kernel.Process32NextW
    first.argtypes = next_entry.argtypes = (wintypes.HANDLE, ctypes.POINTER(ProcessEntry))
    first.restype = next_entry.restype = wintypes.BOOL
    close = kernel.CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    close.restype = wintypes.BOOL
    snapshot = create(0x00000002, 0)  # TH32CS_SNAPPROCESS
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    children: dict[int, list[int]] = {}
    root_alive = False
    try:
        entry = ProcessEntry()
        entry.size = ctypes.sizeof(entry)
        if not first(snapshot, ctypes.byref(entry)):
            raise ctypes.WinError(ctypes.get_last_error())
        while True:
            if entry.pid == pid:
                root_alive = True
            children.setdefault(entry.parent_pid, []).append(entry.pid)
            if not next_entry(snapshot, ctypes.byref(entry)):
                if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
                    raise ctypes.WinError(ctypes.get_last_error())
                break
    finally:
        close(snapshot)
    if not root_alive:
        return ()
    pending = [pid]
    owned: dict[int, None] = {}
    while pending:
        current = pending.pop()
        if current not in owned:
            owned[current] = None
            pending.extend(children.get(current, ()))
    return tuple(owned)


def _sample_windows_memory_kb(pid: int) -> tuple[int, int, int | None]:
    """Sample worker private commit and system commit with the local Windows API."""
    class ProcessMemory(ctypes.Structure):
        _fields_ = [
            ("size", wintypes.DWORD), ("page_faults", wintypes.DWORD),
            *[(name, ctypes.c_size_t) for name in (
                "peak_working_set", "working_set", "peak_paged_pool", "paged_pool",
                "peak_nonpaged_pool", "nonpaged_pool", "pagefile", "peak_pagefile",
                "private_bytes",
            )],
        ]

    class SystemMemory(ctypes.Structure):
        _fields_ = [
            ("size", wintypes.DWORD),
            *[(name, ctypes.c_size_t) for name in (
                "commit_total", "commit_limit", "commit_peak", "physical_total",
                "physical_available", "system_cache", "kernel_total", "kernel_paged",
                "kernel_nonpaged", "page_size",
            )],
            ("handle_count", wintypes.DWORD), ("process_count", wintypes.DWORD),
            ("thread_count", wintypes.DWORD),
        ]

    owned = _windows_worker_pids(pid)
    if not owned:
        return 0, 0, None
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    open_process = kernel.OpenProcess
    open_process.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    open_process.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    close.restype = wintypes.BOOL
    process_memory = psapi.GetProcessMemoryInfo
    process_memory.argtypes = (wintypes.HANDLE, ctypes.POINTER(ProcessMemory), wintypes.DWORD)
    process_memory.restype = wintypes.BOOL

    working_set = private = 0
    for worker in owned:
        handle = open_process(0x1000, False, worker)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            if ctypes.get_last_error() == 87 and worker != pid:  # exited since enumeration
                continue
            return 0, 0, None
        try:
            memory = ProcessMemory()
            memory.size = ctypes.sizeof(memory)
            if not process_memory(handle, ctypes.byref(memory), memory.size):
                return 0, 0, None
            working_set += memory.working_set
            private += memory.private_bytes
        finally:
            close(handle)

    system_memory = psapi.GetPerformanceInfo
    system_memory.argtypes = (ctypes.POINTER(SystemMemory), wintypes.DWORD)
    system_memory.restype = wintypes.BOOL
    system = SystemMemory()
    system.size = ctypes.sizeof(system)
    free_kb = None
    if system_memory(ctypes.byref(system), system.size):
        free_kb = max(0, system.commit_limit - system.commit_total) * system.page_size // 1024
    return working_set // 1024, private // 1024, free_kb


def sample_memory_kb(pid: int) -> tuple[int, int, int | None]:
    """(working set KB, private KB, system free commit KB or None) for ``pid`` and all its descendants.

    A Windows virtual environment's ``python.exe`` is only a launcher that starts the real interpreter as a
    child, so sampling ``pid`` alone reads the launcher (a few MB). The whole process tree is summed.
    Failure to sample returns an explicit missing reading for the caller's memory policy.
    """
    try:
        if os.name == "nt":
            return _sample_windows_memory_kb(pid)
        procfs_pid = _procfs_pid_for_namespace_pid(pid)
        if procfs_pid is None:
            return 0, 0, None
        children = _children_by_parent()
        pids, stack = set(), [procfs_pid]
        while stack:
            current = stack.pop()
            if current not in pids:
                pids.add(current)
                stack.extend(children.get(current, ()))
        rss_kb = 0
        for current in pids:
            try:
                for line in (_PROC_ROOT / str(current) / "status").read_text().splitlines():
                    if line.startswith("VmRSS:"):
                        rss_kb += int(line.split()[1])
            except OSError:
                continue
        free_kb = None
        meminfo = {line.split(":")[0]: int(line.split()[1]) for line in (_PROC_ROOT / "meminfo").read_text().splitlines()}
        if "MemAvailable" in meminfo:
            free_kb = meminfo["MemAvailable"] + meminfo.get("SwapFree", 0)
        return rss_kb, rss_kb, free_kb
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return 0, 0, None


def kill_tree(proc: subprocess.Popen) -> None:
    """Reap a source worker and, on POSIX, its *isolated* process group.

    A producer can spawn OCR/PDF children. Killing just its parent leaves
    descendants running after a MEMORY_LIMIT/TIMEOUT decision and can make
    the next immutable-source role consume memory from a previous attempt.
    Never signal the caller's group or an externally supplied ungrouped pid.
    """
    if os.name == "nt":
        if proc.poll() is not None:
            return
        # A single worker can be stopped via the owned Popen handle. For an
        # actual tree, require taskkill to confirm descendant termination.
        try:
            owned = _windows_worker_pids(proc.pid)
            if owned == (proc.pid,):
                proc.kill()
            elif proc.poll() is None and subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                capture_output=True, check=False, timeout=10,
            ).returncode:
                raise RuntimeError("Windows could not confirm termination of the source worker tree")
        except (OSError, RuntimeError, subprocess.SubprocessError):
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=10)
            raise
        proc.wait(timeout=10)
        return
    else:
        try:
            group_id = os.getpgid(proc.pid)
            if group_id == proc.pid and group_id != os.getpgrp():
                os.killpg(group_id, signal.SIGKILL)
            else:
                # Fail closed for a Popen that was not launched in our own
                # session: killing a shared group could kill the caller.
                proc.kill()
        except ProcessLookupError:
            pass  # The worker exited between polling and termination.
    proc.wait()


def run_logged(
    args: list[str], cwd: Path, log: Path, *, timeout_s: int = 1800, track_memory: bool = False,
    poll_s: float = 15, max_private_mb: int | None = None, min_free_commit_mb: int | None = None,
) -> tuple[int | None, str, dict]:
    """Run ``args`` under hard limits. Returns (exit code, status, usage).

    Status is COMPLETED, PROCESS_FAILED, TIMEOUT, MEMORY_SAMPLING_UNAVAILABLE,
    MEMORY_LIMIT (the process tree's private memory exceeded
    ``max_private_mb``) or SYSTEM_MEMORY_GUARD (the machine's free commit fell below ``min_free_commit_mb``,
    which would start failing other programs). The last two are recorded as negative evidence, not hidden.
    ``usage`` holds the sampled peaks in KB.
    """
    log.parent.mkdir(parents=True, exist_ok=True)
    usage = {"peak_working_set_kb": 0, "peak_private_kb": 0, "min_system_free_commit_kb": None}
    measure = track_memory or max_private_mb is not None or min_free_commit_mb is not None
    with log.open("w", encoding="utf-8", errors="replace") as fh:
        fh.write("COMMAND: " + " ".join(map(str, args)) + "\n")
        fh.flush()
        proc = subprocess.Popen(
            args, cwd=cwd, stdout=fh, stderr=subprocess.STDOUT,
            start_new_session=(os.name != "nt"),
        )
        started = time.monotonic()
        while True:
            try:
                rc = proc.wait(timeout=poll_s)
                # A process that exits before the first polling deadline has
                # no observed memory evidence. Never call that a guarded pass.
                if ((max_private_mb is not None and usage["peak_private_kb"] <= 0)
                        or (min_free_commit_mb is not None
                            and usage["min_system_free_commit_kb"] is None)):
                    return None, "MEMORY_SAMPLING_UNAVAILABLE", usage
                return rc, "COMPLETED" if rc == 0 else "PROCESS_FAILED", usage
            except subprocess.TimeoutExpired:
                elapsed = time.monotonic() - started
                if measure:
                    ws_kb, private_kb, free_kb = sample_memory_kb(proc.pid)
                    usage["peak_working_set_kb"] = max(usage["peak_working_set_kb"], ws_kb)
                    usage["peak_private_kb"] = max(usage["peak_private_kb"], private_kb)
                    if free_kb is not None:
                        previous = usage["min_system_free_commit_kb"]
                        usage["min_system_free_commit_kb"] = free_kb if previous is None else min(previous, free_kb)
                    # Fail closed when a configured guard lacks its required metric.
                    # A zero private-memory reading is not evidence of safety;
                    # free commit may be unavailable even when RSS was sampled.
                    if ((max_private_mb is not None and private_kb <= 0)
                            or (min_free_commit_mb is not None and free_kb is None)):
                        kill_tree(proc)
                        return None, "MEMORY_SAMPLING_UNAVAILABLE", usage
                    if max_private_mb is not None and private_kb // 1024 > max_private_mb:
                        kill_tree(proc)
                        return None, "MEMORY_LIMIT", usage
                    if (min_free_commit_mb is not None and free_kb is not None
                            and free_kb // 1024 < min_free_commit_mb):
                        kill_tree(proc)
                        return None, "SYSTEM_MEMORY_GUARD", usage
                if elapsed >= timeout_s:
                    kill_tree(proc)
                    return None, "TIMEOUT", usage
                if int(elapsed) % 300 < max(poll_s, 1):
                    note(f"  ... running {int(elapsed // 60)} min, peak private {usage['peak_private_kb'] // 1024} MB "
                         f"(log: {log.name})")


OCR_EXTRAS = ("rapidocr", "onnxruntime")


def ocr_install_command(python: Path) -> list[str]:
    """The optional OCR extras the diagnostic CI jobs install (not in requirements.txt on purpose)."""
    return [str(python), "-m", "pip", "install", "--disable-pip-version-check", *OCR_EXTRAS]


def verify_originals(kit: Path, report_dir: Path) -> bool:
    manifest = json.loads((kit / "LOCAL_SOURCE_INVENTORY.json").read_text(encoding="utf-8-sig"))
    if not isinstance(manifest, dict):
        raise ValueError("Unsafe source inventory")
    entries = manifest.get("docs")
    if (manifest.get("benchmark_id") != "full_plan_takeoff_reconciliation_v2"
            or not isinstance(entries, list) or len(entries) != 10):
        raise ValueError("Expected exactly the ten original Full Plan V2 sources")
    roster = []
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("Unsafe source inventory entry")
        project, filename = item.get("project_id"), item.get("manifest_name")
        size, digest = item.get("expected_size_bytes"), item.get("original_sha256")
        if (
            project not in PROJECTS
            or type(filename) is not str
            or not filename.lower().endswith(".pdf")
            or any(separator in filename for separator in ("/", "\\", ":"))
            or type(size) is not int
            or size <= 0
            or type(digest) is not str
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError("Unsafe source inventory entry")
        roster.append((project, filename, size, digest))
    roster_bytes = json.dumps(sorted(roster), separators=(",", ":")).encode("utf-8")
    if hashlib.sha256(roster_bytes).hexdigest() != _FROZEN_SOURCE_ROSTER_SHA256:
        raise ValueError("Source inventory differs from the frozen original source roster")

    statuses = []
    for project, filename, size, digest in roster:
        path = kit / "sources" / project / filename
        if not path.is_file() or path.is_symlink():
            status = "MISSING"
        elif path.stat().st_size != size:
            status = "MISMATCH"
        else:
            with path.open("rb") as source:
                checksum = hashlib.sha256()
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    checksum.update(chunk)
            status = "VERIFIED" if checksum.hexdigest() == digest else "MISMATCH"
        statuses.append({"project_id": project, "file_name": filename, "status": status})
        note(f"  {project}: {filename}: {status}")
    output_report(report_dir / "SOURCE_SHA_VERIFICATION.json", {
        "benchmark_id": "full_plan_takeoff_reconciliation_v2",
        "verified_document_count": sum(x["status"] == "VERIFIED" for x in statuses),
        "expected_document_count": 10,
        "rows": statuses,
        "score_granted": False,
    })
    return all(x["status"] == "VERIFIED" for x in statuses)


def git(args: list[str], repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)


def _full_commit(ref: str) -> bool:
    return len(ref) == 40 and all(character in "0123456789abcdefABCDEF" for character in ref)


def refresh_failure(session: Path, ref: str, status: str) -> None:
    """Record that the requested snapshot was not obtained. No producer runs after this."""
    output_report(session / "SNAPSHOT_REFRESH.json", {
        "requested_ref": ref,
        "status": status,
        "repo_head_used": None,
        "preflight_started": False,
        "production_started": False,
        "official_four_project_coverage_accuracy": None,
        "official_four_project_precision_adjusted_accuracy": None,
        "full_suite_publication_status": "UNPUBLISHED",
    })


def refresh_snapshot(repo: Path, runs: Path, session: Path, ref: str) -> str | None:
    """Clone on first use; afterwards fetch ``ref`` and check it out detached.

    A failed fetch or a checkout that is not the requested commit returns None.
    The previous snapshot is never reused in that case.
    """
    if not repo.exists():
        note("Step 2: obtaining a private local copy of the public PlanReader code (no upload)")
        rc, _, _ = run_logged(["git", "clone", "--depth", "1", "--branch", "main", REPO_URL, str(repo)], runs,
                              session / "git_clone.log", timeout_s=900)
        if rc != 0:
            note(f"Unable to clone repository. See {session / 'git_clone.log'}; check Git and internet access.")
            refresh_failure(session, ref, "CLONE_FAILED")
            return None
    elif not (repo / ".git").exists():
        note(f"Expected Git repository but found unrelated directory: {repo}. No files changed.")
        refresh_failure(session, ref, "SNAPSHOT_NOT_A_REPOSITORY")
        return None
    note(f"Step 2: refreshing the dedicated snapshot to {ref}")
    log = session / "git_refresh.log"
    # A shallow snapshot is fetched at the requested ref only; nothing outside the snapshot changes.
    fetch = git(["fetch", "--depth", "1", "origin", ref], repo)
    log.write_text(fetch.stdout + fetch.stderr, encoding="utf-8")
    if fetch.returncode != 0:
        note(f"Could not fetch {ref}; see {log}. No preflight or production will start.")
        refresh_failure(session, ref, "FETCH_FAILED")
        return None
    checkout = git(["checkout", "--detach", "FETCH_HEAD"], repo)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(checkout.stdout + checkout.stderr)
    if checkout.returncode != 0:
        note(f"Could not check out {ref}; see {log}. No preflight or production will start.")
        refresh_failure(session, ref, "CHECKOUT_FAILED")
        return None
    parsed = git(["rev-parse", "HEAD"], repo)
    head = parsed.stdout.strip()
    if parsed.returncode != 0 or len(head) != 40:
        note(f"Could not read the snapshot HEAD after checking out {ref}. No extraction will start.")
        refresh_failure(session, ref, "HEAD_UNREADABLE")
        return None
    if _full_commit(ref) and head.lower() != ref.lower():
        note(f"Checked out {head}, which is not the requested commit {ref}. No extraction will start.")
        refresh_failure(session, ref, "PINNED_COMMIT_MISMATCH")
        return None
    state = git(["status", "--porcelain=v1", "--untracked-files=no"], repo)
    if state.returncode != 0 or state.stdout.strip():
        note("The tracked checkout could not be verified as clean. No extraction will start.")
        refresh_failure(
            session, ref, "CHECKOUT_STATE_UNVERIFIED" if state.returncode else "CHECKOUT_HAS_TRACKED_CHANGES",
        )
        return None
    output_report(session / "SNAPSHOT_REFRESH.json", {
        "requested_ref": ref,
        "status": "CHECKED_OUT",
        "repo_head_used": head,
        "preflight_started": False,
        "production_started": False,
        "official_four_project_coverage_accuracy": None,
        "full_suite_publication_status": "UNPUBLISHED",
    })
    return head


def handoff_bootstrap(
    out: Path, pdf: Path, project: str, stack_dump_min: int,
    *, family_group: str = "all", source_plan_page_index: int | None = None,
) -> str:
    """Python source that starts one handoff. Paths are data, not syntax."""
    dump = repr(str(out / "stack_dumps.txt"))
    pdf_literal = repr(str(pdf))
    out_literal = repr(str(out))
    project_literal = repr(project)
    seconds = max(1, int(stack_dump_min)) * 60
    if family_group not in ("all", "core", "surfaces", "floor_area"):
        raise ValueError("unsupported source handoff family group")
    if source_plan_page_index is not None and (
        type(source_plan_page_index) is not int or source_plan_page_index < 0
    ):
        raise ValueError("source plan page index must be nonnegative")
    suffix = (
        f", '--source-plan-page-index', {source_plan_page_index!r}"
        if source_plan_page_index is not None else ""
    )
    return (
        "import faulthandler, sys, runpy\n"
        f"f = open({dump}, 'a', encoding='utf-8')\n"
        f"faulthandler.dump_traceback_later({seconds}, repeat=True, file=f)\n"
        "sys.argv = ['run_source_closed_project_handoff', '--pdf', "
        f"{pdf_literal}, '--project-id', {project_literal},\n"
        f"            '--family-group', {family_group!r}, '--output-dir', {out_literal}{suffix}]\n"
        "runpy.run_module('tools.run_source_closed_project_handoff', run_name='__main__', alter_sys=True)\n"
    )


def timeout_stack_tail(out: Path, limit: int = 40) -> str:
    """Last lines of the faulthandler dump, or a stated absence. Not a stage guess."""
    path = out / "stack_dumps.txt"
    if not path.is_file():
        return "no stack dump was written"
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return "stack dump file was empty"
    lines = text.splitlines()
    return "\n".join(lines[-limit:])


def share_safe(status: dict, home: str) -> dict:
    """Same content with the owner's local paths removed."""
    text = json.dumps(status).replace(home.replace("\\", "\\\\"), "<HOME>").replace(home, "<HOME>")
    return json.loads(text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source-only", action="store_true",
                        help="Verify bundled files only; skip network, packages and production")
    parser.add_argument("--ref", default="main", help="Branch or commit of the public repository to run (default main)")
    parser.add_argument("--only", nargs="*", choices=PROJECTS, help="Run production for these projects only")
    parser.add_argument(
        "--family-group", choices=("all", "core", "surfaces", "floor_area"),
        default="all",
        help="Bound original source production by physical family, without claiming full-suite score",
    )
    parser.add_argument(
        "--source-plan-page-index", type=int, default=None,
        help="0-based original floor-plan page (requires exactly one --only project)",
    )
    parser.add_argument("--timeout-min", type=int, default=180, help="Per-project production limit in minutes")
    parser.add_argument("--stack-dump-min", type=int, default=10, help="Dump Python stacks this often (minutes)")
    parser.add_argument("--with-ocr", action="store_true",
                        help="Also install the optional OCR extras (rapidocr, onnxruntime) into the isolated environment, "
                             "as the diagnostic CI jobs do. The shadow raster text corroboration reads about one word per "
                             "2.7 s with them; most of the text on subset-font CAD exports is otherwise untrusted "
                             "(docs/engineering/text_integrity_coverage_20261016.md). Default off.")
    parser.add_argument("--max-private-gb", type=float, default=10.0,
                        help="Stop a project whose process tree commits more private memory than this (MEMORY_LIMIT)")
    parser.add_argument("--min-free-commit-gb", type=float, default=3.0,
                        help="Stop a project when the machine's free commit falls below this (SYSTEM_MEMORY_GUARD)")
    return parser


def main() -> int:
    parser = build_parser()
    opts = parser.parse_args()
    projects = tuple(opts.only) if opts.only else PROJECTS
    if opts.source_plan_page_index is not None and (
        opts.source_plan_page_index < 0 or len(projects) != 1
    ):
        parser.error("source plan page index must be nonnegative and specify exactly one --only project")

    kit = Path(__file__).resolve().parent
    if not (kit / "LOCAL_SOURCE_INVENTORY.json").is_file():
        # The launcher can live in the repository; the kit folder is then the current directory.
        kit = Path.cwd()
    runs = Path.home() / "Documents" / "PlanReader_Private_V2_Run"
    runs.mkdir(parents=True, exist_ok=True)
    session = runs / time.strftime("%Y%m%d_%H%M%S")
    session.mkdir(exist_ok=False)
    note("\nPLANREADER FOUR-JOB PRIVATE SOURCE AND PRODUCTION DIAGNOSTIC (v2)")
    note(f"Input folder: {kit}")
    note(f"Private result folder: {session}")
    note("No source PDFs or project outputs will be uploaded or pushed to GitHub.\n")

    note("Step 1: verifying all 10 original file hashes")
    try:
        verified = verify_originals(kit, session)
    except (OSError, ValueError) as exc:
        note(f"ERROR: Original source inventory verification failed ({type(exc).__name__}).")
        return 2
    if not verified:
        note("ERROR: Original SHA verification failed. No extraction will start.")
        return 2
    note("10/10 SHA-256 sources verified.\n")
    if opts.source_only:
        note("Source-only mode complete. No production extraction or benchmark scorer invoked.")
        return 0

    if not shutil.which("git"):
        note("Git was not found. Install Git for Windows from https://git-scm.com/downloads/win then run again.")
        return 3
    repo = runs / "repo_readonly_snapshot"
    head = refresh_snapshot(repo, runs, session, opts.ref)
    if not head:
        return 4
    note(f"Repository HEAD: {head}")

    envdir = runs / ".venv"
    python = envdir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        note("Step 3: creating an isolated Python environment")
        try:
            venv.create(envdir, with_pip=True)
        except Exception as exc:  # noqa: BLE001 - report any environment failure and stop
            note(f"Could not create Python environment: {exc}")
            return 5
    note("Step 4: installing source-preflight dependency PyMuPDF (first run only)")
    rc, _, _ = run_logged([str(python), "-m", "pip", "install", "--disable-pip-version-check", "PyMuPDF==1.28.0"],
                          repo, session / "install_pymupdf.log", timeout_s=900)
    if rc != 0:
        note(f"Python dependency installation failed; see {session / 'install_pymupdf.log'}.")
        return 5

    note("Step 5: running repository source-package preflight for all four jobs")
    preflight = []
    for project in PROJECTS:
        manifest = repo / "benchmarks" / "frozen_holdout" / "full_plan_v2" / "projects" / project / "source_manifest.json"
        report = session / "preflight" / f"{project}.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        cmd = [str(python), "-m", "tools.diag_gpt1_source_pdf_package_preflight",
               "--manifest", str(manifest), "--source-root", str(kit / "sources" / project), "--output", str(report)]
        rc, status, _ = run_logged(cmd, repo, session / "logs" / f"{project}.preflight.log", timeout_s=240)
        preflight.append({"project_id": project, "status": status, "exit_code": rc, "report": str(report)})
        note(f"  {project}: {status}")
    output_report(session / "PREFLIGHT_STATUS.json", preflight)
    if any(v["status"] != "COMPLETED" for v in preflight):
        note("One or more repository preflights failed. No production extraction started.")
        return 6

    note("Step 6: preparing isolated production dependencies (may take several minutes)")
    rc, _, _ = run_logged([str(python), "-m", "pip", "install", "--disable-pip-version-check", "-r",
                           str(repo / "requirements.txt")], repo, session / "install_production_dependencies.log",
                          timeout_s=1800)
    if rc != 0:
        note(f"Production dependency installation failed. Source preflight succeeded. See {session / 'install_production_dependencies.log'}.")
        return 7

    ocr_installed = False
    if opts.with_ocr:
        note("Step 6b: installing the optional OCR extras (rapidocr, onnxruntime) into the isolated environment")
        rc, _, _ = run_logged(ocr_install_command(python), repo, session / "install_ocr_extras.log", timeout_s=1800)
        ocr_installed = rc == 0
        if not ocr_installed:
            note(f"OCR extras were not installed; continuing without them. See {session / 'install_ocr_extras.log'}.")

    note("Step 7: running separate source-closed production diagnostics, one project at a time")
    note("NOTE: the main architectural PDF is the per-project handoff input. Multi-document roles are NOT silently "
         "treated as a complete source-closed project.")
    summary = {
        "benchmark_id": "full_plan_takeoff_reconciliation_v2",
        "launcher_version": 2,
        "repo_head": head,
        "requested_ref": opts.ref,
        "source_pdf_count": 10,
        "source_preflight": "VERIFIED",
        "family_group": opts.family_group,
        "source_plan_page_index": opts.source_plan_page_index,
        # This diagnostic passes one primary PDF per project even when it runs
        # every project and all quantity families. Companion roles do not run.
        "source_scope_complete": False,
        "requested_full_diagnostic_scope": (
            opts.family_group == "all" and opts.source_plan_page_index is None
            and len(projects) == len(PROJECTS)
        ),
        "per_project_timeout_min": opts.timeout_min,
        "ocr_extras_requested": bool(opts.with_ocr),
        "ocr_extras_installed": ocr_installed,
        "max_private_gb": opts.max_private_gb,
        "min_free_commit_gb": opts.min_free_commit_gb,
        "project_handoffs": [],
        "official_four_project_coverage_accuracy": None,
        "official_four_project_precision_adjusted_accuracy": None,
        "full_suite_publication_status": "UNPUBLISHED",
        "explanation": "Single primary-PDF project handoffs are partial diagnostics and do not contain independent "
                       "four-project signed identity maps and complete multi-document source authority. "
                       "No official V2 evaluator was run.",
    }
    for project in projects:
        pdf = kit / "sources" / project / PRIMARY_PDF[project]
        if not pdf.is_file():
            summary["project_handoffs"].append({"project_id": project, "status": "PRIMARY_SOURCE_UNAVAILABLE"})
            continue
        out = session / "project_outputs" / project
        out.mkdir(parents=True, exist_ok=True)
        bootstrap = handoff_bootstrap(
            out, pdf, project, opts.stack_dump_min,
            family_group=opts.family_group,
            source_plan_page_index=opts.source_plan_page_index,
        )
        note(f"  Starting {project} (max {opts.timeout_min} minutes; log in the logs folder)")
        started = time.monotonic()
        rc, status, usage = run_logged([str(python), "-u", "-c", bootstrap], repo,
                                       session / "logs" / f"{project}.handoff.log",
                                       timeout_s=opts.timeout_min * 60, track_memory=True,
                                       max_private_mb=int(opts.max_private_gb * 1024),
                                       min_free_commit_mb=int(opts.min_free_commit_gb * 1024))
        handoff = {
            "project_id": project, "status": status, "exit_code": rc,
            "family_group": opts.family_group,
            "source_plan_page_index": opts.source_plan_page_index,
            "elapsed_s": round(time.monotonic() - started, 1),
            "peak_working_set_mb_sampled": round(usage["peak_working_set_kb"] / 1024, 1),
            "peak_private_mb_sampled": round(usage["peak_private_kb"] / 1024, 1),
            "min_system_free_commit_mb_sampled": (None if usage["min_system_free_commit_kb"] is None
                                                  else round(usage["min_system_free_commit_kb"] / 1024, 1)),
            "single_document_handoff_only": True, "output_folder": str(out),
        }
        if status in {"TIMEOUT", "MEMORY_LIMIT", "SYSTEM_MEMORY_GUARD", "PROCESS_FAILED"}:
            handoff["stack_dump_tail"] = timeout_stack_tail(out)
        summary["project_handoffs"].append(handoff)
        note(f"  {project}: {status}")
        # Written after every project so an interrupted run keeps what already finished.
        output_report(session / "BENCHMARK_DIAGNOSTIC_STATUS.json", summary)
        output_report(session / "SHARE_SAFE_STATUS.json", share_safe(summary, str(Path.home())))
    output_report(session / "BENCHMARK_DIAGNOSTIC_STATUS.json", summary)
    output_report(session / "SHARE_SAFE_STATUS.json", share_safe(summary, str(Path.home())))
    note("\nPrivate diagnostic complete. Do not claim an official four-job accuracy score.")
    note(f"Please share SHARE_SAFE_STATUS.json and the logs from: {session}")
    return 0 if all(x["status"] == "COMPLETED" for x in summary["project_handoffs"]) else 8


if __name__ == "__main__":
    raise SystemExit(main())
