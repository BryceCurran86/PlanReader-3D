#!/usr/bin/env python3
"""Structure-adjusted native graphic-state report for Item 35 candidates (diagnostic only).

For each PDF (and optional 0-based page scope) this publishes the same semantic
scope the Item 35 shadow publishes, hashes the caller-supplied bytes against the
scope's source SHA-256, joins the producer-owned graphic state to the visible
native primitives by exact producer identity (the Phase-2 join rows), and compares
participating paths with the rest of the candidate-page native paths inside strata
of path structure.  See ``pb_native_graphic_state_stratified`` for the groups, the
strata, the direct standardisation, the null control and the rules.

Inputs are PDF bytes and page indexes only.  No benchmark expectation, mapping,
tolerance or accepted row is read; nothing is scored; nothing is rejected,
filtered or merged; each document is reported on its own (never pooled).

usage: native_graphic_state_stratified_report.py PDF_OR_DIR [...] [--pages 0,1,...]
           [--output report.json] [--no-reference]
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

from pb_native_graphic_state_stratified import (  # noqa: E402
    STRATIFIED_SCHEMA_VERSION,
    collect_stratified_graphic_state_check,
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
    # Same derivation as the join and census reports, so the semantic scope (and
    # every id under it) is the one those reports were built on.
    return f"item35_funnel:{hashlib.sha256(payload).hexdigest()[:16]}"


def build_report(
    pdf_paths: Sequence[Path],
    *,
    pages: Optional[Sequence[int]] = None,
    with_reference: bool = True,
) -> dict[str, Any]:
    entries: list[tuple[str, str, dict[str, Any]]] = []
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
            "analysis_state": None,
            "stratified": None,
        }
        if not payload:
            entry["status"] = "source_unavailable"
        else:
            try:
                check = collect_stratified_graphic_state_check(
                    pdf_path,
                    document_id=document_id_for(payload),
                    pages=pages,
                    source_bytes=payload,  # the exact bytes that were hashed
                    with_reference=with_reference,
                )
                check_dict = check.to_dict()
                if check_dict["status"] != "ok":
                    entry["status"] = check_dict["status"]
                entry["stratified"] = check_dict
                # surfaced here so a partial analysis is not read as a complete one
                entry["analysis_state"] = (check_dict.get("integrity") or {}).get("analysis_state")
            except Exception as exc:  # reported, never swallowed silently
                entry["status"] = "error"
                entry["error"] = f"{type(exc).__name__}: {exc}"[:500]
        entries.append((digest, pdf_path.name, entry))
    entries.sort(key=lambda item: (item[0], item[1]))
    statuses = [entry["status"] for _, _, entry in entries]
    incomplete = [
        entry["label"]
        for _, _, entry in entries
        if entry["analysis_state"] not in (None, "complete")
    ]
    return {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "stratified_schema_version": STRATIFIED_SCHEMA_VERSION,
        "pooled": False,  # documents are never merged into one statistic
        "entries": [entry for _, _, entry in entries],
        "coverage": {
            "entries_total": len(statuses),
            "entries_ok": statuses.count("ok"),
            "entries_semantic_record_absent": statuses.count("semantic_record_absent"),
            "entries_sha_mismatch": statuses.count("no_join_sha_mismatch"),
            "entries_error": statuses.count("error"),
            "entries_source_unavailable": statuses.count("source_unavailable"),
            "entries_analysis_incomplete": len(incomplete),
            "analysis_incomplete_labels": sorted(incomplete),
        },
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
    parser.add_argument(
        "--no-reference",
        action="store_true",
        help="skip the #1059 structure cross-check of the candidate count",
    )
    args = parser.parse_args(argv)

    pdf_paths = expand_pdf_paths(args.paths)
    if not pdf_paths:
        print("no PDF files found", file=sys.stderr)
        return 2
    report = build_report(pdf_paths, pages=args.pages, with_reference=not args.no_reference)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        sys.stdout.write(text)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    coverage = report["coverage"]
    if coverage["entries_analysis_incomplete"]:
        print(
            "warning: analysis incomplete for "
            + ", ".join(coverage["analysis_incomplete_labels"])
            + " (see integrity.analysis_state)",
            file=sys.stderr,
        )
    # Non-zero when any entry failed or could not be read, so a partial run is
    # never mistaken for a complete one by a caller that only checks the exit code.
    return 1 if coverage["entries_error"] or coverage["entries_source_unavailable"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
