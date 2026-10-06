from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from pb_drawing_evidence_binding import DrawingViewType
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_schedule_opening_instance_binding_authority import (
    ScheduleOpeningInstanceBindingProducer,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_room_face_authority import (
    SourceRoomFaceSelector,
    build_source_room_face_authority,
)
from pb_source_room_label_authority import _point_in_polygon
from pb_source_visibility_authority import SourceVisibilityProducer


SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
PLAN_PAGE_ID = "7"
SCHEDULE_PAGE_ID = "28"
TARGETS = ("M-AMB", "F-AMB")


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())


def _receipt_center(receipt) -> tuple[float, float] | None:
    geometry = tuple(float(v) for v in (getattr(receipt, "geometry", ()) or ()))
    if len(geometry) != 4:
        return None
    x0, y0, x1, y1 = geometry
    if x1 <= x0 or y1 <= y0:
        return None
    return ((x0 + x1) * 0.5, (y0 + y1) * 0.5)


def main() -> int:
    started = time.perf_counter()
    payload = SOURCE.read_bytes()
    source_sha = hashlib.sha256(payload).hexdigest()

    source = SourceVisibilityProducer(
        producer_method="gpt2-maryborough-ambulant-schedule-binding-diag",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"diag-maryborough:{source_sha[:32]}",
        source_bytes=payload,
        source_locator="memory://diag-maryborough.pdf",
        page_ids=(PLAN_PAGE_ID, SCHEDULE_PAGE_ID),
    )

    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=(PLAN_PAGE_ID,),
        evidence_page_ids=(SCHEDULE_PAGE_ID,),
    )
    current = source.published_snapshot_for_revision(published.revision.revision_id)
    if current is None:
        raise RuntimeError("current source snapshot unavailable")

    wall_authority = composition.physical_wall_candidate_authority
    selectors = wall_authority.selectors_for_authenticated_viewports(
        document_id=current.revision.document_id,
        revision_id=current.revision.revision_id,
        source_sha256=current.revision.source_sha256,
        snapshot_id=current.snapshot.snapshot_id,
        page_id=PLAN_PAGE_ID,
        view_type=DrawingViewType.FLOOR_PLAN.value,
    )
    room_scopes = []
    if selectors:
        room_authority = build_source_room_face_authority(wall_authority)
        for selector in selectors:
            result = room_authority.resolve_scope(
                SourceRoomFaceSelector(
                    document_id=selector.document_id,
                    revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,
                    snapshot_id=selector.snapshot_id,
                    page_id=selector.page_id,
                    decision_scope_id=selector.decision_scope_id,
                )
            )
            if result.status is EvidenceResolutionStatus.CORROBORATED:
                room_scopes.append(result)

    room_records = [
        record
        for scope in room_scopes
        for record in scope.records
    ]

    text_authority = source.text_integrity_authority()
    raw_plan_targets = []
    for observation_id in current.text_observation_ids:
        result = text_authority.resolve_text(
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
        raw_text = _norm(receipt.raw_text)
        if raw_text not in TARGETS:
            continue
        center = _receipt_center(receipt)
        matches = []
        if center is not None:
            for record in room_records:
                if _point_in_polygon(center, record.polygon_pdf_pts):
                    matches.append(
                        {
                            "face_id": str(record.face_id),
                            "record_id": str(record.record_id),
                            "area_page_pts2": float(record.area_page_pts2),
                            "bounding_wall_ids": list(record.bounding_wall_ids),
                        }
                    )
        raw_plan_targets.append(
            {
                "observation_id": observation_id,
                "raw_text": raw_text,
                "status": getattr(result.status, "value", str(result.status)),
                "reason_codes": list(result.reason_codes),
                "center": list(center) if center is not None else None,
                "face_match_count": len(matches),
                "face_matches": matches,
            }
        )

    binding_producer = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(
        source
    )
    target_bindings = []
    seen_openings = set()

    for trace in composition.opening_traces:
        opening_id = str(trace.opening_identity_id or "").strip()
        observation_id = str(trace.representative_observation_id or "").strip()
        if (
            not opening_id
            or not observation_id
            or str(trace.page_id or "") != PLAN_PAGE_ID
            or opening_id in seen_openings
        ):
            continue
        seen_openings.add(opening_id)

        opening_selector = ObservationSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        schedule_result = binding_producer.publish_scope(
            opening_selector=opening_selector,
            decision_scope_id=f"wall-source:page-{PLAN_PAGE_ID}",
        )
        record = schedule_result.record
        if (
            schedule_result.status is not EvidenceResolutionStatus.CORROBORATED
            or record is None
            or str(record.schedule_page_id) != SCHEDULE_PAGE_ID
        ):
            continue

        trusted_row_texts = []
        trusted_row_receipts = []
        for row_obs_id in record.schedule_row_observation_ids:
            row_result = text_authority.resolve_text(
                ObservationSelector(
                    document_id=current.revision.document_id,
                    revision_id=current.revision.revision_id,
                    source_sha256=current.revision.source_sha256,
                    snapshot_id=current.snapshot.snapshot_id,
                    observation_id=row_obs_id,
                )
            )
            if (
                row_result.status is EvidenceResolutionStatus.CORROBORATED
                and row_result.trusted_text is not None
                and row_result.receipt is not None
            ):
                trusted_row_texts.append(_norm(row_result.trusted_text))
                trusted_row_receipts.append(
                    {
                        "observation_id": row_obs_id,
                        "trusted_text": _norm(row_result.trusted_text),
                        "block_no": row_result.receipt.block_no,
                        "line_no": row_result.receipt.line_no,
                        "word_no": row_result.receipt.word_no,
                    }
                )

        row_blob = " | ".join(trusted_row_texts)
        matched_targets = [
            target for target in TARGETS
            if target in row_blob
        ]
        if not matched_targets:
            continue

        host_wall_id = None
        host_binding_status = None
        host_binding_reasons = []
        binding_selector = composition.binding_selectors.get(opening_id)
        if binding_selector is not None:
            host_result = composition.opening_host_binding_authority.resolve(
                binding_selector
            )
            host_binding_status = getattr(
                host_result.status, "value", str(host_result.status)
            )
            host_binding_reasons = list(host_result.reason_codes)
            if host_result.record is not None:
                host_wall_id = str(host_result.record.host_wall_id)

        adjacent_faces = []
        if host_wall_id:
            for room in room_records:
                if host_wall_id in {str(v) for v in room.bounding_wall_ids}:
                    adjacent_faces.append(
                        {
                            "face_id": str(room.face_id),
                            "record_id": str(room.record_id),
                            "area_page_pts2": float(room.area_page_pts2),
                            "bounding_wall_ids": list(room.bounding_wall_ids),
                        }
                    )

        target_bindings.append(
            {
                "opening_identity_id": opening_id,
                "representative_observation_id": observation_id,
                "tag_mark": record.tag_mark,
                "schedule_page_id": record.schedule_page_id,
                "schedule_row_type_mark": record.schedule_row_type_mark,
                "schedule_row_observation_ids": list(record.schedule_row_observation_ids),
                "trusted_schedule_row_texts": trusted_row_receipts,
                "matched_targets": matched_targets,
                "host_binding_status": host_binding_status,
                "host_binding_reason_codes": host_binding_reasons,
                "host_wall_id": host_wall_id,
                "adjacent_face_count": len(adjacent_faces),
                "adjacent_faces": adjacent_faces,
            }
        )

    print(
        json.dumps(
            {
                "source_sha256": source_sha,
                "mode": "DIAGNOSTIC_ONLY_AMBULANT_SCHEDULE_PHYSICAL_BINDING",
                "wall_opening_status": getattr(
                    composition.status, "value", str(composition.status)
                ),
                "opening_trace_count": len(composition.opening_traces),
                "room_scope_count": len(room_scopes),
                "room_face_count": len(room_records),
                "raw_plan_targets": raw_plan_targets,
                "target_schedule_bindings": target_bindings,
                "elapsed_seconds": time.perf_counter() - started,
            },
            indent=2,
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
