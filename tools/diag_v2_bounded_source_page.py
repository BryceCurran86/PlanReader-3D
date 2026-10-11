"""Isolated original-PDF page runtime diagnostics; never takeoff or benchmark truth.

Each selected page is executed in its own child process so slow/hanging native
PDF extraction can be stopped and diagnosed without polluting other pages.
Results are explicitly unsealed, incomplete source *diagnostics* only. They
are never an authority to narrow production page scope, certify a source
universe, or publish a customer quantity or V2 score.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import fitz


SCHEMA = "v2-page-runtime-diagnostic-1"


def _rss_kb(pid: int) -> int | None:
    try:
        data = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    for line in data.splitlines():
        if line.startswith("VmRSS:"):
            fields = line.split()
            if len(fields) == 3 and fields[2] == "kB":
                return int(fields[1])
    return None


def _watch(process: subprocess.Popen, *, timeout_seconds: float, rss_limit_mb: int) -> dict:
    """Bound CPU/native process failures externally; no child result is trusted."""
    started = time.monotonic()
    peak_kb = 0
    reason = None
    while process.poll() is None:
        kb = _rss_kb(process.pid)
        if kb is not None:
            peak_kb = max(peak_kb, kb)
            if kb > rss_limit_mb * 1024:
                reason = "RSS_LIMIT_EXCEEDED"
        if reason is None and time.monotonic() - started >= timeout_seconds:
            reason = "TIMEOUT"
        if reason is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            break
        time.sleep(0.05)
    try:
        code = process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        code = process.wait(timeout=2)
        reason = reason or "CHILD_DID_NOT_EXIT"
    if reason is None:
        reason = "COMPLETED" if code == 0 else "CHILD_FAILED"
    return {
        "outcome": reason,
        "exit_code": code,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "peak_rss_kb_observed": peak_kb,
    }


def _worker(pdf_path: Path, page_index: int) -> None:
    from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim

    # A single original page is an *incomplete* cross-document production
    # universe, even when the producer can prove an individual source object.
    claim = collect_live_physical_net_wall_claim(
        pdf_path, pages=(page_index,), topology_pages=(page_index,),
    )
    print(json.dumps({
        "diagnostic_only": True,
        "physical_wall_candidates": len(claim.canonical_walls),
        "canonical_opening_count_observed": len(claim.canonical_openings),
        "status": getattr(claim.status, "value", str(claim.status)),
        "benchmark_score_granted": False,
    }), flush=True)


def _verify_original(path: Path, expected_sha256: str | None) -> tuple[str, int]:
    if not path.is_file() or path.is_symlink():
        raise ValueError("original PDF missing or symlinked")
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected_sha256 is not None and sha != expected_sha256:
        raise ValueError("original source SHA mismatch")
    with fitz.open(path) as doc:
        count = len(doc)
    return sha, count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--page-index", type=int, action="append", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=25.0)
    parser.add_argument("--rss-limit-mb", type=int, default=900)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if (
        not 0 < args.timeout_seconds <= 600
        or not 100 <= args.rss_limit_mb <= 16384
        or len(args.page_index) > 50
        or len(args.page_index) != len(set(args.page_index))
    ):
        parser.error("invalid diagnostic time, memory or distinct page constraints")
    if args.expected_sha256 is not None and (
        len(args.expected_sha256) != 64
        or any(c not in "0123456789abcdef" for c in args.expected_sha256)
    ):
        parser.error("source SHA-256 must be lowercase 64-digit hex")
    sha, page_count = _verify_original(args.pdf, args.expected_sha256)
    if any(i < 0 or i >= page_count for i in args.page_index):
        parser.error("page index outside original PDF")
    if args.worker:
        if len(args.page_index) != 1:
            parser.error("child worker must have one selected page")
        _worker(args.pdf, args.page_index[0])
        return 0

    rows = []
    report = {
        "schema_version": SCHEMA,
        "diagnostic_only": True,
        "benchmark_score_granted": False,
        "sealed_run_file": None,
        "identity_map_file": None,
        "complete_source_coverage_proven": False,
        "original_source_sha256": sha,
        "original_page_count": page_count,
        "pages": rows,
    }
    for page_index in args.page_index:
        if hashlib.sha256(args.pdf.read_bytes()).hexdigest() != sha:
            raise RuntimeError("original source changed during diagnostic")
        cmd = [
            sys.executable, "-m", "tools.diag_v2_bounded_source_page", "--pdf", str(args.pdf.resolve()),
            "--expected-sha256", sha,
            "--page-index", str(page_index),
            "--timeout-seconds", str(args.timeout_seconds),
            "--rss-limit-mb", str(args.rss_limit_mb), "--worker",
        ]
        proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        result = _watch(proc, timeout_seconds=args.timeout_seconds,
                        rss_limit_mb=args.rss_limit_mb)
        if hashlib.sha256(args.pdf.read_bytes()).hexdigest() != sha:
            raise RuntimeError("original source changed during diagnostic")
        rows.append({"source_page_index": page_index, **result})
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            temporary = args.output.with_suffix(args.output.suffix + ".tmp")
            temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, args.output)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
