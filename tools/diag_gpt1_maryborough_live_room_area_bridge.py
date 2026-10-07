from __future__ import annotations

import json
from pathlib import Path

import pb_live_physical_net_wall_integration as live
from pb_cross_view_room_area_authority import CrossViewRoomAreaProducer


PDF = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")


def main() -> int:
    captures = {"cross": [], "bridges": []}
    original_cross = CrossViewRoomAreaProducer.publish
    original_bridge = live.build_source_room_area_bridge

    def capture_cross(self):
        result = original_cross(self)
        captures["cross"].append({
            "status": getattr(result.status, "value", str(result.status)),
            "reason_codes": list(result.reason_codes),
            "record_count": len(result.records),
            "records": [
                {
                    "room_label": row.room_label,
                    "physical_room_id": row.physical_room_id,
                    "source_room_face_record_id": row.source_room_face_record_id,
                    "source_dimension_page_id": row.source_dimension_page_id,
                    "value": row.area_evidence.normalized_value,
                    "unit": row.area_evidence.unit,
                    "evidence_id": row.area_evidence.evidence_id,
                    "viewport_id": row.area_evidence.viewport_id,
                    "page_id": row.area_evidence.page_id,
                }
                for row in result.records
            ],
        })
        return result

    def capture_bridge(**kwargs):
        explicit = dict(kwargs.get("explicit_area_evidence_by_room_id") or {})
        result = original_bridge(**kwargs)
        index = result.room_index
        captures["bridges"].append({
            "selector": {
                "page_id": kwargs["selector"].page_id,
                "decision_scope_id": kwargs["selector"].decision_scope_id,
            },
            "viewport": {
                "viewport_id": kwargs["viewport"].viewport_id,
                "page_id": kwargs["viewport"].page_id,
                "view_type": kwargs["viewport"].view_type,
                "bbox": list(kwargs["viewport"].bbox),
                "status": getattr(kwargs["viewport"].status, "value", str(kwargs["viewport"].status)),
            },
            "explicit_count": len(explicit),
            "explicit": [
                {
                    "room_ref": key,
                    "evidence_id": ev.evidence_id,
                    "value": ev.normalized_value,
                    "page_id": ev.page_id,
                    "viewport_id": ev.viewport_id,
                    "source_room_face_record_id": (ev.metadata or {}).get("source_room_face_record_id"),
                    "source_label_text": (ev.metadata or {}).get("source_label_text"),
                }
                for key, ev in sorted(explicit.items())
            ],
            "status": getattr(result.status, "value", str(result.status)),
            "reason_codes": list(result.reason_codes),
            "room_index_count": 0 if index is None else len(index.rooms()),
            "room_index_ids": [] if index is None else [room.room_ref for room in index.rooms()],
            "quantities": [
                {
                    "quantity_id": q.quantity_id,
                    "input_entity_ids": list(q.input_entity_ids),
                    "value": q.value,
                    "authority": q.authority,
                    "status": q.status,
                    "abstained": q.abstained,
                    "blocking_reasons": list(q.blocking_reasons),
                    "reason_codes": list(q.reason_codes),
                    "metadata": dict(q.metadata or {}),
                }
                for q in result.quantities
            ],
        })
        return result

    CrossViewRoomAreaProducer.publish = capture_cross
    live.build_source_room_area_bridge = capture_bridge
    try:
        claim = live.collect_live_physical_net_wall_claim(
            PDF,
            pages=(6,),
            topology_pages=(6,),
            room_area_support_pages=(10,),
        )
    finally:
        CrossViewRoomAreaProducer.publish = original_cross
        live.build_source_room_area_bridge = original_bridge

    output = {
        "canonical_room_count": len(claim.canonical_rooms),
        "labelled_rooms": [
            {
                "label": room.room_label,
                "source_room_face_record_id": room.source_room_face_record_id,
                "viewport_id": room.viewport_id,
                "decision_scope_id": room.decision_scope_id,
            }
            for room in claim.canonical_rooms
            if str(room.room_label or "").strip()
        ],
        "cross": captures["cross"],
        "bridges": captures["bridges"],
        "claim_room_quantities": [
            {
                "quantity_id": q.quantity_id,
                "input_entity_ids": list(q.input_entity_ids),
                "value": q.value,
                "authority": q.authority,
                "status": q.status,
                "abstained": q.abstained,
                "blocking_reasons": list(q.blocking_reasons),
                "metadata": dict(q.metadata or {}),
            }
            for q in claim.room_area_quantity_evidence
        ],
    }
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
