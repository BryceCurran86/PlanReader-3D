from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz

from pb_physical_scale_authority import PhysicalScaleProducer, PhysicalScaleSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import (
    ViewportSegmentationStatus,
    segment_page_viewports,
)


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID = "3"


def _result_row(name, result):
    evidence = result.evidence
    return {
        "selector": name,
        "status": str(getattr(result.status, "value", result.status)),
        "reason_codes": list(result.reason_codes),
        "evidence": None if evidence is None else {
            "record_id": evidence.record_id,
            "source_kind": evidence.source_kind,
            "source_span_pt": evidence.source_span_pt,
            "physical_span_mm": evidence.physical_span_mm,
            "points_per_mm": evidence.points_per_mm,
            "mm_per_point": evidence.mm_per_point,
            "viewport_id": evidence.viewport_id,
        },
    }


def main() -> None:
    source_bytes = PDF.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    if source_sha != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {source_sha}")

    source = SourceVisibilityProducer(
        producer_method="diag_lot16_floor_plan_scale",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="diag-lot16-floor-plan-scale",
        source_bytes=source_bytes,
        source_locator=str(PDF),
        page_ids=(PAGE_ID,),
    )
    scale = PhysicalScaleProducer.from_source_visibility_producer(source)

    selectors = [("page", None)]
    with fitz.open(str(PDF)) as doc:
        page = doc.load_page(int(PAGE_ID) - 1)
        viewports = segment_page_viewports(page, page_number=int(PAGE_ID))
    viewport_rows = []
    for viewport in viewports:
        viewport_rows.append({
            "view_id": viewport.view_id,
            "view_type": viewport.view_type,
            "status": viewport.status,
            "bbox": None if viewport.bounding_box is None else list(viewport.bounding_box),
        })
        if (
            viewport.status == ViewportSegmentationStatus.RESOLVED.value
            and viewport.bounding_box is not None
        ):
            selectors.append((f"viewport:{viewport.view_id}", viewport.view_id))

    results = []
    for name, viewport_id in selectors:
        result = scale.publish_scope(PhysicalScaleSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id=PAGE_ID,
            viewport_id=viewport_id,
        ))
        results.append(_result_row(name, result))

    print(json.dumps({
        "source_sha256": source_sha,
        "page_id": PAGE_ID,
        "viewports": viewport_rows,
        "scale_results": results,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
