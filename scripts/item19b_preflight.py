from __future__ import annotations

from pathlib import Path
import json
import math

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_vector_geometry_v130 import extract_native_page
from pb_viewport_segmentation import assign_bbox_to_viewport, segment_page_viewports
from pb_wall_role_authority import WallRoleProducer, WallRoleSelector

PDF = Path("benchmarks/sources/1727358888238-bq-nd-drawing.pdf")
PAGE_ID = "54"
SCOPE_ID = "wall-source:page-54"


def intersects(seg, bbox):
    x0, y0, x1, y1 = bbox
    a = fitz.Point(float(seg["x1"]), float(seg["y1"]))
    b = fitz.Point(float(seg["x2"]), float(seg["y2"]))
    rect = fitz.Rect(float(x0), float(y0), float(x1), float(y1))
    if rect.contains(a) or rect.contains(b):
        return True
    for p, q in (
        (fitz.Point(rect.x0, rect.y0), fitz.Point(rect.x1, rect.y0)),
        (fitz.Point(rect.x1, rect.y0), fitz.Point(rect.x1, rect.y1)),
        (fitz.Point(rect.x1, rect.y1), fitz.Point(rect.x0, rect.y1)),
        (fitz.Point(rect.x0, rect.y1), fitz.Point(rect.x0, rect.y0)),
    ):
        if fitz.utils.get_line_intersection(a, b, p, q):
            return True
    return False


def main():
    if not PDF.exists():
        raise SystemExit(f"missing {PDF}")
    payload = PDF.read_bytes()
    source = SourceVisibilityProducer(
        producer_method="item19b-preflight",
        producer_version="0.1",
    )
    initial = source.ingest_native_pdf_bytes(
        document_id="kstvet-item19b-preflight",
        source_bytes=payload,
        source_locator=str(PDF),
    )
    walls = PhysicalWallCandidateProducer.from_source_visibility_producer(
        source,
        page_ids=(PAGE_ID,),
    ).authority()
    published = source.published_snapshot_for_revision(initial.revision.revision_id)
    assert published is not None
    selector = PhysicalWallCandidateSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=PAGE_ID,
        decision_scope_id=SCOPE_ID,
    )
    scope = walls.resolve_scope(selector)
    print(
        "SCOPE", scope.status, "complete", scope.scope_complete,
        "records", len(scope.records), "reasons", scope.reason_codes,
    )
    print("LINEAGE", published.revision.revision_id, published.revision.source_sha256, published.snapshot.snapshot_id)

    doc = fitz.open(PDF)
    page = doc[53]
    viewports = segment_page_viewports(page, page_number=54)
    print("VIEWPORTS")
    for vp in viewports:
        print(json.dumps({
            "id": vp.view_id,
            "label": vp.label,
            "status": vp.status,
            "bbox": vp.bounding_box,
            "boundary_source": vp.boundary_source,
            "provenance": vp.provenance,
        }, default=str, sort_keys=True))

    native = extract_native_page(page)
    raw = {str(s["id"]): s for s in native.get("segments") or ()}
    role_prod = WallRoleProducer.from_source_topology(
        physical_wall_candidate_authority=walls
    )

    targets = {
        "external": (644.3074, 476.6662, 651.8647, 484.2264),
        "internal": (266.3530, 618.2343, 273.9123, 625.7916),
    }
    for name, box in targets.items():
        vp = assign_bbox_to_viewport(box, viewports, allow_derived=True)
        print("TARGET", name, "viewport", None if vp is None else (vp.view_id, vp.label, vp.status, vp.bounding_box))
        touched = []
        for rec in scope.records:
            source_ids = tuple(rec.physical_identity.source_primitive_ids)
            hit_ids = tuple(sorted(sid for sid in source_ids if sid in raw and intersects(raw[sid], box)))
            if not hit_ids:
                continue
            role = role_prod.publish(
                WallRoleSelector(
                    document_id=published.revision.document_id,
                    revision_id=published.revision.revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    page_id=PAGE_ID,
                    decision_scope_id=SCOPE_ID,
                    physical_wall_id=rec.wall_candidate_id,
                )
            )
            touched.append({
                "wall_id": rec.wall_candidate_id,
                "identity_id": rec.physical_identity.candidate_identity_id,
                "hit_source_ids": hit_ids,
                "all_source_ids": source_ids,
                "centerline": rec.wall_candidate.centerline_pts,
                "face_a": rec.wall_candidate.face_a_segment_ids,
                "face_b": rec.wall_candidate.face_b_segment_ids,
                "representation": rec.wall_candidate.representation,
                "role_status": role.status.value,
                "role": None if role.record is None else role.record.role.value,
                "role_reasons": role.reason_codes,
            })
        print("TOUCHED", name, json.dumps(touched, default=str, sort_keys=True))
    doc.close()


if __name__ == "__main__":
    main()
