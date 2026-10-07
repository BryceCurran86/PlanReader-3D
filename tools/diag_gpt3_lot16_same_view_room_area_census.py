from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pb_cross_view_room_area_authority import (
    _figured_pair_scale_consistent,
    _line_inside_dimension_pair,
    _norm_label,
    _trusted_lines_for_page,
    _trusted_native_dimensions_for_page,
    _witness_systems_intersect,
)
from pb_dimension_evidence_v172 import DimensionOrientation
from pb_live_canonical_room_composition import compose_live_canonical_rooms
from pb_live_canonical_wall_composition import compose_live_canonical_walls
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_visibility_authority import SourceVisibilityProducer


PDF=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA="10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID="3"


def main():
    payload=PDF.read_bytes()
    source_sha=hashlib.sha256(payload).hexdigest()
    if source_sha != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {source_sha}")

    source=SourceVisibilityProducer(
        producer_method="diag-lot16-same-view-room-area-census",
        producer_version="1",
    )
    published=source.ingest_native_pdf_bytes(
        document_id=f"diag:{source_sha[:32]}",
        source_bytes=payload,
        source_locator=str(PDF),
        page_ids=tuple(str(i) for i in range(1,14)),
    )
    wall_opening=compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=(PAGE_ID,),
        evidence_page_ids=tuple(str(i) for i in range(1,14) if str(i)!=PAGE_ID),
    )
    walls=compose_live_canonical_walls(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )
    rooms=compose_live_canonical_rooms(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
        canonical_wall_ids_by_candidate=walls.candidate_to_canonical_wall_id,
        unresolved_wall_candidate_ids=walls.unresolved_wall_candidate_ids,
    )

    eligible=[
        room for room in rooms.rooms
        if room.geometry_complete
        and str(room.physical_room_id or "").strip()
        and str(room.source_room_face_record_id or "").strip()
        and _norm_label(room.room_label)
        and str(room.room_label_binding_record_id or "").strip()
        and bool(room.room_label_evidence_ids)
        and str(room.page_id)==PAGE_ID
    ]
    labels={}
    for room in eligible:
        labels.setdefault(_norm_label(room.room_label),[]).append(room)
    unique={label:group[0] for label,group in labels.items() if len(group)==1}

    lines=_trusted_lines_for_page(
        source,
        revision_id=published.revision.revision_id,
        page_id=PAGE_ID,
        candidate_labels=tuple(unique),
    )
    relevant=tuple(
        line for line in lines if _norm_label(line.text) in unique
    )
    dims=_trusted_native_dimensions_for_page(
        source,
        revision_id=published.revision.revision_id,
        page_id=PAGE_ID,
        candidate_lines=relevant,
    )
    hs=tuple(d for d in dims if d.orientation==DimensionOrientation.HORIZONTAL.value)
    vs=tuple(d for d in dims if d.orientation==DimensionOrientation.VERTICAL.value)

    rows=[]
    for label,room in sorted(unique.items()):
        room_lines=[line for line in relevant if _norm_label(line.text)==label]
        matches=[]
        for line in room_lines:
            for h in hs:
                for v in vs:
                    if (
                        _line_inside_dimension_pair(line,h,v)
                        and _figured_pair_scale_consistent(page_id=PAGE_ID,horizontal=h,vertical=v)
                        and _witness_systems_intersect(h,v)
                    ):
                        matches.append({
                            "label":line.text,
                            "horizontal_dimension_id":h.dimension_id,
                            "horizontal_value_mm":int(h.value_mm),
                            "vertical_dimension_id":v.dimension_id,
                            "vertical_value_mm":int(v.value_mm),
                            "area_m2":round(float(h.value_mm)*float(v.value_mm)/1_000_000.0,6),
                        })
        rows.append({
            "physical_room_id":str(room.physical_room_id),
            "room_label":str(room.room_label),
            "trusted_label_line_count":len(room_lines),
            "same_view_match_count":len(matches),
            "matches":matches,
        })

    payload_out={
        "source_sha256":source_sha,
        "canonical_room_count":len(rooms.rooms),
        "eligible_same_view_room_count":len(eligible),
        "unique_label_room_count":len(unique),
        "trusted_relevant_label_line_count":len(relevant),
        "trusted_horizontal_dimension_count":len(hs),
        "trusted_vertical_dimension_count":len(vs),
        "rooms_with_exactly_one_same_view_pair":sum(1 for r in rows if r["same_view_match_count"]==1),
        "rooms_with_ambiguous_same_view_pairs":sum(1 for r in rows if r["same_view_match_count"]>1),
        "rows":rows,
    }
    print(json.dumps(payload_out,indent=2,sort_keys=True))


if __name__=="__main__":
    main()
