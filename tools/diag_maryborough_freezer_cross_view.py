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
SUPPORT_PAGE_ID = "11"


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())


def _dim_payload(item) -> dict:
    return {
        "dimension_id": str(item.dimension_id),
        "orientation": str(item.orientation),
        "value_mm": float(item.value_mm),
        "endpoints_pt": [
            [float(item.endpoints_pt[0][0]), float(item.endpoints_pt[0][1])],
            [float(item.endpoints_pt[1][0]), float(item.endpoints_pt[1][1])],
        ],
        "text_block_no": item.text_block_no,
        "text_line_no": item.text_line_no,
        "text_word_no": item.text_word_no,
        "text_source_partition_id": str(item.text_source_partition_id),
        "witness_observation_ids": list(item.witness_observation_ids),
        "witness_geometries": [list(value) for value in item.witness_geometries],
    }


def main() -> int:
    started = time.perf_counter()
    payload = SOURCE.read_bytes()
    source_sha = hashlib.sha256(payload).hexdigest()
    source = SourceVisibilityProducer(
        producer_method="diag-gpt2-maryborough-freezer-cross-view",
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
        canonical_wall_ids_by_candidate=(
            canonical_walls.candidate_to_canonical_wall_id
        ),
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

    trusted_lines = cross_view._trusted_lines_for_page(
        source,
        revision_id=published.revision.revision_id,
        page_id=SUPPORT_PAGE_ID,
        candidate_labels=tuple(unique_labels),
    )
    relevant_lines = tuple(
        line
        for line in trusted_lines
        if (
            _norm(line.text) in unique_labels
            and str(unique_labels[_norm(line.text)].page_id) != SUPPORT_PAGE_ID
        )
    )
    trusted_dimensions = cross_view._trusted_native_dimensions_for_page(
        source,
        revision_id=published.revision.revision_id,
        page_id=SUPPORT_PAGE_ID,
        candidate_lines=relevant_lines,
    )

    horizontals = tuple(
        item
        for item in trusted_dimensions
        if item.orientation == cross_view.DimensionOrientation.HORIZONTAL.value
    )
    verticals = tuple(
        item
        for item in trusted_dimensions
        if item.orientation == cross_view.DimensionOrientation.VERTICAL.value
    )

    labels = {}
    for label in sorted(unique_labels):
        label_lines = tuple(line for line in relevant_lines if _norm(line.text) == label)

        regular_spatial = []
        regular_scale = []
        regular_witness = []
        for line in label_lines:
            for horizontal in horizontals:
                for vertical in verticals:
                    key = (
                        str(line.source_partition_id),
                        int(line.block_no),
                        int(line.line_no),
                        str(horizontal.dimension_id),
                        str(vertical.dimension_id),
                    )
                    if not cross_view._line_inside_dimension_pair(
                        line, horizontal, vertical
                    ):
                        continue
                    regular_spatial.append(key)
                    if not cross_view._figured_pair_scale_consistent(
                        page_id=SUPPORT_PAGE_ID,
                        horizontal=horizontal,
                        vertical=vertical,
                    ):
                        continue
                    regular_scale.append(key)
                    if not cross_view._witness_systems_intersect(
                        horizontal, vertical
                    ):
                        continue
                    regular_witness.append(key)

        annotation_h = tuple(
            (line, dimension)
            for line in label_lines
            for dimension in horizontals
            if cross_view._dimension_is_immediate_label_annotation(line, dimension)
        )
        annotation_v = tuple(
            (line, dimension)
            for line in label_lines
            for dimension in verticals
            if cross_view._dimension_is_immediate_label_annotation(line, dimension)
        )
        annotation_pairs = []
        seen_annotation = set()
        for horizontal_line, horizontal in annotation_h:
            for vertical_line, vertical in annotation_v:
                if not cross_view._figured_pair_scale_consistent(
                    page_id=SUPPORT_PAGE_ID,
                    horizontal=horizontal,
                    vertical=vertical,
                ):
                    continue
                key = (
                    SUPPORT_PAGE_ID,
                    str(horizontal.dimension_id),
                    str(vertical.dimension_id),
                )
                if key in seen_annotation:
                    continue
                seen_annotation.add(key)
                annotation_pairs.append(
                    {
                        "horizontal_label_block": int(horizontal_line.block_no),
                        "vertical_label_block": int(vertical_line.block_no),
                        "horizontal_dimension_id": str(horizontal.dimension_id),
                        "vertical_dimension_id": str(vertical.dimension_id),
                        "horizontal_value_mm": float(horizontal.value_mm),
                        "vertical_value_mm": float(vertical.value_mm),
                    }
                )

        final_match_count = (
            len(regular_witness)
            if regular_witness
            else len(annotation_pairs)
        )

        if not label_lines:
            first_failed_gate = "trusted_support_label"
        elif not horizontals:
            first_failed_gate = "trusted_horizontal_dimensions"
        elif not verticals:
            first_failed_gate = "trusted_vertical_dimensions"
        elif not regular_spatial and not annotation_h and not annotation_v:
            first_failed_gate = "label_dimension_ownership"
        elif regular_spatial and not regular_scale:
            first_failed_gate = "figured_pair_scale_consistency"
        elif regular_scale and not regular_witness:
            first_failed_gate = "witness_system_intersection"
        elif not regular_witness and (not annotation_h or not annotation_v):
            first_failed_gate = "orthogonal_annotation_pair"
        elif final_match_count == 0:
            first_failed_gate = "unique_cross_view_pair"
        elif final_match_count > 1:
            first_failed_gate = "ambiguous_multiple_cross_view_pairs"
        else:
            first_failed_gate = None

        labels[label] = {
            "topology_room_id": str(unique_labels[label].physical_room_id),
            "source_room_face_record_id": str(
                unique_labels[label].source_room_face_record_id
            ),
            "support_label_line_count": len(label_lines),
            "support_label_lines": [
                {
                    "text": line.text,
                    "bbox": list(line.bbox),
                    "source_partition_id": line.source_partition_id,
                    "block_no": line.block_no,
                    "line_no": line.line_no,
                    "observation_ids": list(line.observation_ids),
                    "receipt_ids": list(line.receipt_ids),
                }
                for line in label_lines
            ],
            "regular_spatial_pair_count": len(regular_spatial),
            "regular_scale_consistent_pair_count": len(regular_scale),
            "regular_witness_intersecting_pair_count": len(regular_witness),
            "annotation_horizontal_count": len(annotation_h),
            "annotation_vertical_count": len(annotation_v),
            "annotation_pair_count": len(annotation_pairs),
            "annotation_pairs": annotation_pairs,
            "production_equivalent_final_match_count": final_match_count,
            "first_failed_gate": first_failed_gate,
        }

    output = {
        "source_sha256": source_sha,
        "revision_id": published.revision.revision_id,
        "topology_page_id": TOPOLOGY_PAGE_ID,
        "support_page_id": SUPPORT_PAGE_ID,
        "room_composition_status": getattr(
            rooms.status, "value", str(rooms.status)
        ),
        "room_count": len(rooms.rooms),
        "eligible_labelled_room_count": len(eligible),
        "unique_topology_labels": sorted(unique_labels),
        "trusted_support_line_count": len(relevant_lines),
        "trusted_support_lines": [
            {
                "text": line.text,
                "bbox": list(line.bbox),
                "source_partition_id": line.source_partition_id,
                "block_no": line.block_no,
                "line_no": line.line_no,
            }
            for line in relevant_lines
        ],
        "trusted_dimension_count": len(trusted_dimensions),
        "trusted_horizontal_dimension_count": len(horizontals),
        "trusted_vertical_dimension_count": len(verticals),
        "trusted_dimensions": [_dim_payload(item) for item in trusted_dimensions],
        "labels": labels,
        "elapsed_seconds": time.perf_counter() - started,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
