from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pb_cross_view_room_area_authority as cross_view
from pb_cross_view_room_area_authority import CrossViewRoomAreaProducer
from pb_live_canonical_room_composition import compose_live_canonical_rooms
from pb_live_canonical_wall_composition import compose_live_canonical_walls
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_visibility_authority import SourceVisibilityProducer


SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
TOPOLOGY_PAGE_ID = "7"
SUPPORT_PAGE_ID = "9"


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())


def main() -> int:
    started = time.perf_counter()
    payload = SOURCE.read_bytes()
    source_sha = hashlib.sha256(payload).hexdigest()
    source = SourceVisibilityProducer(
        producer_method="diag-gpt2-maryborough-freezer-rcp",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"diag-maryborough:{source_sha[:32]}",
        source_bytes=payload,
        source_locator="memory://diag-maryborough-source.pdf",
        page_ids=(TOPOLOGY_PAGE_ID, SUPPORT_PAGE_ID),
    )

    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=(TOPOLOGY_PAGE_ID,),
        evidence_page_ids=(),
    )
    canonical_walls = compose_live_canonical_walls(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )
    rooms = compose_live_canonical_rooms(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
        canonical_wall_ids_by_candidate=canonical_walls.candidate_to_canonical_wall_id,
        unresolved_wall_candidate_ids=canonical_walls.unresolved_wall_candidate_ids,
    )

    freezer_rooms = [
        room
        for room in rooms.rooms
        if _norm(room.room_label) == "FREEZER"
    ]

    lines = cross_view._trusted_lines_for_page(
        source,
        revision_id=published.revision.revision_id,
        page_id=SUPPORT_PAGE_ID,
        candidate_labels=("FREEZER",),
    )
    dimensions = cross_view._trusted_native_dimensions_for_page(
        source,
        revision_id=published.revision.revision_id,
        page_id=SUPPORT_PAGE_ID,
        candidate_lines=lines,
    ) if lines else ()

    result = CrossViewRoomAreaProducer.from_source(
        source=source,
        rooms=rooms,
    ).publish()

    freezer_records = [
        {
            "physical_room_id": record.physical_room_id,
            "source_room_face_record_id": record.source_room_face_record_id,
            "source_dimension_page_id": record.source_dimension_page_id,
            "area_m2": record.area_evidence.normalized_value,
            "figured_dimension_ids": list(
                record.area_evidence.metadata.get("figured_dimension_ids") or ()
            ),
            "horizontal_value_mm": record.area_evidence.metadata.get(
                "horizontal_value_mm"
            ),
            "vertical_value_mm": record.area_evidence.metadata.get(
                "vertical_value_mm"
            ),
            "support_mode": record.area_evidence.metadata.get(
                "source_label_support_mode"
            ),
        }
        for record in result.records
        if _norm(record.room_label) == "FREEZER"
    ]

    print(json.dumps({
        "source_sha256": source_sha,
        "topology_page_id": TOPOLOGY_PAGE_ID,
        "support_page_id": SUPPORT_PAGE_ID,
        "freezer_topology_room_count": len(freezer_rooms),
        "freezer_support_line_count": len(lines),
        "freezer_support_lines": [
            {
                "text": line.text,
                "bbox": list(line.bbox),
                "block_no": line.block_no,
                "line_no": line.line_no,
                "source_partition_id": line.source_partition_id,
            }
            for line in lines
        ],
        "trusted_dimension_count": len(dimensions),
        "trusted_dimensions": [
            {
                "dimension_id": item.dimension_id,
                "orientation": item.orientation,
                "value_mm": item.value_mm,
                "endpoints_pt": [list(item.endpoints_pt[0]), list(item.endpoints_pt[1])],
                "text_block_no": item.text_block_no,
                "text_line_no": item.text_line_no,
                "text_word_no": item.text_word_no,
            }
            for item in dimensions
        ],
        "cross_view_status": getattr(result.status, "value", str(result.status)),
        "cross_view_reason_codes": list(result.reason_codes),
        "freezer_records": freezer_records,
        "freezer_unresolved": [
            room.physical_room_id
            for room in freezer_rooms
            if str(room.physical_room_id) in set(result.unresolved_physical_room_ids)
        ],
        "elapsed_seconds": time.perf_counter() - started,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
