"""Run the official four-project benchmark on this computer."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from contextlib import nullcontext
import multiprocessing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import NamedTemporaryFile
from time import perf_counter
from typing import Callable

from tools.gpt3_safe_original_report_output import preflight_new_diagnostic, publish_staged_file
from tools.report_gpt3_four_project_evidence import FROZEN_ROOT, main as report_evidence


_REPO = Path(__file__).resolve().parents[1]
_SETTINGS = ".planreader-benchmark.local.json"
_WINDOWS_ONLINE_CHECK = (
    "[Console]::WriteLine([int](@("
    "[System.Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces() | "
    "Where-Object { $_.NetworkInterfaceType -ne 'Loopback' "
    "-and $_.OperationalStatus -eq 'Up' }).Count -gt 0))"
)


def _require_local_offline() -> None:
    """Verify the local execution session is disconnected before extraction."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        raise ValueError("original-source benchmark execution is local only")
    if os.name == "nt":
        powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / (
            "System32/WindowsPowerShell/v1.0/powershell.exe"
        )
        result = subprocess.run(
            [str(powershell), "-NoProfile", "-NonInteractive", "-Command", _WINDOWS_ONLINE_CHECK],
            check=True, capture_output=True, text=True, timeout=15,
        )
        if result.stdout.strip() == "0":
            return
        if result.stdout.strip() != "1":
            raise ValueError("could not verify the local network state")
    else:
        interfaces = Path("/sys/class/net")
        if not interfaces.is_dir():
            raise ValueError("could not verify the local network state")
        if not any(
            dev.name != "lo" and int((dev / "flags").read_text(), 16) & 1
            for dev in interfaces.iterdir()
        ):
            return
    raise ValueError("original-source extraction requires a disconnected local session")


def _read_checkout_head() -> str:
    command = ["git", "-C", str(_REPO)]
    head = subprocess.check_output(
        [*command, "rev-parse", "--verify", "HEAD"], text=True, timeout=15,
    ).strip()
    status = subprocess.check_output(
        [*command, "status", "--porcelain", "--untracked-files=all"], text=True, timeout=15,
    )
    if status.strip():
        raise ValueError("benchmark checkout must be clean")
    return head


def _local_paths(args: argparse.Namespace) -> tuple[Path, Path, Path | None]:
    settings_path = args.config or _REPO / _SETTINGS
    if settings_path.is_file():
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        if type(settings) is not dict or any(
            name not in ("source_dir", "identity_map_dir", "run_root")
            or type(value) is not str or not value.strip()
            for name, value in settings.items()
        ):
            raise ValueError("invalid local benchmark configuration")
    elif args.config is not None:
        raise ValueError("local benchmark configuration file is unavailable")
    else:
        settings = {}

    source_dir = args.source_dir or settings.get("source_dir") or os.getenv(
        "PLANREADER_PRIVATE_SOURCE_ROOT"
    ) or _REPO / "documents" / "sources"
    identity_map_dir = args.identity_map_dir or settings.get("identity_map_dir")
    if identity_map_dir is None:
        raise ValueError("configure the local benchmark identity map directory")
    output_dir = args.output_dir
    if output_dir is None and not args.check_only:
        root = Path(settings.get("run_root") or Path.home() / "PlanReader" / "benchmark-runs")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output_dir = root / timestamp
    return Path(source_dir).expanduser(), Path(identity_map_dir).expanduser(), output_dir


def _check_local_inputs(source_dir: Path, identity_map_dir: Path) -> dict:
    from tools.gpt3_owner_all_source_role_handoff import PROJECTS, original_roster

    count = sum(len(original_roster(project, source_dir.resolve())) for project in PROJECTS)
    if count != 10:
        raise ValueError("expected ten authentic frozen benchmark sources")
    for project in PROJECTS:
        identity_map = identity_map_dir / f"{project}.identity_map.json"
        if not identity_map.is_file() or identity_map.is_symlink():
            raise ValueError("a required local identity map is unavailable")
    return {"source_files_verified": count, "identity_maps_present": len(PROJECTS)}


def _score_run(source_dir: Path, identity_map_dir: Path, evidence_dir: Path, output_dir: Path) -> int:
    return report_evidence([
        "--source-dir", str(source_dir), "--sealed-dir", str(evidence_dir / "sealed"),
        "--identity-map-dir", str(identity_map_dir), "--customer-dir", str(evidence_dir / "customer"),
        "--output", str(output_dir / "frozen120_score.json"),
    ])


