"""Read-only original-page physical-room / FT3 mark crossview hypothesis census.

This never creates a construction object, measurement or quantity.  A common
native construction-grid transform does NOT prove the same physical room,
wall, material occurrence or plan role.  Report actual positive and competing
source candidates so the next typed source authority can prove OR abstain.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import fitz
from shapely.geometry import Polygon, Point

from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from pb_source_grid_registration_shadow import source_grid_registration_shadow


def original_cross_view_room_mark_candidates(
    path: Path, *, expected_sha256: str,
    source_room_page_index: int, source_mark_page_index: int,
    material_code: str,
) -> dict:
    original=path.read_bytes()
    sha=hashlib.sha256(original).hexdigest()
    if sha!=expected_sha256:
        raise ValueError("original PDF source SHA mismatch")
    if not material_code.isalnum() or not material_code.isupper():
        raise ValueError("material mark must be a literal uppercase token")
    grid=source_grid_registration_shadow(
        original,expected_sha256=sha,
        first_page_index=source_room_page_index,
        second_page_index=source_mark_page_index,
    )
    result={
        "diagnostic_only":True,
        "source_sha256":sha,
        "original_source_room_page":source_room_page_index+1,
        "original_material_mark_page":source_mark_page_index+1,
        "material_code":material_code,
        "original_grid_native_vector_candidate":bool(
            grid.get("source_native_vector_grid_candidate") is True
        ),
        "grid_native_vector_delta_pdf_pts":grid.get(
            "native_vector_grid_translation_candidate_pdf_pts"
        ),
        "published_floor_finish_quantities":0,
        "physical_room_crossview_equivalence_proven":False,
        "material_occurrence_source_trusted":False,
        "page_material_role_proven":False,
        "original_room_wall_equivalence_proven":False,
        "commercial_projection_allowed":False,
        "first_unclosed_gate":"original_grid_native_vector_witness_unavailable",
        "source_room_candidates":[],
        "native_material_marks":[],
        "source_region_geometric_candidates":[],
    }
    if not result["original_grid_native_vector_candidate"]:
        return result
    dx,dy=result["grid_native_vector_delta_pdf_pts"]
    with fitz.open(stream=original,filetype="pdf") as doc:
        p=doc[source_mark_page_index]
        marks=[
            {
                "native_source_address":[int(word[5]),int(word[6]),int(word[7])],
                "native_bbox_pdf_pts":[round(float(v),6) for v in word[:4]],
                "source_word_text_only_not_raster_authority":str(word[4]),
            }
            for word in p.get_text("words")
            if len(word)>=8 and str(word[4]).strip()==material_code
        ]
    result["native_material_marks"]=marks

    claim=collect_live_physical_net_wall_claim(
        path,
        pages=(source_room_page_index,),
        topology_pages=(source_room_page_index,),
        room_area_support_pages=(source_mark_page_index,),
    )
    rooms=[]
    for room in claim.canonical_rooms:
        if (
            str(room.page_id)!=str(source_room_page_index+1)
            or not room.geometry_complete
            or not room.physical_room_id or not room.source_room_face_record_id
            or not room.room_label_binding_record_id
            or not room.room_label_evidence_ids
            or str(room.source_sha256).lower()!=sha
        ):
            continue
        polygon=tuple(room.polygon_pdf_pts)
        try:
            native=Polygon(polygon)
            if not native.is_valid or native.is_empty or native.area<=0 or native.interiors:
                continue
        except Exception:
            continue
        rooms.append((room,native))
    counts={}
    for room,_ in rooms:
        counts[str(room.physical_room_id)]=counts.get(str(room.physical_room_id),0)+1
    rooms=[(room,polygon) for room,polygon in rooms
           if counts[str(room.physical_room_id)]==1]
    result["source_room_candidates"]=[
        {
            "source_room_record_id":str(room.source_room_face_record_id),
            "canonical_room_id":str(room.canonical_room_id),
            "physical_room_id":str(room.physical_room_id),
            "native_geometry_area_page_pts2":float(room.area_page_pts2),
            "native_source_room_label":str(room.room_label),
            "native_source_room_bbox_pdf_pts":[round(v,6) for v in polygon.bounds],
            "source_wall_relationships_complete":bool(room.wall_relationships_complete),
            "source_bounding_wall_count":len(room.bounding_wall_ids),
        }
        for room,polygon in rooms
    ]

    # Source-native translate only: a geometry shadow to help find where a
    # *separate* physical source equivalence proof would have to start.
    # Do not match by room names, expected area, material kind, or proximity.
    candidates=[]
    for room,polygon in rooms:
        for mark in marks:
            x0,y0,x1,y1=mark["native_bbox_pdf_pts"]
            translated=Polygon([(x+dx,y+dy) for x,y in room.polygon_pdf_pts])
            corners=(
                Point(x0,y0),Point(x1,y0),Point(x0,y1),Point(x1,y1),
            )
            if all(translated.contains(point) for point in corners):
                candidates.append({
                    "original_source_room_face_id":str(room.source_room_face_record_id),
                    "original_room_id":str(room.physical_room_id),
                    "material_native_word_address":mark["native_source_address"],
                    "native_vector_transform_only_no_physical_authority":True,
                    "crossview_structural_wall_equivalence_proven":False,
                    "material_occurrence_owned":False,
                    "customer_quantity_issued":False,
                })
    result["source_region_geometric_candidates"]=candidates
    result["first_unclosed_gate"]=(
        "unique_physical_room_and_source_material_occurrence_binding_unproven"
        if candidates else "original_crossview_native_region_overlap_unproven"
    )
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf",type=Path,required=True)
    parser.add_argument("--sha256",required=True)
    parser.add_argument("--room-page",type=int,required=True)
    parser.add_argument("--material-page",type=int,required=True)
    parser.add_argument("--code",required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(argv)
    result=original_cross_view_room_mark_candidates(
        args.pdf, expected_sha256=args.sha256,
        source_room_page_index=args.room_page-1,
        source_mark_page_index=args.material_page-1,
        material_code=args.code,
    )
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(json.dumps({
        "source_sha256":result["source_sha256"],
        "original_grid_native_vector_candidate":result["original_grid_native_vector_candidate"],
        "source_room_candidates":len(result["source_room_candidates"]),
        "native_material_marks":len(result["native_material_marks"]),
        "source_region_geometric_candidates":result["source_region_geometric_candidates"],
        "first_unclosed_gate":result["first_unclosed_gate"],
        "commercial_projection_allowed":False,
    },sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
