#!/usr/bin/env python3
"""TEST-ONLY driver: run the candidate provenance census on real sources.

Not for merge.  Orchestrates ``pb_candidate_provenance_census`` (the PR under
test): for one SHA-verified PDF it censuses the document scope in a child process
with a timeout (and, only if that fails, a sample of drawing pages).  It reads no
benchmark gold / expected value / tolerance / mapping, scores nothing and writes
nothing to the repository.  The caller SHA-verifies the PDF; this driver never
downloads.

  run    <pdf> --label L --out DIR
  merge  <dir> [<dir> ...]     aggregate the pickled censuses of many sources
"""
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import pickle
import queue
import sys
import time
from pathlib import Path
from typing import Any, Optional, Sequence

ROOT = (
    Path(__file__).resolve().parents[1]
    if (Path(__file__).resolve().parents[1] / "pb_candidate_provenance_census.py").exists()
    else Path.cwd()
)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import fitz  # noqa: E402

from pb_candidate_provenance_census import (  # noqa: E402
    aggregate_candidate_provenance_censuses,
    collect_candidate_provenance_census,
)


def _worker(pdf: str, document_id: str, pages: Optional[list[int]], out: "mp.Queue") -> None:
    try:
        out.put(("ok", collect_candidate_provenance_census(pdf, document_id=document_id, pages=pages), None))
    except BaseException as exc:  # reported, never swallowed silently
        out.put(("error", None, f"{type(exc).__name__}: {exc}"[:500]))


def run_isolated(pdf: Path, document_id: str, pages: Optional[list[int]], timeout_s: float) -> dict[str, Any]:
    ctx = mp.get_context("fork")
    out = ctx.Queue()
    proc = ctx.Process(target=_worker, args=(str(pdf), document_id, pages, out))
    started = time.monotonic()
    proc.start()
    try:
        kind, census, message = out.get(timeout=timeout_s)
        status = "ok" if kind == "ok" else "error"
    except queue.Empty:
        census, message, status = None, None, "timeout"
    finally:
        if proc.is_alive():
            proc.terminate()
        proc.join(30)
    return {"status": status, "census": census, "error": message,
            "elapsed_s": round(time.monotonic() - started, 1)}


def headline(census: dict[str, Any]) -> dict[str, Any]:
    """Compact, source-independent summary of one census (for the log)."""
    groups = {}
    for name, block in census["groups"].items():
        groups[name] = {
            "candidates": block["candidates_total"],
            "incomplete": block["provenance_incomplete"],
            "path_class": block["path_class"],
            "distinct_paths": block["distinct_paths_per_candidate"],
            "draw_order": block["draw_order"],
            "incidences": block["member_incidences"],
        }
    obs = census["ambiguous_observations"]
    checks = census["consistency"]["checks"]
    return {
        "pages": census["pages"]["enumerated"],
        "pages_unavailable": census["pages"]["unavailable"],
        "groups": groups,
        "ambiguous_obs": {
            "assessed": obs["assessed"],
            "concentration": obs["path_concentration"],
            "incomplete": obs["provenance_incomplete"],
            "raster": obs["raster_involved"],
        },
        "anomalies": census["anomalies"]["counts"],
        "checks_all_passed": census["consistency"]["all_checks_passed"],
        "checks_failing": sorted(name for name, ok in checks.items() if ok is False),
        "checks_not_run": sorted(name for name, ok in checks.items() if ok is None),
    }


def trimmed_examples(census: dict[str, Any], cells: int = 3) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for group, block in census["examples"]["candidates"].items():
        picked = {}
        for cell in block["dominant_cells"][:cells]:
            entries = block["by_cell"].get(cell) or []
            if not entries:
                continue
            entry = entries[0]
            picked[cell] = {
                "page": entry["page_id"],
                "distinct_paths": entry["distinct_paths"],
                "members": [
                    [m["source_primitive_ref"], m["length_band"], m["length"]]
                    for m in entry["members"]
                ],
            }
        out[group] = {"dominant_cells": block["dominant_cells"], "examples": picked}
    return out


def _line(scope: str, label: str, page: Optional[int], ops: Optional[int], result: dict[str, Any]) -> str:
    census = result["census"]
    if census is None:
        return (f"{scope} label={label} page={page} ops={ops} status={result['status']} "
                f"elapsed={result['elapsed_s']}s error={result['error']!r}")
    data = census.to_dict()
    return (f"{scope} label={label} page={page} ops={ops} status={data['status']} "
            f"elapsed={result['elapsed_s']}s headline="
            + json.dumps(headline(data), sort_keys=True, separators=(",", ":")))