def _publish_project_evidence(role_dir: Path, sealed_path: Path, customer_path: Path) -> None:
    """Stage both receipts before exposing complete copies to the scorer."""
    copies = (
        (role_dir / "ALL_SOURCE_ROLES.sealed.json", sealed_path),
        (role_dir / "ALL_SOURCE_ROLES.customer_rows.json", customer_path),
    )
    staged: list[tuple[Path, Path]] = []
    published: list[tuple[Path, os.stat_result]] = []
    try:
        for source, target in copies:
            with NamedTemporaryFile(
                "wb", dir=target.parent, prefix=".replay-", suffix=".tmp", delete=False,
            ) as stream:
                staged.append((Path(stream.name), target))
                with source.open("rb") as receipt:
                    shutil.copyfileobj(receipt, stream)
                stream.flush()
                os.fsync(stream.fileno())
        for stage, target in staged:
            identity = stage.lstat()
            publish_staged_file(stage, target)
            published.append((target, identity))
    except BaseException:
        for target, identity in published:
            try:
                still_ours = os.path.samestat(target.lstat(), identity)
            except FileNotFoundError:
                continue
            if still_ours:
                target.unlink(missing_ok=True)
        raise
    finally:
        for stage, _ in staged:
            stage.unlink(missing_ok=True)


def _produce_project(project: str, source_dir: Path, role_dir: Path, timeout_min: int) -> tuple[dict, dict]:
    """Run one isolated project; never publish benchmark evidence from a worker."""
    from tools.gpt3_owner_all_source_role_handoff import produce_all_source_roles

    started = perf_counter()
    print(f"Starting original-source replay for {project}", flush=True)
    status = {}
    try:
        status = produce_all_source_roles(
            project_id=project, source_dir=source_dir, output_dir=role_dir,
            timeout_min=timeout_min, record_native_source_input_coverage=True,
            source_native_finish_text_shadow=True, source_role_abstention_receipts=True,
        )
        outcome = {"project_id": project, "status": status["status"]}
        # Only carry the verified publication flags across the process boundary.
        status = {key: status.get(key) is True for key in (
            "native_source_input_coverage_verified",
            "source_role_coverage_verified",
            "customer_bijection_verified",
        )}
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        status = {}
        outcome = {"project_id": project, "status": "ROLE_REPLAY_FAILED",
                   "failure_type": type(exc).__name__}
    outcome["elapsed_seconds"] = round(perf_counter() - started, 3)
    return outcome, status


