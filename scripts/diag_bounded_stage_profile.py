#!/usr/bin/env python3
"""TEST-ONLY bounded cProfile probe for exact-source PlanReader stages."""
from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
from pathlib import Path
import pstats
import signal
import time

from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_physical_scale_authority import PhysicalScaleProducer, PhysicalScaleSelector
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_visibility_authority import SourceVisibilityProducer


class StageTimeout(RuntimeError):
    pass


def _handler(_signum, _frame):
    raise StageTimeout("bounded_profile_timeout")


def _top_stats(profiler, limit=100):
    stats = pstats.Stats(profiler)
    rows = []
    for (filename, line, name), (cc, nc, tt, ct, _callers) in stats.stats.items():
        rows.append({
            "file": str(filename),
            "line": int(line),
            "function": str(name),
            "primitive_calls": int(cc),
            "total_calls": int(nc),
            "self_seconds": float(tt),
            "cumulative_seconds": float(ct),
        })
    rows.sort(key=lambda r: (-r["cumulative_seconds"], -r["self_seconds"], r["file"], r["line"]))
    return rows[:limit]


def _profile(fn, timeout_seconds):
    profiler = cProfile.Profile()
    timed_out = False
    error = None
    started = time.perf_counter()
    old_handler = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(timeout_seconds)
    profiler.enable()
    try:
        fn()
    except StageTimeout:
        timed_out = True
    except Exception as exc:
        error = f"{type(exc).__name__}:{exc}"
    finally:
        profiler.disable()
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
    elapsed = time.perf_counter() - started
    return {
        "elapsed_seconds": elapsed,
        "timed_out": timed_out,
        "error": error,
        "top_cumulative": _top_stats(profiler),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--page-start", type=int, required=True)
    parser.add_argument("--page-end", type=int, required=True)
    parser.add_argument("--mode", choices=("wall-candidates", "wall-opening", "scale"), required=True)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    path = Path(args.pdf)
    payload = path.read_bytes()
    sha = hashlib.sha256(payload).hexdigest()
    page_ids = tuple(str(i) for i in range(args.page_start, args.page_end + 1))
    source = SourceVisibilityProducer(
        producer_method="bounded-exact-source-profiler",
        producer_version="1",
    )
    ingest_start = time.perf_counter()
    published = source.ingest_native_pdf_bytes(
        document_id=f"profile:{args.project}:{sha[:24]}",
        source_bytes=payload,
        source_locator=f"memory://{path.name}",
        page_ids=page_ids,
    )
    ingest_seconds = time.perf_counter() - ingest_start

    if args.mode == "wall-candidates":
        def run():
            PhysicalWallCandidateProducer.from_source_visibility_producer(
                source,
                page_ids=page_ids,
            ).authority()
    elif args.mode == "wall-opening":
        def run():
            compose_live_wall_opening_authority(
                source_visibility_producer=source,
                revision_id=published.revision.revision_id,
                page_ids=page_ids,
            )
    else:
        def run():
            producer = PhysicalScaleProducer.from_source_visibility_producer(source)
            current = source.published_snapshot_for_revision(published.revision.revision_id)
            if current is None:
                raise RuntimeError("published snapshot unavailable")
            for page_id in page_ids:
                producer.publish_scope(
                    PhysicalScaleSelector(
                        document_id=current.revision.document_id,
                        revision_id=current.revision.revision_id,
                        source_sha256=current.revision.source_sha256,
                        snapshot_id=current.snapshot.snapshot_id,
                        page_id=page_id,
                        viewport_id=None,
                    )
                )

    profile = _profile(run, args.timeout_seconds)
    result = {
        "project": args.project,
        "mode": args.mode,
        "source_sha256": sha,
        "page_ids": page_ids,
        "source_ingest_seconds": ingest_seconds,
        **profile,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "project": args.project,
        "mode": args.mode,
        "ingest_seconds": ingest_seconds,
        "elapsed_seconds": profile["elapsed_seconds"],
        "timed_out": profile["timed_out"],
        "error": profile["error"],
        "top": profile["top_cumulative"][:12],
    }, indent=2))
    return 0 if profile["error"] is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
