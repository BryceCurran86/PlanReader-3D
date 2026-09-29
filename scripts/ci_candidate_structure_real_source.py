#!/usr/bin/env python3
"""TEST-ONLY driver: run the semantic conflict diagnostic on real sources.

Not for merge.  Orchestrates ``pb_semantic_conflict_diagnostic`` (the PR under
test): for one SHA-verified PDF it diagnoses the document scope and a sample of
drawing pages, each in a child process with a timeout.  It reads no benchmark
gold / expected value / tolerance / mapping, scores nothing and writes nothing
to the repository.  The caller SHA-verifies the PDF; this driver never downloads.

  run    <pdf> --label L --out DIR
  merge  <dir> [<dir> ...]     aggregate the pickled diagnostics of many sources
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

ROOT = Path(__file__).resolve().parents[1] if (Path(__file__).resolve().parents[1] / "pb_semantic_conflict_diagnostic.py").exists() else Path.cwd()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import fitz  # noqa: E402

from pb_semantic_conflict_diagnostic import (  # noqa: E402
    aggregate_semantic_conflict_diagnostics,
    collect_semantic_conflict_diagnostic,
)


def _worker(pdf: str, document_id: str, pages: Optional[list[int]], out: "mp.Queue") -> None:
    try:
        out.put(("ok", collect_semantic_conflict_diagnostic(pdf, document_id=document_id, pages=pages), None))
    except BaseException as exc:  # reported, never swallowed silently
        out.put(("error", None, f"{type(exc).__name__}: {exc}"[:500]))


def run_isolated(pdf: Path, document_id: str, pages: Optional[list[int]], timeout_s: float) -> dict[str, Any]:
    ctx = mp.get_context("fork")
    out = ctx.Queue()
    proc = ctx.Process(target=_worker, args=(str(pdf), document_id, pages, out))
    started = time.monotonic()
    proc.start()
    try:
        kind, diagnostic, message = out.get(timeout=timeout_s)
        status = "ok" if kind == "ok" else "error"
    except queue.Empty:
        diagnostic, message, status = None, None, "timeout"
    finally:
        if proc.is_alive():
            proc.terminate()
        proc.join(30)
    return {"status": status, "diagnostic": diagnostic, "error": message,
            "elapsed_s": round(time.monotonic() - started, 1)}


def _structure_line(agg: dict) -> str:
    cs = agg["candidate_structure"]
    return json.dumps({k: cs[k] for k in (
        "pages_enumerated", "pages_unavailable", "candidates_total", "variant_families_total",
        "observations_in_candidates", "observations_in_multiple_candidates",
        "candidates_with_strict_superset", "candidates_with_identical_member_set",
        "ambiguous_observations_assessed", "disposition_candidate_id_mismatches",
        "ambiguous_observation_family_span", "variant_family_sizes")},
        sort_keys=True, separators=(",", ":"))


def _length(geometry) -> float:
    return ((geometry[2] - geometry[0]) ** 2 + (geometry[3] - geometry[1]) ** 2) ** 0.5 if len(geometry) == 4 else -1.0


def _quantiles(values):
    values = sorted(values)
    if not values:
        return None
    pick = lambda q: round(values[min(len(values) - 1, int(q * len(values)))], 1)
    return {"n": len(values), "min": round(values[0], 1), "p50": pick(0.5), "p90": pick(0.9), "max": round(values[-1], 1)}


def span_lengths(diag) -> dict:
    # Descriptive: segment length of ambiguous conflicting observations, split by
    # how many variant families their candidates span (member sets only).
    groups: dict = {}
    for item in diag.conflicts:
        if item.candidate_family_count is None:
            key = "unavailable"
        elif item.candidate_family_count >= 3:
            key = "3+"
        else:
            key = str(item.candidate_family_count)
        groups.setdefault(key, []).append(_length(item.evidence.geometry))
    return {key: _quantiles(vals) for key, vals in sorted(groups.items())}


def examples(diag, per_class: int = 2) -> list:
    taken: dict = {}
    out = []
    for item in sorted(diag.conflicts, key=lambda c: c.evidence.observation_id):
        key = (item.candidate_family_count, item.in_opening_support)
        if taken.get(key, 0) >= per_class:
            continue
        taken[key] = taken.get(key, 0) + 1
        out.append({
            "observation_id": item.evidence.observation_id, "page": item.evidence.page_id,
            "kind": item.evidence.observation_kind, "geometry": list(item.evidence.geometry),
            "length": round(_length(item.evidence.geometry), 1),
            "candidates": len(item.disposition.candidate_ids),
            "family_count": item.candidate_family_count, "in_opening_support": item.in_opening_support,
            "paths": list(item.paths)})
    return out[:8]


def _one_line(label: str, scope: str, page: Optional[int], ops: Optional[int], result: dict[str, Any]) -> str:
    diag = result["diagnostic"]
    if diag is None:
        return f"{scope} label={label} page={page} ops={ops} status={result['status']} elapsed={result['elapsed_s']}s error={result['error']!r}"
    agg = aggregate_semantic_conflict_diagnostics([diag])
    return (f"{scope} label={label} page={page} ops={ops} elapsed={result['elapsed_s']}s "
            f"semantic={diag.semantic_status} counts={diag.counts_dict()} "
            f"paths={agg['conflict_path_observation_counts']} relations={agg['ambiguous_candidate_relation_counts']} "
            f"clusters={agg['conflict_clusters']['count']} closure_incomplete_pages={agg['closure']['pages_incomplete']} "
            f"rep_unresolvable={agg['proven_openings_with_unresolvable_representative']}/{agg['proven_openings_total']} "
            f"unattributed={agg['unattributed_observations']} consistent={diag.rederivation_consistent} "
            f"structure={_structure_line(agg)}")


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
    print(f"=== SOURCE {args.label} sha256={digest} pages={page_count} page_candidates(>={args.min_drawing_ops} vector ops)={len(candidates)}", flush=True)

    records: list[dict[str, Any]] = []

    def record(scope: str, page: Optional[int], op_count: Optional[int], result: dict[str, Any]) -> None:
        print(_one_line(args.label, scope, page, op_count, result), flush=True)
        records.append({"scope": scope, "page": page, "drawing_ops": op_count,
                        "status": result["status"], "error": result["error"],
                        "elapsed_s": result["elapsed_s"], "diagnostic": result["diagnostic"]})

    record("DOC", None, None, run_isolated(pdf, document_id, None, args.doc_timeout))
    budget_end = time.monotonic() + args.page_budget
    skipped = 0
    for index in candidates:
        if time.monotonic() >= budget_end:
            skipped += 1
            continue
        record("PAGE", index + 1, ops[index], run_isolated(pdf, document_id, [index], args.page_timeout))

    # Illustrative relationships (observation-id order; no selection criterion).
    for entry in records:
        diag = entry["diagnostic"]
        if diag is not None and diag.conflicts:
            print("EXAMPLES", json.dumps({"label": args.label, "scope": entry["scope"], "page": entry["page"],
                                          "examples": examples(diag), "span_lengths": span_lengths(diag)},
                                         sort_keys=True, separators=(",", ":")), flush=True)
            if entry["scope"] == "DOC":
                break
    with (out_dir / f"diag_{args.label}.pkl").open("wb") as handle:
        pickle.dump({"label": args.label, "pdf_sha256": digest, "page_count": page_count,
                     "drawing_ops_per_page": ops, "page_candidates": [i + 1 for i in candidates],
                     "skipped_by_budget": skipped, "records": records}, handle)
    print(f"=== DONE {args.label}: candidates={len(candidates)} skipped_by_budget={skipped}", flush=True)
    return 0


def _emit(tag: str, value: Any) -> None:
    print(f"{tag} {json.dumps(value, sort_keys=True, separators=(',', ':'))}", flush=True)


_KEYS = (
    "scope_count", "scopes_with_conflict", "semantic_status_counts",
    "conflict_observations_total", "conflict_path_observation_counts", "conflict_path_scope_counts",
    "conflict_path_exclusive_observation_counts", "conflict_path_combination_counts",
    "dominant_conflict_paths_by_observations", "dominant_conflict_paths_by_scopes",
    "conflict_disposition_reason_code_counts", "conflict_visible_reason_code_counts",
    "ambiguous_candidates_per_conflict", "ambiguous_candidate_relation_counts",
    "ambiguous_proven_openings_per_observation", "ambiguous_candidate_pair_shared_observations",
    "conflict_clusters", "residual_observations_total", "residual_path_counts",
    "residual_disposition_reason_code_counts", "closure", "proven_openings_total",
    "proven_openings_with_unresolvable_representative", "unresolvable_representative_reason_code_counts",
    "unattributed_observations", "unavailable_scope_counts", "candidate_structure",
)


def cmd_merge(args: argparse.Namespace) -> int:
    payloads = []
    for directory in args.dirs:
        for path in sorted(Path(directory).rglob("diag_*.pkl")):
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
            diags = [r["diagnostic"] for r in recs if r["diagnostic"] is not None]
            everything.extend(diags)
            if diags:
                agg = aggregate_semantic_conflict_diagnostics(diags)
                _emit(f"PROJECT_{tag}_{p['label']}", {k: agg[k] for k in _KEYS})
        agg = aggregate_semantic_conflict_diagnostics(everything)
        _emit(f"AGGREGATE_{tag}", {k: agg[k] for k in _KEYS})
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("pdf")
    run.add_argument("--label", required=True)
    run.add_argument("--out", required=True)
    run.add_argument("--min-drawing-ops", type=int, default=50)
    run.add_argument("--doc-timeout", type=float, default=3600.0)
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
