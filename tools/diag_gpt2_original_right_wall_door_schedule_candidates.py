"""Original native manufacturer-door word roles on one source-room side.

No word adjacency, panel width or printed door-code label grants a physical
opening, door count or measured room/threshold quantity.
"""
from __future__ import annotations

import hashlib
import math
import re

import fitz


def audit_original_wall_side_door_code_source_candidates(
    pdf_bytes:bytes, *, expected_sha256:str,
    plan_page_1_based:int, schedule_page_1_based:int,
    candidate_right_face_x_pdf_pts:float,
    candidate_wall_y_span_pdf_pts:tuple[float,float],
    explicit_door_code_schedule_blocks:tuple[tuple[str,int],...],
    maximum_code_word_distance_pdf_pts:float=0.5,
) -> dict:
    if (type(pdf_bytes) is not bytes or type(expected_sha256) is not str
            or not re.fullmatch(r"[0-9a-f]{64}",expected_sha256)
            or hashlib.sha256(pdf_bytes).hexdigest()!=expected_sha256):
        raise ValueError("immutable_original_door_source_sha_required")
    if (type(plan_page_1_based) is not int
            or type(schedule_page_1_based) is not int
            or min(plan_page_1_based,schedule_page_1_based)<=0
            or plan_page_1_based==schedule_page_1_based):
        raise ValueError("distinct_original_door_plan_schedule_pages_required")
    if (type(candidate_right_face_x_pdf_pts) not in (int,float)
            or not math.isfinite(candidate_right_face_x_pdf_pts)
            or type(candidate_wall_y_span_pdf_pts) not in (tuple,list)
            or len(candidate_wall_y_span_pdf_pts)!=2
            or any(type(v) not in (int,float) or not math.isfinite(v)
                   for v in candidate_wall_y_span_pdf_pts)
            or candidate_wall_y_span_pdf_pts[0]>=candidate_wall_y_span_pdf_pts[1]
            or type(maximum_code_word_distance_pdf_pts) not in (int,float)
            or not math.isfinite(maximum_code_word_distance_pdf_pts)
            or maximum_code_word_distance_pdf_pts<=0):
        raise ValueError("original_wall_face_source_geometry_invalid")
    if (type(explicit_door_code_schedule_blocks) not in (tuple,list)
            or not 1<=len(explicit_door_code_schedule_blocks)<=32):
        raise ValueError("original_door_schedule_universe_invalid")
    codes={}
    for row in explicit_door_code_schedule_blocks:
        if (type(row) not in (tuple,list) or len(row)!=2
                or type(row[0]) is not str
                or not re.fullmatch(r"D[1-9][0-9]{0,3}",row[0])
                or type(row[1]) is not int or row[1]<0
                or row[0] in codes or row[1] in codes.values()):
            raise ValueError("original_door_schedule_code_alias")
        codes[row[0]]=row[1]
    with fitz.open(stream=pdf_bytes,filetype="pdf") as doc:
        if max(plan_page_1_based,schedule_page_1_based)>len(doc):
            raise ValueError("original_door_source_page_unavailable")
        plan=doc[plan_page_1_based-1].get_text("words",sort=False)
        schedule=doc[schedule_page_1_based-1].get_text("words",sort=False)
    y0,y1=map(float,candidate_wall_y_span_pdf_pts)
    rows=[]
    for code,block in codes.items():
        schedule_row=sorted((w for w in schedule if int(w[5])==block),
                            key=lambda w:(int(w[6]),int(w[7])))
        if (not schedule_row or str(schedule_row[0][4])!=code
                or sum(str(w[4])==code for w in schedule_row)!=1):
            raise ValueError("original_door_schedule_row_code_conflict")
        same_code=[w for w in plan if str(w[4])==code]
        def receipt(w,page):
            return {
                "native_source_word_address":(page,int(w[5]),int(w[6]),int(w[7])),
                "original_word_bbox_pdf_pts":tuple(float(v) for v in w[:4]),
                "raw_text_untrusted":str(w[4]),
                "source_glyph_clip_verified":False,
            }
        near=[]
        far=[]
        for word in same_code:
            a,b,c,d=map(float,word[:4])
            on_wall=(abs(a-candidate_right_face_x_pdf_pts)
                     <=maximum_code_word_distance_pdf_pts
                     and b<y1 and d>y0)
            (near if on_wall else far).append(receipt(word,plan_page_1_based))
        rows.append({
            "door_code_untrusted":code,
            "original_schedule_native_block":block,
            "all_original_schedule_row_text":tuple(
                str(w[4]) for w in schedule_row
            ),
            "original_plan_same_code_at_candidate_right_face":tuple(near),
            "original_plan_same_code_outside_candidate_right_face":tuple(far),
            "plan_door_physical_opening_owner_proven":False,
            "door_area_or_count_authority_proven":False,
        })
    return {
        "status":"original_wall_door_word_schedule_roles_source_candidates",
        "original_source_sha256":expected_sha256,
        "all_explicit_door_schedule_candidates":tuple(rows),
        "original_door_ink_and_schedule_does_not_measure_opening":True,
        "new_firm_quantities":0,
    }
