from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pb_cross_view_room_area_authority import CrossViewRoomAreaProducer
from pb_live_canonical_room_composition import compose_live_canonical_rooms
from pb_live_canonical_wall_composition import compose_live_canonical_walls
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_same_view_room_area_authority import SameViewRoomAreaProducer
from pb_source_visibility_authority import SourceVisibilityProducer


PDF = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")


def _record(row):
    ev = row.area_evidence
    return {
        "physical_room_id": row.physical_room_id,
        "source_room_face_record_id": row.source_room_face_record_id,
        "room_label": row.room_label,
        "source_dimension_page_id": row.source_dimension_page_id,
        "value": ev.normalized_value,
        "unit": ev.unit,
        "method": ev.method,
        "evidence_id": ev.evidence_id,
        "figured_dimension_ids": list((ev.metadata or {}).get("figured_dimension_ids") or ()),
        "source_dimension_box_pdf_pts": (ev.metadata or {}).get("source_dimension_box_pdf_pts"),
    }


def main() -> int:
    payload = PDF.read_bytes()
    sha = hashlib.sha256(payload).hexdigest()
    source = SourceVisibilityProducer(
        producer_method="diag-gpt1-room-area-split",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"diag:{sha[:32]}",
        source_bytes=payload,
        source_locator="memory://maryborough.pdf",
        page_ids=("7", "11"),
    )
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("7",),
        evidence_page_ids=(),
    )
    walls = compose_live_canonical_walls(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )
    rooms = compose_live_canonical_rooms(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
        canonical_wall_ids_by_candidate=walls.candidate_to_canonical_wall_id,
        unresolved_wall_candidate_ids=walls.unresolved_wall_candidate_ids,
    )
    same = SameViewRoomAreaProducer.from_source(source=source, rooms=rooms).publish()
    cross = CrossViewRoomAreaProducer.from_source(source=source, rooms=rooms).publish()

    same_by = {r.source_room_face_record_id: r for r in same.records}
    cross_by = {r.source_room_face_record_id: r for r in cross.records}

    binding_diagnostics = []
    rooms_by_record = {
        str(room.source_room_face_record_id): room
        for room in rooms.rooms
        if str(room.source_room_face_record_id or "").strip()
    }
    for record_id, area_record in sorted(cross_by.items()):
        room = rooms_by_record.get(str(record_id))
        row = {
            "source_room_face_record_id": str(record_id),
            "room_label": area_record.room_label,
            "room_found": room is not None,
        }
        if room is not None:
            row.update({
                "canonical_room_id": room.canonical_room_id,
                "physical_room_id": room.physical_room_id,
                "page_id": room.page_id,
                "viewport_id": room.viewport_id,
                "decision_scope_id": room.decision_scope_id,
            })
            binding = rooms.room_face_authority_binding_for(room)
            row["binding_found"] = binding is not None
            if binding is not None:
                row.update({
                    "binding_viewport_id": binding.viewport_id,
                    "binding_viewport_bbox": binding.viewport_bbox,
                    "binding_viewport_view_type": binding.viewport_view_type,
                    "binding_record_count": len(binding.source_room_face_record_ids),
                    "binding_contains_record": str(record_id) in binding.source_room_face_record_ids,
                })
                from pb_source_room_face_authority import SourceRoomFaceSelector
                selector = SourceRoomFaceSelector(
                    document_id=room.document_id,
                    revision_id=room.revision_id,
                    source_sha256=room.source_sha256,
                    snapshot_id=room.snapshot_id,
                    page_id=room.page_id,
                    decision_scope_id=room.decision_scope_id,
                )
                resolved = binding.authority.resolve_scope(selector)
                row.update({
                    "resolved_status": getattr(resolved.status, "value", str(resolved.status)),
                    "resolved_scope_complete": bool(resolved.scope_complete),
                    "resolved_record_count": len(resolved.records),
                    "resolved_contains_record": any(
                        str(item.record_id) == str(record_id)
                        for item in resolved.records
                    ),
                    "resolved_face_id": next(
                        (
                            str(item.face_id)
                            for item in resolved.records
                            if str(item.record_id) == str(record_id)
                        ),
                        None,
                    ),
                })
        binding_diagnostics.append(row)

    overlap = []
    for record_id in sorted(set(same_by) & set(cross_by)):
        a, b = same_by[record_id], cross_by[record_id]
        overlap.append({
            "record_id": record_id,
            "label": a.room_label,
            "same_value": a.area_evidence.normalized_value,
            "cross_value": b.area_evidence.normalized_value,
            "same_method": a.area_evidence.method,
            "cross_method": b.area_evidence.method,
            "same_evidence_id": a.area_evidence.evidence_id,
            "cross_evidence_id": b.area_evidence.evidence_id,
        })

    labels = sorted({
        str(room.room_label or "").strip()
        for room in rooms.rooms
        if str(room.room_label or "").strip()
    })
    print(json.dumps({
        "source_sha256": sha,
        "canonical_room_count": len(rooms.rooms),
        "canonical_labels": labels,
        "same_status": getattr(same.status, "value", str(same.status)),
        "same_reason_codes": list(same.reason_codes),
        "same_record_count": len(same.records),
        "same_records": [_record(r) for r in same.records],
        "cross_status": getattr(cross.status, "value", str(cross.status)),
        "cross_reason_codes": list(cross.reason_codes),
        "cross_record_count": len(cross.records),
        "cross_records": [_record(r) for r in cross.records],
        "overlap_count": len(overlap),
        "overlap": overlap,
        "binding_diagnostics": binding_diagnostics,
    }, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
