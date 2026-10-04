"""SHADOW DIFF: F.07 viewports vs the title-block floor-plan viewport proposal.

Diagnostic only. For every selected page of a PDF it records what the REAL,
unmodified F.07 ``segment_page_viewports`` returns and what the shadow
``pb_title_block_viewport_shadow`` proposes, plus how they relate:

* ``shadow_adds_floor_plan``  F.07 has no floor-plan viewport and the shadow has one candidate
* ``f07_floor_plan_stands``   F.07 already has a floor-plan viewport; the shadow defers
* ``shadow_ambiguous`` / ``shadow_conflict`` / ``shadow_abstains``  nothing is proposed

It changes no authority, publishes no quantity, writes nothing (JSON goes to
stdout only), reads no filename, page number or coordinate as evidence, and is
imported by no production module. The source is identified by its SHA-256.

CLI:  python scripts/title_block_viewport_shadow_diff.py --pdf FILE [--pages 1,2,3]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import fitz  # noqa: E402

from pb_drawing_evidence_binding import DrawingViewType  # noqa: E402
from pb_migration_contracts import EvidenceResolutionStatus  # noqa: E402
from pb_title_block_viewport_shadow import (  # noqa: E402
    TITLE_BLOCK_VIEWPORT_F07_FLOOR_PLAN_PRESENT,
    propose_title_block_floor_plan_viewport,
)
from pb_viewport_segmentation import segment_page_viewports  # noqa: E402


def _relation(proposal: Any) -> str:
    if proposal.is_candidate:
        return "shadow_adds_floor_plan"
    if TITLE_BLOCK_VIEWPORT_F07_FLOOR_PLAN_PRESENT in proposal.reason_codes:
        return "f07_floor_plan_stands"
    if proposal.ambiguous:
        return "shadow_ambiguous"
    if proposal.status is EvidenceResolutionStatus.CONFLICT:
        return "shadow_conflict"
    return "shadow_abstains"


def diff_pdf(path: Path, pages: Optional[Sequence[int]] = None) -> dict[str, Any]:
    payload = path.read_bytes()
    doc = fitz.open(stream=payload, filetype="pdf")
    try:
        selected = (
            [p for p in pages if 1 <= p <= len(doc)]
            if pages
            else list(range(1, len(doc) + 1))
        )
        rows: list[dict[str, Any]] = []
        counts: dict[str, int] = {}
        started = time.perf_counter()
        for page_number in selected:
            page = doc[page_number - 1]
            page_started = time.perf_counter()
            f07 = segment_page_viewports(page, page_number=page_number)
            proposal = propose_title_block_floor_plan_viewport(
                page, page_number=page_number, f07_viewports=f07
            )
            relation = _relation(proposal)
            counts[relation] = counts.get(relation, 0) + 1
            rows.append(
                {
                    "page_number": page_number,
                    "relation": relation,
                    "f07_viewports": [
                        {
                            "view_type": v.view_type,
                            "status": v.status,
                            "has_bounding_box": v.bounding_box is not None,
                        }
                        for v in f07
                    ],
                    "f07_has_floor_plan": any(
                        v.view_type == DrawingViewType.FLOOR_PLAN.value
                        and v.bounding_box is not None
                        for v in f07
                    ),
                    "shadow": proposal.to_dict(),
                    "seconds": round(time.perf_counter() - page_started, 3),
                }
            )
        return {
            "source_sha256": hashlib.sha256(payload).hexdigest(),
            "page_count": len(doc),
            "pages_examined": len(selected),
            "relation_counts": counts,
            "live_change": False,
            "seconds": round(time.perf_counter() - started, 3),
            "pages": rows,
        }
    finally:
        doc.close()


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--pages", default="", help="comma separated 1-based pages")
    args = parser.parse_args(argv)
    pages = [int(p) for p in args.pages.split(",") if p.strip()] or None
    print(json.dumps(diff_pdf(args.pdf, pages), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
