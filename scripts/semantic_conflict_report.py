#!/usr/bin/env python3
"""Conflict anatomy report for Item 35 semantic enumeration (diagnostic only).

For each PDF (and optional 0-based page scope) this publishes the same semantic
scope the Item 35 shadow publishes and explains, with the authorities' PUBLIC
results only, which observations are in ``conflict_observation_ids`` /
``residual_visible_observation_ids`` and which path put them there.  See
``pb_semantic_conflict_diagnostic`` for the paths and for what is reported as
unavailable.

Inputs are PDF bytes and page indexes only.  No benchmark expectation, mapping,
tolerance or accepted row is read; nothing is scored; no production behaviour,
extractor prediction or commercial output is touched; no identity is inferred
from counts.  ``document_id`` is derived from the PDF's content hash, the same
way as ``item35_stage_funnel_report``, so record ids do not depend on file names.

usage: semantic_conflict_report.py PDF_OR_DIR [...] [--pages 0,1,...]
           [--output report.json] [--detail summary|full] [--examples N]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pb_semantic_conflict_diagnostic import (  # noqa: E402
    SEMANTIC_CONFLICT_DIAGNOSTIC_SCHEMA_VERSION,
    SemanticConflictDiagnostic,
    aggregate_semantic_conflict_diagnostics,
    collect_semantic_conflict_diagnostic,
)

REPORT_SCHEMA_VERSION = "1.0.0"


def expand_pdf_paths(paths: Sequence[Path]) -> list[Path]:
    expanded: list[Path] = []
    for path in paths:
        if path.is_dir():
            expanded.extend(
                sorted(
                    item
                    for item in path.rglob("*")
                    if item.is_file() and item.suffix.lower() == ".pdf"
                )
            )
        else:
            expanded.append(path)
    return expanded


def document_id_for(payload: bytes) -> str:
    return f"item35_funnel:{hashlib.sha256(payload).hexdigest()[:16]}"


def illustrative_examples(
    diagnostic: SemanticConflictDiagnostic, per_relation: int = 3
) -> list[dict[str, Any]]:
    """A few conflicts per relation class, taken in observation-id order.

    Illustration only: the order-based pick is not a selection criterion and no
    conclusion is drawn from which observations appear here.
    """
    examples: list[dict[str, Any]] = []
    taken: dict[str, int] = {}
    for item in sorted(diagnostic.conflicts, key=lambda c: c.evidence.observation_id):
        key = f"{'+'.join(item.paths)}|{item.candidate_relation}"
        if taken.get(key, 0) >= per_relation:
            continue
        taken[key] = taken.get(key, 0) + 1
        examples.append(
            {
                "observation_id": item.evidence.observation_id,
                "page_id": item.evidence.page_id,
                "source_primitive_ref": item.evidence.source_primitive_ref,
                "geometry": list(item.evidence.geometry),
                "paths": list(item.paths),
                "candidate_relation": item.candidate_relation,
                "candidate_ids": list(item.disposition.candidate_ids),
                "proven_opening_record_ids": list(item.proven_opening_record_ids),
                "in_opening_support": item.in_opening_support,
                "in_closure_unresolved": item.in_closure_unresolved,
                "disposition_reason_codes": list(item.disposition.reason_codes),
            }
        )
    return examples


def build_report(
    pdf_paths: Sequence[Path],
    *,
    pages: Optional[Sequence[int]] = None,
    detail: str = "summary",
    examples: int = 3,
) -> dict[str, Any]:
    if detail not in {"summary", "full"}:
        raise ValueError("detail must be 'summary' or 'full'")
    entries: list[tuple[str, str, dict[str, Any], Optional[SemanticConflictDiagnostic]]] = []
    for pdf_path in pdf_paths:
        try:
            payload = pdf_path.read_bytes()
        except OSError:
            payload = b""
        digest = hashlib.sha256(payload).hexdigest() if payload else ""
        entry: dict[str, Any] = {
            "label": pdf_path.name,
            "pdf_sha256": digest or None,
            "pages_requested": list(pages) if pages is not None else None,
            "status": "ok",
            "error": None,
            "diagnostic": None,
            "summary": None,
            "examples": [],
        }
        diagnostic: Optional[SemanticConflictDiagnostic] = None
        if not payload:
            entry["status"] = "source_unavailable"
        else:
            try:
                diagnostic = collect_semantic_conflict_diagnostic(
                    pdf_path,
                    document_id=document_id_for(payload),
                    pages=pages,
                    source_bytes=payload,  # the exact bytes that were hashed
                )
            except Exception as exc:  # reported, never swallowed silently
                entry["status"] = "error"
                entry["error"] = f"{type(exc).__name__}: {exc}"[:500]
        if diagnostic is not None:
            if diagnostic.semantic_record_id is None:
                # The semantic authority published no record: report why, do not
                # present the scope as a clean one.
                entry["status"] = "semantic_record_absent"
                entry["semantic_status"] = diagnostic.semantic_status
                entry["semantic_reason_codes"] = list(diagnostic.semantic_reason_codes)
            entry["summary"] = aggregate_semantic_conflict_diagnostics([diagnostic])
            entry["examples"] = illustrative_examples(diagnostic, examples)
            if detail == "full":
                entry["diagnostic"] = diagnostic.to_dict()
        entries.append((digest, pdf_path.name, entry, diagnostic))
    entries.sort(key=lambda item: (item[0], item[1]))
    diagnostics = [diag for _, _, _, diag in entries if diag is not None]
    statuses = [entry["status"] for _, _, entry, _ in entries]
    return {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "diagnostic_schema_version": SEMANTIC_CONFLICT_DIAGNOSTIC_SCHEMA_VERSION,
        "entries": [entry for _, _, entry, _ in entries],
        # The summary covers only entries that produced a diagnostic; this says
        # how many did not, so a partial result cannot read as a complete one.
        "coverage": {
            "entries_total": len(statuses),
            "entries_with_semantic_record": statuses.count("ok"),
            "entries_without_semantic_record": statuses.count("semantic_record_absent"),
            "entries_error": statuses.count("error"),
            "entries_source_unavailable": statuses.count("source_unavailable"),
        },
        "summary": aggregate_semantic_conflict_diagnostics(diagnostics),
    }


def _parse_pages(text: str) -> list[int]:
    try:
        pages = sorted({int(part) for part in text.split(",") if part.strip()})
    except ValueError:
        raise argparse.ArgumentTypeError("--pages must be comma-separated integers")
    if not pages or pages[0] < 0:
        raise argparse.ArgumentTypeError("--pages needs at least one 0-based index")
    return pages


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--pages", type=_parse_pages, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--detail", choices=("summary", "full"), default="summary")
    parser.add_argument("--examples", type=int, default=3)
    args = parser.parse_args(argv)

    pdf_paths = expand_pdf_paths(args.paths)
    if not pdf_paths:
        print("no PDF files found", file=sys.stderr)
        return 2
    report = build_report(
        pdf_paths, pages=args.pages, detail=args.detail, examples=args.examples
    )
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        sys.stdout.write(text)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    coverage = report["coverage"]
    # Non-zero when any entry failed or could not be read, so a partial run is
    # never mistaken for a complete one by a caller that only checks the exit code.
    return 1 if coverage["entries_error"] or coverage["entries_source_unavailable"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
