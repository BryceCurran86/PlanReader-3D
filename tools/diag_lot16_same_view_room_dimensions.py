from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from pb_cross_view_room_area_authority import (
    DimensionOrientation,
    _dimension_is_immediate_label_annotation,
    _figured_pair_scale_consistent,
    _line_inside_dimension_pair,
    _norm_label,
    _trusted_lines_for_page,
    _trusted_native_dimensions_for_page,
    _witness_systems_intersect,
)
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from pb_source_visibility_authority import SourceVisibilityProducer


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_INDEX = 2
PAGE_ID = "3"


def main() -> None:
    source_bytes = PDF.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    if source_sha != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {source_sha}")

    claim = collect_live_physical_net_wall_claim(
        PDF,
        pages=(PAGE_INDEX,),
        topology_pages=(PAGE_INDEX,),
        room_area_support_pages=None,
    )

    labelled = [
        room for room in claim.canonical_rooms
        if room.geometry_complete
        and _norm_label(room.room_label)
        and str(room.physical_room_id or "").strip()
        and str(room.source_room_face_record_id or "").strip()
        and str(room.room_label_binding_record_id or "").strip()
        and bool(room.room_label_evidence_ids)
    ]
    by_label = {}
    for room in labelled:
        by_label.setdefault(_norm_label(room.room_label), []).append(room)
    unique = {
        label: rooms[0]
        for label, rooms in by_label.items()
        if len(rooms) == 1
    }

    source = SourceVisibilityProducer(
        producer_method="diag_lot16_same_view_room_dimensions",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="diag-lot16-same-view-room-dimensions",
        source_bytes=source_bytes,
        source_locator=str(PDF),
        page_ids=(PAGE_ID,),
    )

    trusted_lines = _trusted_lines_for_page(
        source,
        revision_id=published.revision.revision_id,
        page_id=PAGE_ID,
        candidate_labels=tuple(unique),
    )
    relevant_lines = tuple(
        line for line in trusted_lines
        if _norm_label(line.text) in unique
    )
    trusted_dimensions = _trusted_native_dimensions_for_page(
        source,
        revision_id=published.revision.revision_id,
        page_id=PAGE_ID,
        candidate_lines=relevant_lines,
    )

    horizontals = tuple(
        item for item in trusted_dimensions
        if item.orientation == DimensionOrientation.HORIZONTAL.value
    )
    verticals = tuple(
        item for item in trusted_dimensions
        if item.orientation == DimensionOrientation.VERTICAL.value
    )

    rows = []
    summary = Counter()
    for label, room in sorted(unique.items()):
        label_lines = tuple(
            line for line in relevant_lines if _norm_label(line.text) == label
        )
        matches = []
        for line in label_lines:
            for horizontal in horizontals:
                for vertical in verticals:
                    if (
                        _line_inside_dimension_pair(line, horizontal, vertical)
                        and _figured_pair_scale_consistent(
                            page_id=PAGE_ID,
                            horizontal=horizontal,
                            vertical=vertical,
                        )
                        and _witness_systems_intersect(horizontal, vertical)
                    ):
                        matches.append((line, horizontal, vertical, "contained_witness_pair"))

        if not matches:
            seen = set()
            owned_h = tuple(
                (line, dim)
                for line in label_lines
                for dim in horizontals
                if _dimension_is_immediate_label_annotation(line, dim)
            )
            owned_v = tuple(
                (line, dim)
                for line in label_lines
                for dim in verticals
                if _dimension_is_immediate_label_annotation(line, dim)
            )
            for h_line, horizontal in owned_h:
                for v_line, vertical in owned_v:
                    if not _figured_pair_scale_consistent(
                        page_id=PAGE_ID,
                        horizontal=horizontal,
                        vertical=vertical,
                    ):
                        continue
                    key=(horizontal.dimension_id, vertical.dimension_id)
                    if key in seen:
                        continue
                    seen.add(key)
                    matches.append((
                        h_line,
                        horizontal,
                        vertical,
                        "immediate_annotation_pair",
                    ))

        if len(matches) == 1:
            line, horizontal, vertical, mode = matches[0]
            area = round(
                float(horizontal.value_mm)
                * float(vertical.value_mm)
                / 1_000_000.0,
                6,
            )
            category = "unique_same_view_figured_area"
            summary[category] += 1
            row = {
                "label": label,
                "physical_room_id": room.physical_room_id,
                "source_room_face_record_id": room.source_room_face_record_id,
                "match_count": 1,
                "mode": mode,
                "area_m2": area,
                "horizontal_value_mm": horizontal.value_mm,
                "vertical_value_mm": vertical.value_mm,
                "horizontal_dimension_id": horizontal.dimension_id,
                "vertical_dimension_id": vertical.dimension_id,
                "source_label_text": line.text,
            }
        elif len(matches) > 1:
            category = "ambiguous_same_view_figured_area"
            summary[category] += 1
            row = {
                "label": label,
                "physical_room_id": room.physical_room_id,
                "source_room_face_record_id": room.source_room_face_record_id,
                "match_count": len(matches),
            }
        else:
            category = "same_view_figured_area_unavailable"
            summary[category] += 1
            row = {
                "label": label,
                "physical_room_id": room.physical_room_id,
                "source_room_face_record_id": room.source_room_face_record_id,
                "match_count": 0,
            }
        rows.append(row)

    print(json.dumps({
        "source_sha256": source_sha,
        "canonical_room_count": len(claim.canonical_rooms),
        "eligible_labelled_room_count": len(labelled),
        "unique_label_count": len(unique),
        "trusted_label_line_count": len(relevant_lines),
        "trusted_dimension_count": len(trusted_dimensions),
        "trusted_horizontal_count": len(horizontals),
        "trusted_vertical_count": len(verticals),
        "summary": dict(sorted(summary.items())),
        "rows": rows,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
