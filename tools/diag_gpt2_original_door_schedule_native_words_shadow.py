"""Exact original door schedule row versus other same-code source words.

Read-only original SHA/source text inventory. Schedule description and plan
mark do not prove a structural wall gap, installed door or metric opening.
"""
from __future__ import annotations

import hashlib
import re
import fitz


def census_original_door_schedule_native_source(
    original_pdf_bytes: bytes, *, expected_sha256: str,
    schedule_page_1_based: int, plan_page_1_based: int,
    requested_door_code: str, schedule_native_block: int,
) -> dict:
    if (type(original_pdf_bytes) is not bytes
            or type(expected_sha256) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
            or hashlib.sha256(original_pdf_bytes).hexdigest()!=expected_sha256):
        raise ValueError("original_door_source_sha256_required")
    if (type(schedule_page_1_based) is not int
            or type(plan_page_1_based) is not int
            or schedule_page_1_based <= 0 or plan_page_1_based <= 0
            or schedule_page_1_based == plan_page_1_based):
        raise ValueError("distinct_original_schedule_and_plan_pages_required")
    if (type(requested_door_code) is not str
            or not re.fullmatch(r"D[1-9][0-9]{0,3}", requested_door_code)
            or type(schedule_native_block) is not int
            or schedule_native_block < 0):
        raise ValueError("original_door_code_schedule_selector_invalid")
    with fitz.open(stream=original_pdf_bytes,filetype="pdf") as pdf:
        if max(schedule_page_1_based,plan_page_1_based)>len(pdf):
            raise ValueError("original_source_page_out_of_range")
        schedule=pdf[schedule_page_1_based-1].get_text("words",sort=False)
        plan=pdf[plan_page_1_based-1].get_text("words",sort=False)
    if len(schedule)>100000 or len(plan)>100000:
        raise ValueError("bounded_native_source_word_universe_required")
    def receipt(word,page):
        return {
            "original_native_word_address":(page,int(word[5]),int(word[6]),int(word[7])),
            "original_word_text_untrusted":str(word[4]),
            "original_word_bbox_pdf_pts":tuple(float(v) for v in word[:4]),
            "source_text_glyph_and_clip_authenticated":False,
        }
    for words,page in ((schedule,schedule_page_1_based),(plan,plan_page_1_based)):
        native_ids=[(page,int(w[5]),int(w[6]),int(w[7])) for w in words]
        if len(set(native_ids))!=len(native_ids):
            raise ValueError("duplicate_original_door_source_word_address")
    row=sorted((w for w in schedule if int(w[5])==schedule_native_block),
               key=lambda w:(int(w[6]),int(w[7])))
    code_words=[w for w in row if str(w[4]).strip()==requested_door_code]
    if (not row or str(row[0][4]).strip()!=requested_door_code
            or len(code_words)!=1 or int(row[0][6])!=0
            or int(row[0][7])!=0):
        raise ValueError("original_door_schedule_native_code_row_unproven")
    all_schedule=tuple(receipt(w,schedule_page_1_based)
                       for w in schedule if str(w[4]).strip()==requested_door_code)
    all_plan=tuple(receipt(w,plan_page_1_based)
                   for w in plan if str(w[4]).strip()==requested_door_code)
    if not all_plan:
        return {
            "status":"original_door_plan_source_mark_unavailable",
            "original_source_sha256":expected_sha256,
            "new_firm_quantities":0,
        }
    lines={}
    for word in row:
        lines.setdefault(int(word[6]),[]).append(str(word[4]))
    return {
        "status":"native_original_door_schedule_and_plan_words_only",
        "original_source_sha256":expected_sha256,
        "source_schedule_page_1_based":schedule_page_1_based,
        "source_plan_page_1_based":plan_page_1_based,
        "selected_door_code_untrusted":requested_door_code,
        "selected_native_schedule_block":schedule_native_block,
        "selected_schedule_row_original_words":tuple(
            receipt(w,schedule_page_1_based) for w in row
        ),
        "original_schedule_row_lines":tuple(
            tuple(lines[k]) for k in sorted(lines)
        ),
        "all_original_schedule_same_door_code_words":all_schedule,
        "all_original_plan_same_door_code_words":all_plan,
        "door_schedule_semantic_issuer_authenticated":False,
        "plan_doorway_physical_owner_authenticated":False,
        "doorway_gap_metric_width_proven":False,
        "new_firm_quantities":0,
    }
