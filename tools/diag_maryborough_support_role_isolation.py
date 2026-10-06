from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import pb_cross_view_room_area_authority as cross_view
from pb_cross_view_room_area_authority import CrossViewRoomAreaProducer
from pb_live_canonical_room_composition import compose_live_canonical_rooms
from pb_live_canonical_wall_composition import compose_live_canonical_walls
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_floor_plan_page_scope import source_floor_plan_topology_scope
from pb_source_visibility_authority import SourceVisibilityProducer


SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
TOPOLOGY_PAGE_ID = "7"


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--support-page", required=True, type=int)
    args = parser.parse_args()
    support_page_id = str(args.support_page)

    started = time.perf_counter()
    payload = SOURCE.read_bytes()
    source_sha = hashlib.sha256(payload).hexdigest()

    scope = source_floor_plan_topology_scope(SOURCE, tuple(range(31)))
    decision = None
    if scope is not None:
        decision = next(
            (
                item for item in scope.decisions
                if int(item.page_index) + 1 == int(args.support_page)
            ),
            None,
        )

    source = SourceVisibilityProducer(
        producer_method="diag-gpt2-maryborough-support-role",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"diag-maryborough:{source_sha[:32]}",
        source_bytes=payload,
        source_locator="memory://diag-maryborough-source.pdf",
        page_ids=(TOPOLOGY_PAGE_ID, support_page_id),
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

    unique_labels = {}
    grouped = {}
    for room in rooms.rooms:
        label = _norm(room.room_label)
        if (
            room.geometry_complete
            and label
            and str(room.physical_room_id or "").strip()
            and str(room.source_room_face_record_id or "").strip()
            and str(room.room_label_binding_record_id or "").strip()
            and bool(room.room_label_evidence_ids)
        ):
            grouped.setdefault(label, []).append(room)
    for label, values in grouped.items():
        if len(values) == 1:
            unique_labels[label] = values[0]

    trusted_lines = cross_view._trusted_lines_for_page(
        source,
        revision_id=published.revision.revision_id,
        page_id=support_page_id,
        candidate_labels=tuple(unique_labels),
    )
    relevant_lines = tuple(
        line
        for line in trusted_lines
        if (
            _norm(line.text) in unique_labels
            and str(unique_labels[_norm(line.text)].page_id) != support_page_id
        )
    )
    dimensions = cross_view._trusted_native_dimensions_for_page(
        source,
        revision_id=published.revision.revision_id,
        page_id=support_page_id,
        candidate_lines=relevant_lines,
    ) if relevant_lines else ()

    result = CrossViewRoomAreaProducer.from_source(
        source=source,
        rooms=rooms,
    ).publish()

    records = [
        {
            "room_label": _norm(record.room_label),
            "physical_room_id": record.physical_room_id,
            "source_room_face_record_id": record.source_room_face_record_id,
            "source_dimension_page_id": record.source_dimension_page_id,
            "area_m2": record.area_evidence.normalized_value,
            "support_mode": record.area_evidence.metadata.get(
                "source_label_support_mode"
            ),
            "horizontal_value_mm": record.area_evidence.metadata.get(
                "horizontal_value_mm"
            ),
            "vertical_value_mm": record.area_evidence.metadata.get(
                "vertical_value_mm"
            ),
        }
        for record in result.records
    ]

    print(json.dumps({
        "source_sha256": source_sha,
        "support_page_id": support_page_id,
        "support_page_title": None if decision is None else decision.title,
        "support_page_classification": (
            None if decision is None else decision.classification
        ),
        "support_page_view_types": (
            [] if decision is None else list(decision.view_types)
        ),
        "trusted_support_labels": sorted(
            {_norm(line.text) for line in relevant_lines}
        ),
        "trusted_dimension_count": len(dimensions),
        "trusted_horizontal_dimension_count": sum(
            item.orientation == cross_view.DimensionOrientation.HORIZONTAL.value
            for item in dimensions
        ),
        "trusted_vertical_dimension_count": sum(
            item.orientation == cross_view.DimensionOrientation.VERTICAL.value
            for item in dimensions
        ),
        "cross_view_status": getattr(result.status, "value", str(result.status)),
        "cross_view_reason_codes": list(result.reason_codes),
        "records": records,
        "freezer_records": [
            record for record in records if record["room_label"] == "FREEZER"
        ],
        "elapsed_seconds": time.perf_counter() - started,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
