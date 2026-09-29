#!/usr/bin/env python3
"""TEST-ONLY diagnostic driver: run the #1041 Item 35 stage funnel on real sources.

Not part of production and not for merge.  It only orchestrates
``scripts/item35_stage_funnel_report`` (PR #1041): the shadow is run once per
(source, scope) through ``collect_item35_authority_shadow`` and the result is
fed to ``build_item35_stage_funnel``.  No authority is run here, no benchmark
expectation / mapping / tolerance / accepted row is read, nothing is scored, and
nothing is written to the repository.  The caller must SHA-256-verify the PDF
first; this driver never downloads.

  run    <pdf> --label L --out DIR   document-scope funnel + per-page funnels
  merge  <dir> [<dir> ...]           aggregate the run outputs with the official aggregator

Scopes: ``document`` (pages=None, what the live extractor uses by default) and
``page`` (pages=[i], what it uses when pages are passed; this adds raster
visible segments for that page).  Pages are sampled only by a cheap native
vector-op count, so text-only BOQ pages do not masquerade as drawings; the count
is recorded for every page so the cut can be re-sliced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import queue
import sys
import time
from pathlib import Path
from typing import Any, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1] if (Path(__file__).resolve().parents[1] / "pb_item35_stage_funnel.py").exists() else Path.cwd()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import fitz  # noqa: E402

from pb_item35_production_authority_shadow import (  # noqa: E402
    collect_item35_authority_shadow,
    empty_item35_authority_shadow,
)
from pb_item35_stage_funnel import (  # noqa: E402
    Item35StageFunnel,
    StageObservation,
    aggregate_item35_stage_funnels,
    build_item35_stage_funnel,
)
from pb_migration_contracts import EvidenceResolutionStatus  # noqa: E402


# ----------------------------------------------------------------- isolation
def _worker(pdf: str, pages: Optional[list[int]], out: "mp.Queue") -> None:
    try:
        payload = Path(pdf).read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        try:
            shadow = collect_item35_authority_shadow(
                pdf, document_id=f"item35_funnel:{digest[:16]}", pages=pages
            )
            message = None
        except Exception as exc:  # mirrors the live extractor's call site
            shadow = empty_item35_authority_shadow(
                reason=f"shadow_exception:{type(exc).__name__}"
            )
            message = f"{type(exc).__name__}: {exc}"[:500]
        out.put(("ok", shadow, digest, message))
    except BaseException as exc:  # pragma: no cover - defensive
        out.put(("error", None, None, f"{type(exc).__name__}: {exc}"[:500]))


def run_isolated(pdf: Path, pages: Optional[list[int]], timeout_s: float) -> dict[str, Any]:
    """One shadow execution in a child process, killed after ``timeout_s``."""
    ctx = mp.get_context("fork")
    out = ctx.Queue()
    proc = ctx.Process(target=_worker, args=(str(pdf), pages, out))
    started = time.monotonic()
    proc.start()
    try:
        kind, shadow, digest, message = out.get(timeout=timeout_s)
        status = "ok" if kind == "ok" else "error"
    except queue.Empty:
        kind, shadow, digest, message, status = "timeout", None, None, None, "timeout"
    finally:
        if proc.is_alive():
            proc.terminate()
        proc.join(30)
    return {
        "status": status,
        "shadow": shadow,
        "pdf_sha256": digest,
        "shadow_exception_message": message,
        "elapsed_s": round(time.monotonic() - started, 1),
    }


def _entry(scope: str, page: Optional[int], ops: Optional[int], result: dict[str, Any]) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "scope": scope,
        "page": page,  # 1-based
        "drawing_ops": ops,
        "status": result["status"],
        "elapsed_s": result["elapsed_s"],
        "shadow_exception_message": result["shadow_exception_message"],
        "funnel": None,
        "funnel_error": None,
    }
    if result["status"] == "ok":
        try:
            entry["funnel"] = build_item35_stage_funnel(result["shadow"]).to_dict()
        except Exception as exc:  # a real shadow the funnel refuses is itself a finding
            entry["funnel_error"] = f"{type(exc).__name__}: {exc}"[:500]
    return entry


# ----------------------------------------------------------------------- run
def cmd_run(args: argparse.Namespace) -> int:
    pdf = Path(args.pdf)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
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

    entries: list[dict[str, Any]] = []
    entries.append(_entry("document", None, None, run_isolated(pdf, None, args.doc_timeout)))
    print("DOC", _compact(entries[-1]), flush=True)

    budget_end = time.monotonic() + args.page_budget
    skipped = 0
    for index in candidates:
        if time.monotonic() >= budget_end:
            skipped += 1
            continue
        entries.append(_entry("page", index + 1, ops[index], run_isolated(pdf, [index], args.page_timeout)))
        print("PAGE", _compact(entries[-1]), flush=True)

    payload = {
        "label": args.label,
        "pdf_sha256": digest,
        "page_count": page_count,
        "min_drawing_ops": args.min_drawing_ops,
        "drawing_ops_per_page": ops,
        "page_candidates": [i + 1 for i in candidates],
        "page_candidates_skipped_by_budget": skipped,
        "entries": entries,
    }
    (out_dir / f"funnels_{args.label}.json").write_text(
        json.dumps(payload, sort_keys=True), encoding="utf-8"
    )
    print(f"=== DONE {args.label}: candidates={len(candidates)} skipped_by_budget={skipped}", flush=True)
    return 0


def _compact(entry: dict[str, Any]) -> str:
    funnel = entry["funnel"]
    if funnel is None:
        return (f"scope={entry['scope']} page={entry['page']} ops={entry['drawing_ops']} "
                f"status={entry['status']} elapsed={entry['elapsed_s']}s "
                f"funnel_error={entry['funnel_error']!r} msg={entry['shadow_exception_message']!r}")
    rows = {row["stage"]: row for row in funnel["stages"]}
    first = funnel["first_blocker_stage"]
    codes = rows[first]["reason_codes"] if first else []
    visible = rows["source_visibility"]["output_count"]
    openings = rows["semantic_opening_enumeration"]["output_count"]
    generic = rows["generic_count_publication"]
    return (f"scope={entry['scope']} page={entry['page']} ops={entry['drawing_ops']} "
            f"elapsed={entry['elapsed_s']}s shadow={funnel['shadow_status']}/{funnel['shadow_reason']} "
            f"first_blocker={first} first_unobserved={funnel['first_unobserved_stage']} "
            f"codes={codes} visible={visible} openings={openings} "
            f"generic={generic['status']}:{generic['output_count']} "
            f"msg={entry['shadow_exception_message']!r}")


# --------------------------------------------------------------------- merge
def _rebuild(d: dict[str, Any]) -> Item35StageFunnel:
    def row(r: dict[str, Any]) -> StageObservation:
        return StageObservation(
            stage=r["stage"],
            observed=r["observed"],
            status=EvidenceResolutionStatus(r["status"]) if r["status"] else None,
            input_count=r["input_count"],
            output_count=r["output_count"],
            complete=r["complete"],
            blocking=r["blocking"],
            reason_codes=tuple(r["reason_codes"]),
            detail_counts=tuple(sorted(r["detail_counts"].items())),
            not_observed_reason=r["not_observed_reason"],
        )

    return Item35StageFunnel(
        record_id=d["record_id"],
        shadow_schema_version=d["shadow_schema_version"],
        shadow_status=d["shadow_status"],
        shadow_reason=d["shadow_reason"],
        document_id=d["document_id"],
        revision_id=d["revision_id"],
        source_sha256=d["source_sha256"],
        snapshot_id=d["snapshot_id"],
        semantic_record_id=d["semantic_record_id"],
        stages=tuple(row(r) for r in d["stages"]),
        unobserved_identity_stages=tuple(row(r) for r in d["unobserved_identity_stages"]),
        blocking_stages=tuple(d["blocking_stages"]),
        first_blocker_stage=d["first_blocker_stage"],
        first_unobserved_stage=d["first_unobserved_stage"],
        shadow_reported_commercial_count_unlocked=d["shadow_reported_commercial_count_unlocked"],
        commercial_authority_granted=d["commercial_authority_granted"],
        schema_version=d["schema_version"],
    )


_SUMMARY_KEYS = (
    "funnel_count",
    "dominant_first_blocker_stages",
    "first_blocker_stage_counts",
    "first_blocker_reason_code_counts",
    "first_unobserved_stage_counts",
    "undetermined_funnel_count",
    "no_observed_blocker_funnel_count",
    "shadow_status_counts",
    "shadow_reason_counts",
    "shadow_reported_commercial_count_unlocked_count",
    "unobserved_identity_stages",
    "commercial_authority_granted",
)


def _emit(tag: str, value: Any) -> None:
    print(f"{tag} {json.dumps(value, sort_keys=True, separators=(',', ':'))}", flush=True)


def _tally(entries: Sequence[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for entry in entries:
        key = entry["status"] if entry["funnel"] is not None or entry["status"] != "ok" else "ok"
        if entry["status"] == "ok" and entry["funnel"] is None:
            key = "funnel_error"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def cmd_merge(args: argparse.Namespace) -> int:
    payloads = []
    for directory in args.dirs:
        for path in sorted(Path(directory).rglob("funnels_*.json")):
            payloads.append(json.loads(path.read_text(encoding="utf-8")))
    payloads.sort(key=lambda item: item["label"])
    _emit("SOURCES", [
        {"label": p["label"], "pdf_sha256": p["pdf_sha256"], "pages": p["page_count"],
         "page_candidates": len(p["page_candidates"]),
         "skipped_by_budget": p["page_candidates_skipped_by_budget"]}
        for p in payloads
    ])

    for scope in ("document", "page"):
        funnels: list[Item35StageFunnel] = []
        per_project: dict[str, list[Item35StageFunnel]] = {}
        for p in payloads:
            scoped = [e for e in p["entries"] if e["scope"] == scope]
            _emit(f"TALLY_{scope.upper()}_{p['label']}", _tally(scoped))
            for e in scoped:
                if e["funnel"] is not None:
                    f = _rebuild(e["funnel"])
                    funnels.append(f)
                    per_project.setdefault(p["label"], []).append(f)
        summary = aggregate_item35_stage_funnels(funnels)
        _emit(f"AGGREGATE_{scope.upper()}", {k: summary[k] for k in _SUMMARY_KEYS})
        _emit(f"PER_STAGE_{scope.upper()}", summary["per_stage"])
        for label, items in sorted(per_project.items()):
            s = aggregate_item35_stage_funnels(items)
            _emit(f"PROJECT_{scope.upper()}_{label}", {k: s[k] for k in (
                "funnel_count", "dominant_first_blocker_stages", "first_blocker_stage_counts",
                "first_blocker_reason_code_counts", "first_unobserved_stage_counts",
                "undetermined_funnel_count", "no_observed_blocker_funnel_count", "shadow_reason_counts")})
    # Pages by first blocker (project, page) for the page scope.
    table = []
    for p in payloads:
        for e in p["entries"]:
            if e["scope"] == "page" and e["funnel"] is not None:
                fun = e["funnel"]
                rows = {r["stage"]: r for r in fun["stages"]}
                first = fun["first_blocker_stage"]
                table.append([p["label"], e["page"], e["drawing_ops"], first,
                              rows[first]["reason_codes"] if first else [],
                              rows["source_visibility"]["output_count"],
                              rows["semantic_opening_enumeration"]["output_count"]])
    _emit("PAGE_TABLE(project,page,ops,first_blocker,codes,visible,openings)", table)
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("pdf")
    run.add_argument("--label", required=True)
    run.add_argument("--out", required=True)
    run.add_argument("--min-drawing-ops", type=int, default=50)
    run.add_argument("--doc-timeout", type=float, default=1800.0)
    run.add_argument("--page-timeout", type=float, default=300.0)
    run.add_argument("--page-budget", type=float, default=1800.0)
    run.set_defaults(func=cmd_run)
    merge = sub.add_parser("merge")
    merge.add_argument("dirs", nargs="+")
    merge.set_defaults(func=cmd_merge)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
