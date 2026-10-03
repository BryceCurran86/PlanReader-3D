#!/usr/bin/env python3
"""Per-page wall-scope funnel report (diagnostic only).

For each requested page this reports, from PUBLIC authority results only, how
native segments reduce through the generic drafting / annotation-mask filter
and what the physical-wall-candidate scope then decides:

    raw native segments -> proven annotation-mask edges -> filtered segments
    -> scope status / scope_complete / reason codes / candidate records

A page whose scope is not CORROBORATED, not ``scope_complete`` or has no
records yields no canonical walls in ``compose_live_canonical_walls``; the
reason codes printed here are therefore the first thing to read when
``physical wall candidates -> canonical walls`` collapses to zero.

Inputs are PDF bytes and 1-based page ids only.  No benchmark expectation,
mapping, tolerance or accepted row is read; nothing is scored; no production
behaviour, extractor prediction or commercial output is touched; no identity is
inferred from counts.  ``document_id`` derives from the PDF content hash, so
record ids do not depend on file names.

usage: wall_scope_funnel_report.py PDF [--pages 1,2,...] [--output report.json]
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

import fitz  # noqa: E402

import pb_physical_wall_candidate_authority as wall_candidates  # noqa: E402
from pb_source_visibility_authority import SourceVisibilityProducer  # noqa: E402
from pb_vector_geometry_v130 import extract_native_page  # noqa: E402


def wall_scope_funnel(
    pdf_bytes: bytes,
    page_ids: Optional[Sequence[str]] = None,
) -> dict[str, Any]:
    """Return the per-page funnel for ``pdf_bytes`` (read-only)."""

    digest = hashlib.sha256(pdf_bytes).hexdigest()
    producer = SourceVisibilityProducer(
        producer_method="wall-scope-funnel-report", producer_version="1"
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=f"funnel-{digest[:16]}",
        source_bytes=pdf_bytes,
        source_locator=f"memory://{digest[:16]}.pdf",
    )
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        pages = tuple(str(p) for p in page_ids) if page_ids else tuple(
            str(index + 1) for index in range(len(doc))
        )
        authority = wall_candidates.PhysicalWallCandidateProducer.from_source_visibility_producer(
            producer, page_ids=pages
        ).authority()
        mask_proof = hasattr(wall_candidates, "_annotate_producer_owned_annotation_masks")
        receipts_by_page = (
            wall_candidates._text_receipts_by_page(
                source_producer=producer, published=published
            )
            if hasattr(wall_candidates, "_text_receipts_by_page")
            else {}
        )
        rows = []
        for page_id in pages:
            page = doc[int(page_id) - 1]
            width, height = wall_candidates.native_wall_scope_page_extent(page)
            segments = list(extract_native_page(page)["segments"])
            raw = len(segments)
            masks = 0
            if mask_proof:
                annotated = wall_candidates._annotate_producer_owned_annotation_masks(
                    segments, text_receipts=receipts_by_page.get(page_id, ())
                )
                masks = sum(
                    1
                    for segment in annotated
                    if wall_candidates._is_proven_annotation_mask_edge(segment)
                )
                segments = list(annotated)
            filtered = wall_candidates.filtered_wall_topology_source_segment_count(
                segments, page_width=width, page_height=height
            )
            scope = authority.resolve_scope(
                wall_candidates.PhysicalWallCandidateSelector(
                    document_id=published.revision.document_id,
                    revision_id=published.revision.revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    page_id=page_id,
                    decision_scope_id=f"wall-source:page-{page_id}",
                )
            )
            rows.append(
                {
                    "page_id": page_id,
                    "raw_segments": raw,
                    "annotation_mask_edges_proven": masks,
                    "filtered_segments": filtered,
                    "scope_status": scope.status.value,
                    "scope_complete": bool(scope.scope_complete),
                    "candidate_records": len(scope.records),
                    "reason_codes": list(scope.reason_codes),
                    "complexity_exceeded": (
                        wall_candidates.PHYSICAL_WALL_CANDIDATE_SCOPE_COMPLEXITY_EXCEEDED
                        in scope.reason_codes
                    ),
                    "yields_canonical_walls": bool(
                        scope.status.value == "corroborated"
                        and scope.scope_complete
                        and scope.records
                    ),
                }
            )
    finally:
        doc.close()
    return {
        "source_sha256": digest,
        "mask_proof_available": mask_proof,
        "max_topology_segments": wall_candidates.MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS,
        "pages": rows,
        "candidate_records_total": sum(r["candidate_records"] for r in rows),
        "pages_yielding_canonical_walls": sum(
            1 for r in rows if r["yields_canonical_walls"]
        ),
    }


def _format(report: dict[str, Any]) -> str:
    lines = [
        f"mask proof available: {report['mask_proof_available']} | "
        f"max topology segments: {report['max_topology_segments']}",
        f"{'page':>4} {'raw':>8} {'mask':>6} {'filtered':>8} {'status':>12} "
        f"{'complete':>8} {'records':>7} {'walls?':>6}  reason_codes",
    ]
    for r in report["pages"]:
        lines.append(
            f"{r['page_id']:>4} {r['raw_segments']:>8} "
            f"{r['annotation_mask_edges_proven']:>6} {r['filtered_segments']:>8} "
            f"{r['scope_status']:>12} {str(r['scope_complete']):>8} "
            f"{r['candidate_records']:>7} {str(r['yields_canonical_walls']):>6}  "
            f"{','.join(r['reason_codes'])}"
        )
    lines.append(
        f"candidate records: {report['candidate_records_total']} | pages that can "
        f"yield canonical walls: {report['pages_yielding_canonical_walls']}"
    )
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("pdf")
    parser.add_argument("--pages", default="", help="comma-separated 1-based page ids")
    parser.add_argument("--output", default="", help="write the JSON report here")
    args = parser.parse_args(argv)
    pages = [p.strip() for p in args.pages.split(",") if p.strip()]
    report = wall_scope_funnel(Path(args.pdf).read_bytes(), pages or None)
    print(_format(report))
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
