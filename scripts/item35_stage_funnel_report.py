#!/usr/bin/env python3
"""Stage-wise Item 35 funnel report (diagnostic only, gold-free).

Runs ``collect_item35_authority_shadow`` exactly once per PDF and feeds the
returned shadow dictionary to ``pb_item35_stage_funnel``.  The funnel never
re-runs an authority, so this is the single diagnostic execution path.  A
shadow that raises is turned into the same ``shadow_exception:<Type>`` shell
the live extractor uses.

Inputs are PDF bytes (and optional page indexes) only.  No benchmark
expectation, mapping, tolerance, accepted row or extractor prediction is read,
nothing is written to the repository, and no commercial output is produced or
changed.  Per-opening existence, identity and host-binding stages are reported
as unobserved because the shadow does not expose them.

usage: item35_stage_funnel_report.py PDF_OR_DIR [PDF_OR_DIR ...]
           [--pages 0,1,...] [--output report.json]

``--pages`` takes 0-based page indexes, exactly as ``collect_item35_authority_shadow``.
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

from pb_item35_production_authority_shadow import (  # noqa: E402
    collect_item35_authority_shadow,
    empty_item35_authority_shadow,
)
from pb_item35_stage_funnel import (  # noqa: E402
    ITEM35_STAGE_FUNNEL_SCHEMA_VERSION,
    Item35StageFunnel,
    aggregate_item35_stage_funnels,
    build_item35_stage_funnel,
)

REPORT_SCHEMA_VERSION = "1.0.0"


def expand_pdf_paths(paths: Sequence[Path]) -> list[Path]:
    """Files as given; directories expand to their ``*.pdf`` files, recursively."""
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


def collect_shadow(
    pdf_path: Path, *, pages: Optional[Sequence[int]] = None
) -> tuple[dict[str, Any], Optional[str]]:
    """Run the Item 35 shadow once; return it with the PDF's content hash.

    The document id is derived from the bytes, so ids and funnel record ids do
    not depend on where the file lives or what it is called.
    """
    try:
        payload = pdf_path.read_bytes()
    except OSError:
        payload = b""
    digest = hashlib.sha256(payload).hexdigest() if payload else None
    document_id = f"item35_funnel:{digest[:16]}" if digest else None
    try:
        shadow = collect_item35_authority_shadow(
            pdf_path, document_id=document_id, pages=pages
        )
    except Exception as exc:  # mirrors the live extractor's call site
        shadow = empty_item35_authority_shadow(
            reason=f"shadow_exception:{type(exc).__name__}"
        )
    return shadow, digest


def build_report(
    pdf_paths: Sequence[Path], *, pages: Optional[Sequence[int]] = None
) -> dict[str, Any]:
    funnels: list[tuple[Item35StageFunnel, dict[str, Any]]] = []
    for pdf_path in pdf_paths:
        shadow, digest = collect_shadow(pdf_path, pages=pages)
        funnel = build_item35_stage_funnel(shadow)
        funnels.append(
            (
                funnel,
                {
                    "label": pdf_path.name,
                    "pdf_sha256": digest,
                    "pages_requested": list(pages) if pages is not None else None,
                    "funnel": funnel.to_dict(),
                },
            )
        )
    funnels.sort(
        key=lambda item: (
            item[1]["pdf_sha256"] or "",
            item[1]["label"],
            item[0].record_id,
        )
    )
    return {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "funnel_schema_version": ITEM35_STAGE_FUNNEL_SCHEMA_VERSION,
        "entries": [entry for _, entry in funnels],
        "summary": aggregate_item35_stage_funnels(funnel for funnel, _ in funnels),
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
    parser.add_argument("paths", nargs="+", type=Path, help="PDF files or directories")
    parser.add_argument("--pages", type=_parse_pages, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    pdf_paths = expand_pdf_paths(args.paths)
    if not pdf_paths:
        print("no PDF files found", file=sys.stderr)
        return 2
    report = build_report(pdf_paths, pages=args.pages)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        sys.stdout.write(text)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
