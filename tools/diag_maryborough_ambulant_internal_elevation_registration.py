from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz

from pb_cross_sheet_registration_authority import (
    CrossSheetRegistrationProducer,
    CrossSheetRegistrationSelector,
)
from pb_drawing_evidence_binding import DrawingViewType
from pb_internal_elevation_wall_face_authority import (
    InternalElevationWallFaceProducer,
    InternalElevationWallFaceSelector,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_observation_authority import ObservationSelector
from pb_source_room_face_authority import (
    SourceRoomFaceSelector,
    build_source_room_face_authority,
)
from pb_source_room_label_authority import _point_in_polygon
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import (
    ViewportSegmentationStatus,
    is_authoritative_derived_viewport,
    segment_page_viewports,
    validate_non_overlapping_viewports,
)

SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
PLAN_PAGE_ID = "7"
ELEVATION_PAGE_ID = "27"
TARGETS = ("M-AMB", "F-AMB")


def norm(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())


def bbox_center(values) -> tuple[float, float] | None:
    bbox = tuple(float(v) for v in (values or ()))
    if len(bbox) != 4:
        return None
    x0, y0, x1, y1 = bbox
    if x1 <= x0 or y1 <= y0:
        return None
    return ((x0 + x1) * 0.5, (y0 + y1) * 0.5)


def point_in_bbox(point, bbox) -> bool:
    x, y = point
    x0, y0, x1, y1 = [float(v) for v in bbox]
    return x0 < x < x1 and y0 < y < y1


def main() -> int:
    payload = SOURCE.read_bytes()
    source_sha = hashlib.sha256(payload).hexdigest()
    source = SourceVisibilityProducer(
        producer_method="gpt2-ambulant-internal-elevation-registration-diag",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"diag-maryborough:{source_sha[:32]}",
        source_bytes=payload,
        source_locator="memory://maryborough.pdf",
        page_ids=(PLAN_PAGE_ID, ELEVATION_PAGE_ID),
    )
    current = source.published_snapshot_for_revision(published.revision.revision_id)
    if current is None:
        raise RuntimeError("published snapshot unavailable")

    wall_producer = PhysicalWallCandidateProducer.from_source_visibility_producer(
        source,
        page_ids=(PLAN_PAGE_ID, ELEVATION_PAGE_ID),
    )
    wall_authority = wall_producer.authority()
    room_authority = build_source_room_face_authority(wall_authority)
    room_scope = room_authority.resolve_scope(
        SourceRoomFaceSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            page_id=PLAN_PAGE_ID,
            decision_scope_id=f"wall-source:page-{PLAN_PAGE_ID}",
        )
    )

    integrity = source.text_integrity_authority()
    source_target_rows = []
    source_faces_by_target = {}
    for observation_id in current.text_observation_ids:
        result = integrity.resolve_text(
            ObservationSelector(
                document_id=current.revision.document_id,
                revision_id=current.revision.revision_id,
                source_sha256=current.revision.source_sha256,
                snapshot_id=current.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        receipt = result.receipt
        if receipt is None or str(receipt.page_id) != PLAN_PAGE_ID:
            continue
        raw = norm(receipt.raw_text)
        if raw not in TARGETS:
            continue
        center = bbox_center(receipt.geometry)
        matches = []
        if center is not None:
            matches = [
                record
                for record in room_scope.records
                if _point_in_polygon(center, record.polygon_pdf_pts)
            ]
        source_target_rows.append(
            {
                "target": raw,
                "observation_id": observation_id,
                "text_status": getattr(result.status, "value", str(result.status)),
                "text_reason_codes": list(result.reason_codes),
                "center": list(center) if center is not None else None,
                "face_match_count": len(matches),
                "face_matches": [
                    {
                        "face_id": str(record.face_id),
                        "record_id": str(record.record_id),
                        "area_page_pts2": float(record.area_page_pts2),
                        "bounding_wall_ids": list(record.bounding_wall_ids),
                    }
                    for record in matches
                ],
            }
        )
        if len(matches) == 1:
            source_faces_by_target[raw] = matches[0]

    pdf = fitz.open(stream=payload, filetype="pdf")
    try:
        target_page = pdf.load_page(int(ELEVATION_PAGE_ID) - 1)
        viewports = tuple(
            segment_page_viewports(
                target_page,
                page_number=int(ELEVATION_PAGE_ID),
            )
        )
    finally:
        pdf.close()

    authoritative_elevations = [
        viewport
        for viewport in viewports
        if viewport.bounding_box is not None
        and viewport.status == ViewportSegmentationStatus.RESOLVED.value
        and is_authoritative_derived_viewport(viewport)
        and viewport.view_type == DrawingViewType.ELEVATION.value
    ]
    siblings_nonoverlap = validate_non_overlapping_viewports(viewports)

    target_label_rows = []
    target_labels_by_viewport: dict[str, set[str]] = {}
    for observation_id in current.text_observation_ids:
        result = integrity.resolve_text(
            ObservationSelector(
                document_id=current.revision.document_id,
                revision_id=current.revision.revision_id,
                source_sha256=current.revision.source_sha256,
                snapshot_id=current.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        receipt = result.receipt
        if receipt is None or str(receipt.page_id) != ELEVATION_PAGE_ID:
            continue
        trusted = norm(result.trusted_text) if result.trusted_text is not None else ""
        raw = norm(receipt.raw_text)
        if trusted not in TARGETS and raw not in TARGETS:
            continue
        center = bbox_center(receipt.geometry)
        owners = []
        if center is not None:
            owners = [
                viewport
                for viewport in authoritative_elevations
                if point_in_bbox(center, viewport.bounding_box)
            ]
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and trusted in TARGETS
            and len(owners) == 1
        ):
            target_labels_by_viewport.setdefault(owners[0].view_id, set()).add(
                trusted
            )
        target_label_rows.append(
            {
                "raw_text": raw,
                "trusted_text": trusted or None,
                "status": getattr(result.status, "value", str(result.status)),
                "reason_codes": list(result.reason_codes),
                "center": list(center) if center is not None else None,
                "owner_viewport_ids": [viewport.view_id for viewport in owners],
            }
        )

    cross_producer = CrossSheetRegistrationProducer.from_authorities(
        physical_wall_candidate_authority=wall_authority,
        source_visibility_producer=source,
    )

    cross_rows = []
    selector_rows = []
    for target, face in sorted(source_faces_by_target.items()):
        for wall_id in sorted({str(v) for v in face.bounding_wall_ids}):
            selector = CrossSheetRegistrationSelector(
                document_id=current.revision.document_id,
                revision_id=current.revision.revision_id,
                source_sha256=current.revision.source_sha256,
                snapshot_id=current.snapshot.snapshot_id,
                source_page_id=PLAN_PAGE_ID,
                target_page_id=ELEVATION_PAGE_ID,
                physical_element_id=wall_id,
            )
            result = cross_producer.publish(selector)
            record = result.record
            row = {
                "target": target,
                "source_face_id": str(face.face_id),
                "source_room_face_record_id": str(face.record_id),
                "source_wall_id": wall_id,
                "status": getattr(result.status, "value", str(result.status)),
                "reason_codes": list(result.reason_codes),
                "record": None,
            }
            if record is not None:
                row["record"] = {
                    "record_id": record.record_id,
                    "target_physical_element_id": record.target_physical_element_id,
                    "source_view_type": record.source_view_type,
                    "target_view_type": record.target_view_type,
                    "callout_mark": record.callout_mark,
                    "referenced_sheet_code": record.referenced_sheet_code,
                }
                selector_rows.append((target, selector))
            cross_rows.append(row)

    internal_producer = InternalElevationWallFaceProducer.from_authorities(
        cross_sheet_authority=cross_producer.authority(),
        physical_wall_authority=wall_authority,
        room_face_authority=room_authority,
        source_visibility_producer=source,
    )

    internal_rows = []
    for target, cross_selector in selector_rows:
        selector = InternalElevationWallFaceSelector(
            document_id=cross_selector.document_id,
            revision_id=cross_selector.revision_id,
            source_sha256=cross_selector.source_sha256,
            snapshot_id=cross_selector.snapshot_id,
            source_page_id=cross_selector.source_page_id,
            target_page_id=cross_selector.target_page_id,
            physical_wall_id=cross_selector.physical_element_id,
        )
        result = internal_producer.publish(selector)
        record = result.record
        row = {
            "target": target,
            "physical_wall_id": selector.physical_wall_id,
            "status": getattr(result.status, "value", str(result.status)),
            "reason_codes": list(result.reason_codes),
            "record": None,
            "trusted_target_labels_in_resolved_viewport": [],
        }
        if record is not None:
            labels = sorted(target_labels_by_viewport.get(record.target_viewport_id, set()))
            row["record"] = {
                "record_id": record.record_id,
                "source_room_face_id": record.source_room_face_id,
                "source_room_face_record_id": record.source_room_face_record_id,
                "physical_face_id": record.physical_face_id,
                "target_physical_wall_id": record.target_physical_wall_id,
                "target_viewport_id": record.target_viewport_id,
                "target_view_type": record.target_view_type,
                "callout_mark": record.callout_mark,
                "referenced_sheet_code": record.referenced_sheet_code,
            }
            row["trusted_target_labels_in_resolved_viewport"] = labels
        internal_rows.append(row)

    print(json.dumps({
        "source_sha256": source_sha,
        "room_scope_status": getattr(room_scope.status, "value", str(room_scope.status)),
        "room_scope_reason_codes": list(room_scope.reason_codes),
        "room_face_universe_complete": bool(room_scope.face_universe_complete),
        "room_face_count": len(room_scope.records),
        "source_target_rows": source_target_rows,
        "target_viewport_count": len(viewports),
        "authoritative_elevation_viewport_count": len(authoritative_elevations),
        "target_viewports_nonoverlapping": bool(siblings_nonoverlap),
        "target_label_rows": target_label_rows,
        "cross_sheet_rows": cross_rows,
        "internal_elevation_rows": internal_rows,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
