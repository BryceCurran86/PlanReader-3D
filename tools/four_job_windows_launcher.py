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
* v2 writes ``SHARE_SAFE_STATUS.json`` with no local paths, so it can be pasted
  into the coordination issue without exposing the owner's folder names.

It is a diagnostic harness. A completed single-document handoff is not a complete
source-closed project, not a signed quantity and not an official score.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import venv
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


def note(message: str) -> None:
    print(message, flush=True)


def output_report(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _children_by_parent() -> dict[int, list[int]]:
    """POSIX only: parent pid -> child pids, read from /proc."""
    children: dict[int, list[int]] = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text(encoding="utf-8", errors="replace")
            ppid = int(stat.rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            continue
        children.setdefault(ppid, []).append(int(entry.name))
    return children


def sample_memory_kb(pid: int) -> tuple[int, int, int | None]:
    """(working set KB, private KB, system free commit KB or None) for ``pid`` and all its descendants.

    A Windows virtual environment's ``python.exe`` is only a launcher that starts the real interpreter as a
    child, so sampling ``pid`` alone reads the launcher (a few MB). The whole process tree is summed.
    Failure to sample returns zeros, never an exception: a missing measurement must not stop a run.
    """
    try:
        if os.name == "nt":
            script = (
                "$all = Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,WorkingSetSize,PrivatePageCount;"
                f"$ids = [System.Collections.Generic.HashSet[int]]::new(); [void]$ids.Add({int(pid)});"
                "do { $n = $ids.Count; foreach ($p in $all) { if ($ids.Contains([int]$p.ParentProcessId)) "
                "{ [void]$ids.Add([int]$p.ProcessId) } } } while ($ids.Count -ne $n);"
                "$ws = 0; $pv = 0; foreach ($p in $all) { if ($ids.Contains([int]$p.ProcessId)) "
                "{ $ws += [int64]$p.WorkingSetSize; $pv += [int64]$p.PrivatePageCount } };"
                "$free = (Get-CimInstance Win32_OperatingSystem).FreeVirtualMemory;"
                '"$ws $pv $free"'
            )
            result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                                    capture_output=True, text=True, check=False, timeout=60)
            ws, private, free_kb = result.stdout.split()[:3]
            return int(ws) // 1024, int(private) // 1024, int(free_kb)
        children = _children_by_parent()
        pids, stack = set(), [int(pid)]
        while stack:
            current = stack.pop()
            if current not in pids:
                pids.add(current)
                stack.extend(children.get(current, ()))
        rss_kb = 0
        for current in pids:
            try:
                for line in Path(f"/proc/{current}/status").read_text().splitlines():
                    if line.startswith("VmRSS:"):
                        rss_kb += int(line.split()[1])
            except OSError:
                continue
        free_kb = None
        meminfo = {line.split(":")[0]: int(line.split()[1]) for line in Path("/proc/meminfo").read_text().splitlines()}
        if "MemAvailable" in meminfo:
            free_kb = meminfo["MemAvailable"] + meminfo.get("SwapFree", 0)
        return rss_kb, rss_kb, free_kb
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return 0, 0, None


def kill_tree(proc: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, check=False)
    else:
        proc.kill()
    proc.wait()


def run_logged(
    args: list[str], cwd: Path, log: Path, *, timeout_s: int = 1800, track_memory: bool = False,
    poll_s: float = 15, max_private_mb: int | None = None, min_free_commit_mb: int | None = None,
) -> tuple[int | None, str, dict]:
    """Run ``args`` under hard limits. Returns (exit code, status, usage).

    Status is COMPLETED, PROCESS_FAILED, TIMEOUT, MEMORY_LIMIT (the process tree's private memory exceeded
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
        proc = subprocess.Popen(args, cwd=cwd, stdout=fh, stderr=subprocess.STDOUT)
        started = time.monotonic()
        while True:
            try:
                rc = proc.wait(timeout=poll_s)
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


def verify_originals(kit: Path, report_dir: Path) -> bool:
    manifest = json.loads((kit / "LOCAL_SOURCE_INVENTORY.json").read_text(encoding="utf-8-sig"))
    entries = manifest.get("docs")
    if (manifest.get("benchmark_id") != "full_plan_takeoff_reconciliation_v2"
            or not isinstance(entries, list) or len(entries) != 10):
        raise ValueError("Expected exactly the ten original Full Plan V2 sources")
    statuses = []
    for item in entries:
        project, filename = item["project_id"], item["manifest_name"]
        if project not in PROJECTS or not filename.lower().endswith(".pdf") or Path(filename).name != filename:
            raise ValueError("Unsafe source inventory entry")
        path = kit / "sources" / project / filename
        if not path.is_file() or path.is_symlink():
            status = "MISSING"
        else:
            payload = path.read_bytes()
            status = ("VERIFIED" if len(payload) == item["expected_size_bytes"]
                      and hashlib.sha256(payload).hexdigest() == item["original_sha256"] else "MISMATCH")
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


def refresh_snapshot(repo: Path, runs: Path, session: Path, ref: str) -> str | None:
    """Clone on first use; afterwards fetch ``ref`` and check it out detached. Returns HEAD or None."""
    if not repo.exists():
        note("Step 2: obtaining a private local copy of the public PlanReader code (no upload)")
        rc, _, _ = run_logged(["git", "clone", "--depth", "1", "--branch", "main", REPO_URL, str(repo)], runs,
                              session / "git_clone.log", timeout_s=900)
        if rc != 0:
            note(f"Unable to clone repository. See {session / 'git_clone.log'}; check Git and internet access.")
            return None
    elif not (repo / ".git").exists():
        note(f"Expected Git repository but found unrelated directory: {repo}. No files changed.")
        return None
    note(f"Step 2: refreshing the dedicated snapshot to {ref}")
    log = session / "git_refresh.log"
    # A shallow v1 snapshot is fetched at the requested ref only; nothing outside the snapshot changes.
    fetch = git(["fetch", "--depth", "1", "origin", ref], repo)
    log.write_text(fetch.stdout + fetch.stderr, encoding="utf-8")
    if fetch.returncode != 0:
        note(f"Could not fetch {ref}; see {log}. Using the snapshot as it is.")
    else:
        checkout = git(["checkout", "--detach", "FETCH_HEAD"], repo)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(checkout.stdout + checkout.stderr)
        if checkout.returncode != 0:
            note(f"Could not check out {ref}; see {log}.")
            return None
    return git(["rev-parse", "HEAD"], repo).stdout.strip()


def share_safe(status: dict, home: str) -> dict:
    """Same content with the owner's local paths removed."""
    text = json.dumps(status).replace(home.replace("\\", "\\\\"), "<HOME>").replace(home, "<HOME>")
    return json.loads(text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source-only", action="store_true",
                        help="Verify bundled files only; skip network, packages and production")
    parser.add_argument("--ref", default="main", help="Branch or commit of the public repository to run (default main)")
    parser.add_argument("--only", nargs="*", choices=PROJECTS, help="Run production for these projects only")
    parser.add_argument("--timeout-min", type=int, default=180, help="Per-project production limit in minutes")
    parser.add_argument("--stack-dump-min", type=int, default=10, help="Dump Python stacks this often (minutes)")
    parser.add_argument("--max-private-gb", type=float, default=10.0,
                        help="Stop a project whose process tree commits more private memory than this (MEMORY_LIMIT)")
    parser.add_argument("--min-free-commit-gb", type=float, default=3.0,
                        help="Stop a project when the machine's free commit falls below this (SYSTEM_MEMORY_GUARD)")
    opts = parser.parse_args()
    projects = tuple(opts.only) if opts.only else PROJECTS

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
    if not verify_originals(kit, session):
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
        "per_project_timeout_min": opts.timeout_min,
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
        bootstrap = (
            "import faulthandler, sys, runpy\n"
            f"f = open(r'{out}/stack_dumps.txt', 'a')\n"
            f"faulthandler.dump_traceback_later({max(1, opts.stack_dump_min) * 60}, repeat=True, file=f)\n"
            f"sys.argv = ['run_source_closed_project_handoff', '--pdf', r'{pdf}', '--project-id', '{project}',\n"
            f"            '--family-group', 'all', '--output-dir', r'{out}']\n"
            "runpy.run_module('tools.run_source_closed_project_handoff', run_name='__main__', alter_sys=True)\n"
        )
        note(f"  Starting {project} (max {opts.timeout_min} minutes; log in the logs folder)")
        started = time.monotonic()
        rc, status, usage = run_logged([str(python), "-u", "-c", bootstrap], repo,
                                       session / "logs" / f"{project}.handoff.log",
                                       timeout_s=opts.timeout_min * 60, track_memory=True,
                                       max_private_mb=int(opts.max_private_gb * 1024),
                                       min_free_commit_mb=int(opts.min_free_commit_gb * 1024))
        summary["project_handoffs"].append({
            "project_id": project, "status": status, "exit_code": rc,
            "elapsed_s": round(time.monotonic() - started, 1),
            "peak_working_set_mb_sampled": round(usage["peak_working_set_kb"] / 1024, 1),
            "peak_private_mb_sampled": round(usage["peak_private_kb"] / 1024, 1),
            "min_system_free_commit_mb_sampled": (None if usage["min_system_free_commit_kb"] is None
                                                  else round(usage["min_system_free_commit_kb"] / 1024, 1)),
            "single_document_handoff_only": True, "output_folder": str(out),
        })
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
