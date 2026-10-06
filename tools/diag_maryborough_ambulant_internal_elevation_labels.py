from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz

from pb_drawing_evidence_binding import DrawingViewType
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import (
    ViewportSegmentationStatus,
    is_authoritative_derived_viewport,
    segment_page_viewports,
    validate_non_overlapping_viewports,
)

SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
PAGE_ID = "27"
TARGETS = ("M-AMB", "F-AMB")

def norm(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())

def center(bbox):
    x0, y0, x1, y1 = [float(v) for v in bbox]
    return ((x0+x1)*0.5, (y0+y1)*0.5)

def inside(point, bbox):
    x, y = point
    x0, y0, x1, y1 = [float(v) for v in bbox]
    return x0 < x < x1 and y0 < y < y1

def main() -> int:
    payload=SOURCE.read_bytes()
    source_sha=hashlib.sha256(payload).hexdigest()
    source=SourceVisibilityProducer(
        producer_method="gpt2-ambulant-internal-elevation-label-diag",
        producer_version="1",
    )
    published=source.ingest_native_pdf_bytes(
        document_id=f"diag-maryborough:{source_sha[:32]}",
        source_bytes=payload,
        source_locator="memory://maryborough.pdf",
        page_ids=(PAGE_ID,),
    )
    current=source.published_snapshot_for_revision(published.revision.revision_id)
    if current is None:
        raise RuntimeError("published snapshot unavailable")

    pdf=fitz.open(stream=payload,filetype="pdf")
    try:
        page=pdf.load_page(int(PAGE_ID)-1)
        viewports=tuple(segment_page_viewports(page,page_number=int(PAGE_ID)))
    finally:
        pdf.close()

    nonoverlap=validate_non_overlapping_viewports(viewports)
    authoritative=[
        vp for vp in viewports
        if vp.bounding_box is not None
        and vp.status == ViewportSegmentationStatus.RESOLVED.value
        and is_authoritative_derived_viewport(vp)
        and vp.view_type == DrawingViewType.ELEVATION.value
    ]

    integrity=source.text_integrity_authority()
    rows=[]
    for observation_id in current.text_observation_ids:
        result=integrity.resolve_text(
            ObservationSelector(
                document_id=current.revision.document_id,
                revision_id=current.revision.revision_id,
                source_sha256=current.revision.source_sha256,
                snapshot_id=current.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        receipt=result.receipt
        if receipt is None or str(receipt.page_id) != PAGE_ID:
            continue
        raw=norm(receipt.raw_text)
        trusted=norm(result.trusted_text) if result.trusted_text is not None else ""
        if raw not in TARGETS and trusted not in TARGETS:
            continue
        point=center(receipt.geometry)
        owners=[
            {
                "view_id":vp.view_id,
                "view_type":vp.view_type,
                "status":vp.status,
                "bounding_box":list(vp.bounding_box),
            }
            for vp in authoritative
            if inside(point,vp.bounding_box)
        ]
        rows.append({
            "observation_id":observation_id,
            "raw_text":raw,
            "trusted_text":trusted or None,
            "status":getattr(result.status,"value",str(result.status)),
            "reason_codes":list(result.reason_codes),
            "geometry":list(receipt.geometry),
            "center":list(point),
            "authoritative_elevation_owner_count":len(owners),
            "authoritative_elevation_owners":owners,
        })

    print(json.dumps({
        "source_sha256":source_sha,
        "page_id":PAGE_ID,
        "viewport_count":len(viewports),
        "authoritative_elevation_viewport_count":len(authoritative),
        "viewport_siblings_non_overlapping":bool(nonoverlap),
        "target_rows":rows,
    },indent=2,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