def run_benchmark(
    *, source_dir: Path, identity_map_dir: Path, output_dir: Path, timeout_min: int,
    saved_run_dir: Path | None = None,
    check_execution: Callable[[], None] | None = None,
    project_workers: int = 1,
) -> int:
    """Run independent projects in bounded batches, or re-score existing evidence."""
    if type(project_workers) is not int or project_workers not in (1, 2):
        raise ValueError("project_workers must be 1 or 2")
    if saved_run_dir is not None and project_workers != 1:
        raise ValueError("parallel workers require a fresh extraction")
    source_dir = source_dir.resolve()
    identity_map_dir = identity_map_dir.resolve()
    preflight_new_diagnostic(
        output_dir, protected_roots=(source_dir, identity_map_dir, _REPO, saved_run_dir),
    )
    if saved_run_dir is not None:
        saved_run_dir = saved_run_dir.resolve()
        if not (saved_run_dir / "sealed").is_dir() or not (saved_run_dir / "customer").is_dir():
            raise ValueError("saved run directory must contain sealed and customer directories")
        return _score_run(source_dir, identity_map_dir, saved_run_dir, output_dir)

    from tools.gpt3_owner_all_source_role_handoff import (
        PROJECTS, original_roster,
    )

    rosters = [original_roster(project, source_dir) for project in PROJECTS]
    if sum(map(len, rosters)) != 10:
        raise ValueError("expected ten authentic frozen benchmark sources")
    output_dir.mkdir(parents=True, exist_ok=False)
    output_dir = output_dir.resolve()
    sealed_dir = output_dir / "sealed"
    customer_dir = output_dir / "customer"
    sealed_dir.mkdir()
    customer_dir.mkdir()

    total_started = perf_counter()
    outcomes = []
    # PyMuPDF does not support concurrent threads. Spawn separate processes,
    # with at most two active projects; retain the serial default for low RAM.
    pool = (ProcessPoolExecutor(max_workers=project_workers,
                                mp_context=multiprocessing.get_context("spawn"))
            if project_workers > 1 else nullcontext(None))
    with pool as executor:
        for offset in range(0, len(PROJECTS), project_workers):
            batch = PROJECTS[offset:offset + project_workers]
            if check_execution is not None:
                check_execution()
            jobs = []
            if executor is not None:
                for project in batch:
                    role_dir = output_dir / "production" / project
                    jobs.append(executor.submit(
                        _produce_project, project, source_dir, role_dir, timeout_min,
                    ))
            for index, project in enumerate(batch):
                role_dir = output_dir / "production" / project
                outcome, status = (
                    jobs[index].result() if executor is not None
                    else _produce_project(project, source_dir, role_dir, timeout_min)
                )
                if check_execution is not None:
                    check_execution()
                try:
                    if (
                        status.get("native_source_input_coverage_verified") is True
                        and status.get("source_role_coverage_verified") is True
                        and status.get("customer_bijection_verified") is True
                    ):
                        _publish_project_evidence(
                            role_dir, sealed_dir / f"{project}.json",
                            customer_dir / f"{project}.customer_rows.json",
                        )
                except (OSError, TypeError, ValueError, RuntimeError) as exc:
                    outcome.update(status="ROLE_REPLAY_FAILED", failure_type=type(exc).__name__)
                outcomes.append(outcome)
                print(json.dumps(outcome, sort_keys=True), flush=True)
                status_path = output_dir / "attempt_status.json"
                staged = status_path.with_suffix(".tmp")
                staged.write_text(
                    json.dumps({"projects": outcomes, "elapsed_seconds": round(perf_counter() - total_started, 3)},
                               indent=2, sort_keys=True) + "\n", encoding="utf-8",
                )
                staged.replace(status_path)

    if check_execution is not None:
        check_execution()
    return _score_run(source_dir, identity_map_dir, output_dir, output_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("launcher", nargs="?", choices=("benchmark",), help=argparse.SUPPRESS)
    parser.add_argument("--config", type=Path, help="Local JSON settings file")
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--identity-map-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--check-only", action="store_true",
                        help="Verify the local original roster and map availability")
    parser.add_argument("--timeout-min", type=int, default=180,
                        help="Maximum extraction time per source document")
    parser.add_argument("--project-workers", type=int, choices=(1, 2), default=1,
                        help="Independent project processes (default 1; 2 needs sufficient RAM)")
    parser.add_argument("--saved-run-dir", type=Path,
                        help="Verify and re-score an existing sealed/customer run without extracting PDFs")
    args = parser.parse_args(argv)
    if args.timeout_min < 1:
        parser.error("--timeout-min must be positive")
    if args.project_workers != 1 and (args.check_only or args.saved_run_dir is not None):
        parser.error("--project-workers requires fresh extraction")
    if args.check_only and args.saved_run_dir is not None:
        parser.error("--check-only and --saved-run-dir are mutually exclusive")
    try:
        source_dir, identity_map_dir, output_dir = _local_paths(args)
        if args.check_only:
            print(json.dumps(_check_local_inputs(source_dir, identity_map_dir), sort_keys=True))
            return 0
        assert output_dir is not None
        if args.saved_run_dir is not None:
            return run_benchmark(
                source_dir=source_dir, identity_map_dir=identity_map_dir,
                output_dir=output_dir, timeout_min=args.timeout_min,
                saved_run_dir=args.saved_run_dir,
            )
        _require_local_offline()
        expected_head = _read_checkout_head()

        def check_execution() -> None:
            _require_local_offline()
            if _read_checkout_head() != expected_head:
                raise ValueError("benchmark checkout changed during execution")

        _check_local_inputs(source_dir, identity_map_dir)
        print(f"Local benchmark checkout {expected_head}", flush=True)
        return run_benchmark(
            source_dir=source_dir, identity_map_dir=identity_map_dir,
            output_dir=output_dir, timeout_min=args.timeout_min,
            check_execution=check_execution, project_workers=args.project_workers,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        parser.exit(2, f"Local benchmark could not run ({type(exc).__name__}).\n")
    except (TypeError, ValueError) as exc:
        parser.exit(2, f"Local benchmark could not run: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
