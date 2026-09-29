#!/usr/bin/env python3
"""Drawing-path provenance census report for Item 35 candidates (diagnostic only).

For each PDF (and optional 0-based page scope) this publishes the same semantic
scope the Item 35 shadow publishes and describes, from the producer-owned
``source_primitive_ref`` alone, which native PDF drawing path each member of each
physical-opening candidate comes from.  See ``pb_candidate_provenance_census`` for
the grammar, the schema and the rules.

Inputs are PDF bytes and page indexes only.  No benchmark expectation, mapping,
tolerance or accepted row is read; nothing is scored; no candidate is rejected,
filtered or merged; no production behaviour, extractor prediction or commercial
output is touched.  ``document_id`` is derived from the PDF's content hash, the
same way as ``semantic_conflict_report``.

usage: candidate_provenance_census_report.py PDF_OR_DIR [...] [--pages 0,1,...]
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

from pb_candidate_provenance_census import (  # noqa: E402
    CENSUS_SCHEMA_VERSION,
    CandidateProvenanceCensus,
    aggregate_candidate_provenance_censuses,
    collect_candidate_provenance_census,
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


def build_report(
    pdf_paths: Sequence[Path],
    *,
    pages: Optional[Sequence[int]] = None,
    with_reference: bool = True,
) -> dict[str, Any]:
    entries: list[tuple[str, str, dict[str, Any], Optional[CandidateProvenanceCensus]]] = []
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
            "census": None,
        }
        census: Optional[CandidateProvenanceCensus] = None
        if not payload:
            entry["status"] = "source_unavailable"
        else:
            try:
                census = collect_candidate_provenance_census(
                    pdf_path,
                    document_id=document_id_for(payload),
                    pages=pages,
                    source_bytes=payload,  # the exact bytes that were hashed
                    with_reference=with_reference,
                )
            except Exception as exc:  # reported, never swallowed silently
                entry["status"] = "error"
                entry["error"] = f"{type(exc).__name__}: {exc}"[:500]
        if census is not None:
            census_dict = census.to_dict()
            if census_dict["status"] != "ok":
                entry["status"] = census_dict["status"]
            entry["census"] = census_dict
        entries.append((digest, pdf_path.name, entry, census))
    entries.sort(key=lambda item: (item[0], item[1]))
    censuses = [c for _, _, _, c in entries if c is not None]
    statuses = [entry["status"] for _, _, entry, _ in entries]
    return {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "census_schema_version": CENSUS_SCHEMA_VERSION,
        "entries": [entry for _, _, entry, _ in entries],
        # The summary covers only entries that produced a census; this says how
        # many did not, so a partial result cannot read as a complete one.
        "coverage": {
            "entries_total": len(statuses),
            "entries_with_semantic_record": statuses.count("ok"),
            "entries_without_semantic_record": statuses.count("semantic_record_absent"),
            "entries_error": statuses.count("error"),
            "entries_source_unavailable": statuses.count("source_unavailable"),
        },
        "summary": aggregate_candidate_provenance_censuses(censuses),
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
        help="skip the #1059 structure cross-check (those checks are then reported null)",
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
    # Non-zero when any entry failed or could not be read, so a partial run is
    # never mistaken for a complete one by a caller that only checks the exit code.
    return 1 if coverage["entries_error"] or coverage["entries_source_unavailable"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
