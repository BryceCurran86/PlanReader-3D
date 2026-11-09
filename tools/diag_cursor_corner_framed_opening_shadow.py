"""Private original-source SHADOW run of the raster corner framed-opening detector.

Reads one caller-held PDF, publishes the producer's raster opening primitives
for the requested pages, runs the shadow detector and writes the full result
to a new private file. Standard output carries sanitized counts only: no
coordinates, observation IDs or drawing content. Nothing here is takeoff,
host, frame, label or quantity authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pb_migration_contracts import EvidenceResolutionStatus  # noqa: E402
from pb_raster_corner_framed_opening_shadow import (  # noqa: E402
    detect_raster_corner_framed_openings_shadow,
)
from pb_source_visibility_authority import SourceVisibilityProducer  # noqa: E402
from tools.gpt3_safe_original_report_output import (  # noqa: E402
    preflight_new_diagnostic,
    write_new_diagnostic,
)


def run_corner_shadow(source_bytes: bytes, *, pages: tuple[int, ...]) -> dict:
    digest = hashlib.sha256(source_bytes).hexdigest()
    producer = SourceVisibilityProducer(
        producer_method="cursor-corner-framed-opening-shadow-diagnostic",
        producer_version="1",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=f"original-source:{digest[:32]}",
        source_bytes=source_bytes,
        source_locator="memory://private-original.pdf",
        page_ids=pages,
    )
    revision_id = published.revision.revision_id
    page_ids = tuple(str(page) for page in pages)
    producer.augment_with_raster_opening_primitives(revision_id, page_ids=page_ids)
    return {
        "source_sha256": digest,
        "pages": [
            detect_raster_corner_framed_openings_shadow(
                producer, revision_id=revision_id, page_id=page_id).to_dict()
            for page_id in page_ids
        ],
        "shadow_only": True,
        "takeoff_eligible": False,
    }


def sanitized_summary(report: dict) -> dict:
    pages = []
    for page in report["pages"]:
        nominations = page["nominations"]
        abstained = Counter(
            nomination["reason_codes"][0]
            for nomination in nominations
            if nomination["status"] == EvidenceResolutionStatus.ABSTAINED.value
        )
        pages.append({
            "page_id": page["page_id"],
            "status": page["status"],
            "reason_codes": page["reason_codes"],
            "candidate_count": sum(
                1 for nomination in nominations
                if nomination["status"] == EvidenceResolutionStatus.CANDIDATE.value),
            "abstained_by_reason": dict(sorted(abstained.items())),
            "rejected_geometric_corner_count": page["rejected_geometric_corner_count"],
        })
    return {
        "source_sha256": report["source_sha256"],
        "pages": pages,
        "shadow_only": True,
        "takeoff_eligible": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page", type=int, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if any(page < 1 for page in args.page):
        parser.error("--page is 1-based")
    roots = (ROOT, args.pdf)
    preflight_new_diagnostic(args.output, protected_roots=roots)
    report = run_corner_shadow(args.pdf.read_bytes(), pages=tuple(sorted(set(args.page))))
    write_new_diagnostic(
        args.output, json.dumps(report, indent=2, sort_keys=True) + "\n", protected_roots=roots)
    print(json.dumps(sanitized_summary(report), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