def cmd_run(args: argparse.Namespace) -> int:
    pdf = Path(args.pdf)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = pdf.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    document_id = f"item35_funnel:{digest[:16]}"
    doc = fitz.open(str(pdf))
    page_count = doc.page_count
    ops: list[int] = []
    for index in range(page_count):
        try:
            ops.append(len(doc[index].get_drawings()))
        except Exception:
            ops.append(-1)
    doc.close()
    candidates = [i for i, n in enumerate(ops) if n >= args.min_drawing_ops]
    print(f"=== SOURCE {args.label} sha256={digest} pages={page_count} "
          f"page_candidates(>={args.min_drawing_ops} vector ops)={len(candidates)}", flush=True)

    records: list[dict[str, Any]] = []

    def record(scope: str, page: Optional[int], op_count: Optional[int], result: dict[str, Any]) -> None:
        print(_line(scope, args.label, page, op_count, result), flush=True)
        records.append({"scope": scope, "page": page, "drawing_ops": op_count,
                        "status": result["status"], "error": result["error"],
                        "elapsed_s": result["elapsed_s"], "census": result["census"]})
        if result["census"] is not None:
            print("EXAMPLES " + json.dumps(
                {"label": args.label, "scope": scope, "page": page,
                 **trimmed_examples(result["census"].to_dict())},
                sort_keys=True, separators=(",", ":")), flush=True)

    doc_result = run_isolated(pdf, document_id, None, args.doc_timeout)
    record("DOC", None, None, doc_result)
    skipped = 0
    if doc_result["census"] is None:
        # The document scope did not complete: fall back to a sample of pages so the
        # source is not silently absent.  Reported as PAGE scopes, never as the document.
        budget_end = time.monotonic() + args.page_budget
        for index in candidates:
            if time.monotonic() >= budget_end:
                skipped += 1
                continue
            record("PAGE", index + 1, ops[index], run_isolated(pdf, document_id, [index], args.page_timeout))
    with (out_dir / f"census_{args.label}.pkl").open("wb") as handle:
        pickle.dump({"label": args.label, "pdf_sha256": digest, "page_count": page_count,
                     "drawing_ops_per_page": ops, "page_candidates": [i + 1 for i in candidates],
                     "skipped_by_budget": skipped, "records": records}, handle)
    print(f"=== DONE {args.label}: doc_status={doc_result['status']} "
          f"fallback_pages={len([r for r in records if r['scope'] == 'PAGE'])} skipped_by_budget={skipped}",
          flush=True)
    return 0


def _emit(tag: str, value: Any) -> None:
    print(f"{tag} {json.dumps(value, sort_keys=True, separators=(',', ':'))}", flush=True)


def cmd_merge(args: argparse.Namespace) -> int:
    payloads = []
    for directory in args.dirs:
        for path in sorted(Path(directory).rglob("census_*.pkl")):
            with path.open("rb") as handle:
                payloads.append(pickle.load(handle))
    payloads.sort(key=lambda item: item["label"])
    _emit("SOURCES", [{"label": p["label"], "pdf_sha256": p["pdf_sha256"], "pages": p["page_count"],
                       "page_candidates": len(p["page_candidates"]), "skipped_by_budget": p["skipped_by_budget"]}
                      for p in payloads])
    for scope, tag in (("DOC", "DOCUMENT"), ("PAGE", "PAGE")):
        everything = []
        for p in payloads:
            recs = [r for r in p["records"] if r["scope"] == scope]
            tally: dict[str, int] = {}
            for r in recs:
                tally[r["status"]] = tally.get(r["status"], 0) + 1
            _emit(f"TALLY_{tag}_{p['label']}", dict(sorted(tally.items())))
            censuses = [r["census"] for r in recs if r["census"] is not None]
            everything.extend(censuses)
            if censuses:
                _emit(f"PROJECT_{tag}_{p['label']}", aggregate_candidate_provenance_censuses(censuses))
        _emit(f"AGGREGATE_{tag}", aggregate_candidate_provenance_censuses(everything))
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("pdf")
    run.add_argument("--label", required=True)
    run.add_argument("--out", required=True)
    run.add_argument("--min-drawing-ops", type=int, default=50)
    run.add_argument("--doc-timeout", type=float, default=6600.0)
    run.add_argument("--page-timeout", type=float, default=900.0)
    run.add_argument("--page-budget", type=float, default=2400.0)
    run.set_defaults(func=cmd_run)
    merge = sub.add_parser("merge")
    merge.add_argument("dirs", nargs="+")
    merge.set_defaults(func=cmd_merge)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
