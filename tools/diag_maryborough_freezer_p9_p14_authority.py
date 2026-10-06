from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pb_cross_view_room_area_authority as cross_view
from pb_live_canonical_room_composition import compose_live_canonical_rooms
from pb_live_canonical_wall_composition import compose_live_canonical_walls
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_visibility_authority import SourceVisibilityProducer


SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
TOPOLOGY_PAGE_ID = "7"
SUPPORT_PAGE_IDS = ("9", "14")
TARGET = "FREEZER"


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())


def _pair_payload(horizontal, vertical) -> dict:
    return {
        "horizontal_dimension_id": str(horizontal.dimension_id),
        "horizontal_value_mm": float(horizontal.value_mm),
        "horizontal_endpoints_pt": [
            list(horizontal.endpoints_pt[0]),
            list(horizontal.endpoints_pt[1]),
        ],
        "vertical_dimension_id": str(vertical.dimension_id),
        "vertical_value_mm": float(vertical.value_mm),
        "vertical_endpoints_pt": [
            list(vertical.endpoints_pt[0]),
            list(vertical.endpoints_pt[1]),
        ],
        "area_m2_if_owned": round(
            float(horizontal.value_mm) * float(vertical.value_mm) / 1_000_000.0,
            9,
        ),
    }


def main() -> int:
    started = time.perf_counter()
    payload = SOURCE.read_bytes()
    source_sha = hashlib.sha256(payload).hexdigest()
    source = SourceVisibilityProducer(
        producer_method="diag-gpt2-freezer-p9-p14-authority",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"diag-maryborough:{source_sha[:32]}",
        source_bytes=payload,
        source_locator="memory://diag-maryborough-source.pdf",
        page_ids=(TOPOLOGY_PAGE_ID, *SUPPORT_PAGE_IDS),
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

    eligible = [
        room
        for room in rooms.rooms
        if room.geometry_complete
        and str(room.physical_room_id or "").strip()
        and str(room.source_room_face_record_id or "").strip()
        and _norm(room.room_label)
        and str(room.room_label_binding_record_id or "").strip()
        and bool(room.room_label_evidence_ids)
    ]
    grouped: dict[str, list[object]] = {}
    for room in eligible:
        grouped.setdefault(_norm(room.room_label), []).append(room)
    unique_labels = {
        label: values[0]
        for label, values in grouped.items()
        if len(values) == 1
    }
    target_room = unique_labels.get(TARGET)
    if target_room is None:
        raise RuntimeError("FREEZER is not a unique authenticated topology room")

    pages = {}
    for page_id in SUPPORT_PAGE_IDS:
        trusted_lines = cross_view._trusted_lines_for_page(
            source,
            revision_id=published.revision.revision_id,
            page_id=page_id,
            candidate_labels=tuple(unique_labels),
        )
        relevant_lines = tuple(
            line
            for line in trusted_lines
            if (
                _norm(line.text) == TARGET
                and str(target_room.page_id) != str(page_id)
            )
        )
        trusted_dimensions = cross_view._trusted_native_dimensions_for_page(
            source,
            revision_id=published.revision.revision_id,
            page_id=page_id,
            candidate_lines=relevant_lines,
        ) if relevant_lines else ()

        horizontals = tuple(
            d for d in trusted_dimensions
            if d.orientation == cross_view.DimensionOrientation.HORIZONTAL.value
        )
        verticals = tuple(
            d for d in trusted_dimensions
            if d.orientation == cross_view.DimensionOrientation.VERTICAL.value
        )

        spatial = []
        scale = []
        witness = []
        for line in relevant_lines:
            for horizontal in horizontals:
                for vertical in verticals:
                    if not cross_view._line_inside_dimension_pair(
                        line, horizontal, vertical
                    ):
                        continue
                    spatial.append(_pair_payload(horizontal, vertical))
                    if not cross_view._figured_pair_scale_consistent(
                        page_id=page_id,
                        horizontal=horizontal,
                        vertical=vertical,
                    ):
                        continue
                    scale.append(_pair_payload(horizontal, vertical))
                    if not cross_view._witness_systems_intersect(
                        horizontal, vertical
                    ):
                        continue
                    witness.append(_pair_payload(horizontal, vertical))

        owned_h = tuple(
            (line, dim)
            for line in relevant_lines
            for dim in horizontals
            if cross_view._dimension_is_immediate_label_annotation(line, dim)
        )
        owned_v = tuple(
            (line, dim)
            for line in relevant_lines
            for dim in verticals
            if cross_view._dimension_is_immediate_label_annotation(line, dim)
        )
        annotation = []
        seen = set()
        for h_line, horizontal in owned_h:
            for v_line, vertical in owned_v:
                if not cross_view._figured_pair_scale_consistent(
                    page_id=page_id,
                    horizontal=horizontal,
                    vertical=vertical,
                ):
                    continue
                key = (horizontal.dimension_id, vertical.dimension_id)
                if key in seen:
                    continue
                seen.add(key)
                annotation.append(_pair_payload(horizontal, vertical))

        pages[page_id] = {
            "support_label_line_count": len(relevant_lines),
            "support_label_lines": [
                {
                    "text": line.text,
                    "bbox": list(line.bbox),
                    "block_no": line.block_no,
                    "line_no": line.line_no,
                    "source_partition_id": line.source_partition_id,
                }
                for line in relevant_lines
            ],
            "trusted_dimension_count": len(trusted_dimensions),
            "trusted_dimensions": [
                {
                    "dimension_id": str(d.dimension_id),
                    "orientation": str(d.orientation),
                    "value_mm": float(d.value_mm),
                    "endpoints_pt": [
                        list(d.endpoints_pt[0]), list(d.endpoints_pt[1])
                    ],
                    "text_block_no": d.text_block_no,
                    "text_line_no": d.text_line_no,
                    "text_word_no": d.text_word_no,
                }
                for d in trusted_dimensions
            ],
            "horizontal_count": len(horizontals),
            "vertical_count": len(verticals),
            "spatial_pair_count": len(spatial),
            "spatial_pairs": spatial,
            "scale_consistent_pair_count": len(scale),
            "scale_consistent_pairs": scale,
            "witness_intersecting_pair_count": len(witness),
            "witness_intersecting_pairs": witness,
            "annotation_horizontal_count": len(owned_h),
            "annotation_vertical_count": len(owned_v),
            "annotation_pair_count": len(annotation),
            "annotation_pairs": annotation,
        }

    published_result = cross_view.CrossViewRoomAreaProducer.from_source(
        source=source,
        rooms=rooms,
    ).publish()
    freezer_records = [
        {
            "physical_room_id": record.physical_room_id,
            "room_label": record.room_label,
            "source_dimension_page_id": record.source_dimension_page_id,
            "horizontal_dimension_id": record.horizontal_dimension_id,
            "vertical_dimension_id": record.vertical_dimension_id,
            "area_m2": record.area_evidence.normalized_value,
            "support_mode": record.area_evidence.metadata.get(
                "source_label_support_mode"
            ),
        }
        for record in published_result.records
        if _norm(record.room_label) == TARGET
    ]

    print(json.dumps({
        "source_sha256": source_sha,
        "decoded_pages": list(published.coverage.decoded_pages),
        "topology_room_id": target_room.physical_room_id,
        "topology_source_room_face_record_id": target_room.source_room_face_record_id,
        "pages": pages,
        "cross_view_result_status": getattr(
            published_result.status, "value", str(published_result.status)
        ),
        "cross_view_reason_codes": list(published_result.reason_codes),
        "freezer_records": freezer_records,
        "freezer_unresolved": str(target_room.physical_room_id)
        in set(published_result.unresolved_physical_room_ids),
        "elapsed_seconds": time.perf_counter() - started,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
