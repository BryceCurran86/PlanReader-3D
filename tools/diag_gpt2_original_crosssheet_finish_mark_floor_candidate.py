"""Candidate cross-sheet source room vs exact native printed finish words.

Source-only negative/positive lexical census. Translation and source room
identity are caller hypotheses, not physical wall registration authority.
"""
from __future__ import annotations

import math
from tools.gpt2_native_material_mark_census import census_native_plan_material_words


def audit_original_crosssheet_candidate_floor_finish_words(
    original_pdf_bytes:bytes, *, expected_sha256:str,
    original_floor_page_1_based:int, original_finish_page_1_based:int,
    candidate_original_floor_bbox_pdf_pts:tuple[float,float,float,float],
    unproven_original_source_translation_pdf_pts:tuple[float,float],
    candidate_finish_code_words:tuple[str,...]=("FT2","FT3"),
    original_finish_viewport_id:str,
) -> dict:
    if (type(original_floor_page_1_based) is not int
            or type(original_finish_page_1_based) is not int
            or original_floor_page_1_based<=0 or original_finish_page_1_based<=0
            or original_floor_page_1_based==original_finish_page_1_based):
        raise ValueError("distinct_original_floor_finish_pages_required")
    if (type(candidate_original_floor_bbox_pdf_pts) not in (tuple,list)
            or len(candidate_original_floor_bbox_pdf_pts)!=4
            or any(type(v) not in (float,int) or not math.isfinite(v)
                   for v in candidate_original_floor_bbox_pdf_pts)
            or candidate_original_floor_bbox_pdf_pts[2]<=candidate_original_floor_bbox_pdf_pts[0]
            or candidate_original_floor_bbox_pdf_pts[3]<=candidate_original_floor_bbox_pdf_pts[1]):
        raise ValueError("source_candidate_floor_bbox_invalid")
    if (type(unproven_original_source_translation_pdf_pts) not in (tuple,list)
            or len(unproven_original_source_translation_pdf_pts)!=2
            or any(type(v) not in (float,int) or not math.isfinite(v)
                   for v in unproven_original_source_translation_pdf_pts)):
        raise ValueError("source_registration_hypothesis_finite_required")
    x0,y0,x1,y1=map(float,candidate_original_floor_bbox_pdf_pts)
    dx,dy=map(float,unproven_original_source_translation_pdf_pts)
    bbox=(x0+dx,y0+dy,x1+dx,y1+dy)
    if not all(math.isfinite(v) for v in bbox):
        raise ValueError("transformed_source_bbox_nonfinite")
    mark_inventory=census_native_plan_material_words(
        original_pdf_bytes,expected_sha256=expected_sha256,
        page_number=original_finish_page_1_based,
        plan_view_bbox_pdf_pts=bbox,
        codes=candidate_finish_code_words,
        viewport_id=original_finish_viewport_id,
    )
    if mark_inventory["boundary_crossing_plan_words"]:
        return {
            "status":"source_printed_finish_marks_cross_candidate_floor_boundary",
            "source_marks":mark_inventory,
            "new_firm_quantities":0,
            "cross_page_structural_room_equivalence_proven":False,
        }
    return {
        "status":(
            "printed_finish_marks_inside_unproven_translated_floor_candidate"
            if mark_inventory["within_supplied_plan_view"]
            else "no_printed_finish_mark_inside_unproven_translated_floor_candidate"
        ),
        "original_source_sha256":expected_sha256,
        "original_floor_page_1_based":original_floor_page_1_based,
        "original_finish_page_1_based":original_finish_page_1_based,
        "unproven_original_source_translation_pdf_pts":(dx,dy),
        "source_floor_bbox_translated_but_unowned_pdf_pts":bbox,
        "native_finish_words_inside_candidate":mark_inventory["within_supplied_plan_view"],
        "all_native_finish_word_competitors_outside_candidate":
            mark_inventory["outside_supplied_plan_view"],
        "cross_page_structural_room_equivalence_proven":False,
        "finish_material_occurrence_issuer_proven":False,
        "finished_face_geometry_authenticated":False,
        "new_firm_quantities":0,
    }
