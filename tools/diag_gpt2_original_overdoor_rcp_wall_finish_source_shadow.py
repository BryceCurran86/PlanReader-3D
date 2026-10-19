"""Cross-sheet original p7 doorway gap and p9 overhead ceiling-plan ink.

A fully inked RCP wall across a floor-plan door gap is a source candidate
for overhead wall continuity. It does NOT fill the floor doorway, publish
ceiling area or establish an original RCP source-owned viewport.
"""
from __future__ import annotations

import hashlib
import math
import re

import fitz

from tools.diag_original_room_four_edge_source_ink_shadow import _line
from tools.diag_gpt2_original_two_room_door_ink_gap_shadow import (
    audit_original_two_room_source_wall_door_gap,
)


def audit_original_floor_door_gap_vs_rcp_overdoor_ink(
    original_pdf_bytes:bytes, *, expected_sha256:str,
    floor_page_1_based:int, rcp_page_1_based:int,
    door_schedule_page_1_based:int,
    floor_original_room_words:tuple[tuple[str,tuple[int,int,int]],...],
    floor_left_ink_path_id:str, floor_right_ink_path_id:str,
    floor_original_door_code:str, original_door_schedule_block:int,
    source_doorway_wall_axis_y_pdf_pts:float,
    original_rcp_overdoor_ink_path_id:str,
    rcp_room_finish_word_receipts:tuple[
        tuple[str,tuple[int,int,int],tuple[int,int,int]],...],
    source_ceiling_mark_code:str="IPF1",
) -> dict:
    # Do not accept preconstructed 'proven' doorway/room receipts.
    # Recompute p7 original source from the same SHA bytes and schedule.
    floor=audit_original_two_room_source_wall_door_gap(
        original_pdf_bytes,expected_sha256=expected_sha256,
        original_plan_page_1_based=floor_page_1_based,
        original_door_schedule_page_1_based=door_schedule_page_1_based,
        room_word_receipts=floor_original_room_words,
        original_left_wall_ink_id=floor_left_ink_path_id,
        original_right_wall_ink_id=floor_right_ink_path_id,
        door_code=floor_original_door_code,
        original_schedule_native_block=original_door_schedule_block,
        original_doorway_wall_axis_y_pdf_pts=source_doorway_wall_axis_y_pdf_pts,
    )
    if (type(rcp_page_1_based) is not int or rcp_page_1_based<=0
            or rcp_page_1_based in (floor_page_1_based,door_schedule_page_1_based)
            or type(source_ceiling_mark_code) is not str
            or not re.fullmatch(r"[A-Z][A-Z0-9]{1,11}",source_ceiling_mark_code)
            or type(rcp_room_finish_word_receipts) not in (tuple,list)
            or len(rcp_room_finish_word_receipts)!=2):
        raise ValueError("source_rcp_page_material_or_room_receipts_invalid")
    with fitz.open(stream=original_pdf_bytes,filetype="pdf") as doc:
        if rcp_page_1_based>len(doc):
            raise ValueError("original_rcp_source_page_unavailable")
        page=doc[rcp_page_1_based-1]
        native=page.get_text("words",sort=False)
        strokes=page.get_drawings()
    if len(strokes)>120000 or len(native)>100000:
        raise ValueError("original_rcp_source_inventory_over_cap")
    overhead=_line(strokes,original_rcp_overdoor_ink_path_id)
    (a,b),(c,d)=overhead["ends"]
    (lo,wall_y),(hi,_) = floor["original_source_gap_pdf_pts"]
    if (overhead["source_color"]!=(0.,0.,0.)
            or overhead["stroke_opacity"]!=1.
            or b!=d or b!=round(wall_y,3)
            or a>lo or c<hi or a>=c):
        raise ValueError("original_rcp_overdoor_source_ink_does_not_span_door_gap")
    source_idx={}
    for w in native:
        if len(w)<8:
            raise ValueError("original_rcp_source_word_invalid")
        key=tuple(int(v) for v in w[5:8])
        if key in source_idx:
            raise ValueError("original_rcp_source_word_address_collision")
        source_idx[key]=w
    words_all=tuple((rcp_page_1_based,int(w[5]),int(w[6]),int(w[7]))
                    for w in native if str(w[4]).strip()==source_ceiling_mark_code)
    receipt_ids=[]
    pairs=[]
    floor_names={name for name,_ in floor_original_room_words}
    for row in rcp_room_finish_word_receipts:
        if (type(row) not in (tuple,list) or len(row)!=3
                or type(row[0]) is not str or row[0] not in floor_names
                or type(row[1]) not in (tuple,list) or len(row[1])!=3
                or type(row[2]) not in (tuple,list) or len(row[2])!=3
                or any(type(v) is not int or v<0
                       for q in row[1:3] for v in q)):
            raise ValueError("original_rcp_room_mark_word_receipt_invalid")
        room,room_id,mark_id=row
        room_id=tuple(room_id);mark_id=tuple(mark_id)
        receipt_ids.extend((room_id,mark_id))
        w_room=source_idx.get(room_id)
        w_mark=source_idx.get(mark_id)
        if (w_room is None or w_mark is None
                or str(w_room[4]).strip()!=room
                or str(w_mark[4]).strip()!=source_ceiling_mark_code):
            raise ValueError("source_rcp_room_or_ceiling_mark_missing")
        roomsides=[]
        for w in (w_room,w_mark):
            r=tuple(float(v) for v in w[:4])
            if any(not math.isfinite(v) for v in r):
                raise ValueError("original_rcp_word_geometry_nonfinite")
            if r[3]<wall_y:
                roomsides.append("before_ink")
            elif r[1]>wall_y:
                roomsides.append("after_ink")
            else:
                raise ValueError("source_rcp_room_or_finish_word_crosses_partition")
        if roomsides[0]!=roomsides[1]:
            raise ValueError("source_rcp_room_finish_marks_on_different_ink_sides")
        pairs.append({
            "original_rcp_printed_room":room,
            "original_rcp_room_word_address":(rcp_page_1_based,*room_id),
            "original_rcp_finish_word_address":(rcp_page_1_based,*mark_id),
            "source_unproven_ink_side":roomsides[0],
            "source_physical_ceiling_zone_or_room_authenticated":False,
        })
    if (len(set(receipt_ids))!=4
            or {x["original_rcp_printed_room"] for x in pairs}!=floor_names
            or pairs[0]["source_unproven_ink_side"]==
               pairs[1]["source_unproven_ink_side"]
            or any(row["original_rcp_finish_word_address"] not in words_all
                   for row in pairs)):
        raise ValueError("original_rcp_room_finish_cross_page_source_conflict")
    return {
        "status":"source_floor_door_gap_and_unbroken_rcp_wall_correspondence_candidate",
        "original_source_sha256":expected_sha256,
        "original_floor_doorway_source":floor,
        "original_rcp_page_1_based":rcp_page_1_based,
        "original_rcp_overdoor_ink_path_id":original_rcp_overdoor_ink_path_id,
        "original_rcp_overdoor_ink_endpoints_pdf_pts":tuple(overhead["ends"]),
        "original_rcp_room_mark_pairs":tuple(pairs),
        "all_original_rcp_same_ceiling_code_word_competitors":words_all,
        "source_original_floor_doorway_stays_open":True,
        "source_original_wall_above_door_physical_structure_verified":False,
        "source_rcp_viewport_and_cross_page_physical_room_authenticated":False,
        "source_rcp_material_occurrence_and_ceiling_metric_authority":False,
        "new_firm_quantities":0,
    }
