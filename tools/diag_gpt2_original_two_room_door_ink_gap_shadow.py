"""Original source wall-ink doorway gap between two named printed zones.

A gap in black native wall-candidate strokes plus a door mark is NOT an
authenticated structural doorway or a measured finished-face threshold.
Do not convert source native PDF points to construction metres or m2 here.
"""
from __future__ import annotations

import hashlib
import math
import re

import fitz

from tools.diag_original_room_four_edge_source_ink_shadow import _line
from tools.diag_gpt2_original_door_schedule_native_words_shadow import (
    census_original_door_schedule_native_source,
)


def audit_original_two_room_source_wall_door_gap(
    original_pdf_bytes: bytes, *, expected_sha256: str,
    original_plan_page_1_based: int, original_door_schedule_page_1_based: int,
    room_word_receipts: tuple[tuple[str, tuple[int,int,int]],...],
    original_left_wall_ink_id: str, original_right_wall_ink_id: str,
    door_code: str, original_schedule_native_block: int,
    original_doorway_wall_axis_y_pdf_pts: float,
    max_original_native_paths: int=120000,
) -> dict:
    if (type(original_pdf_bytes) is not bytes
            or type(expected_sha256) is not str
            or not re.fullmatch(r"[0-9a-f]{64}",expected_sha256)
            or hashlib.sha256(original_pdf_bytes).hexdigest()!=expected_sha256):
        raise ValueError("original_room_doorway_sha256_conflict")
    if (type(original_plan_page_1_based) is not int
            or type(original_door_schedule_page_1_based) is not int
            or min(original_plan_page_1_based,
                   original_door_schedule_page_1_based)<=0
            or original_plan_page_1_based==original_door_schedule_page_1_based):
        raise ValueError("source_plan_schedule_page_conflict")
    if (type(room_word_receipts) not in (tuple,list)
            or len(room_word_receipts)!=2
            or any(type(row) not in (tuple,list) or len(row)!=2
                   or type(row[0]) is not str or not row[0] or row[0]!=row[0].strip()
                   or type(row[1]) not in (tuple,list) or len(row[1])!=3
                   or any(type(v) is not int or v<0 for v in row[1])
                   for row in room_word_receipts)):
        raise ValueError("two_distinct_original_room_word_receipts_required")
    if (len(set(row[0] for row in room_word_receipts))!=2
            or len(set(tuple(row[1]) for row in room_word_receipts))!=2
            or type(original_left_wall_ink_id) is not str
            or type(original_right_wall_ink_id) is not str
            or original_left_wall_ink_id==original_right_wall_ink_id):
        raise ValueError("distinct_original_room_or_wall_sources_required")
    if (type(original_doorway_wall_axis_y_pdf_pts) not in (int,float)
            or not math.isfinite(original_doorway_wall_axis_y_pdf_pts)
            or type(max_original_native_paths) is not int
            or max_original_native_paths<=0):
        raise ValueError("bounded_original_door_wall_axis_required")
    with fitz.open(stream=original_pdf_bytes,filetype="pdf") as document:
        if max(original_plan_page_1_based,
               original_door_schedule_page_1_based)>len(document):
            raise ValueError("original_source_page_unavailable")
        page=document[original_plan_page_1_based-1]
        drawings=page.get_drawings()
        words=page.get_text("words",sort=False)
    if len(drawings)>max_original_native_paths or len(words)>100000:
        raise ValueError("bounded_original_source_universe_exceeded")
    side_ink=tuple(_line(drawings,value)
                   for value in (original_left_wall_ink_id,
                                 original_right_wall_ink_id))
    intervals=[]
    axis=float(original_doorway_wall_axis_y_pdf_pts)
    for side in side_ink:
        (x0,y0),(x1,y1)=side["ends"]
        if (side["source_color"]!=(0.,0.,0.)
                or side["stroke_opacity"]!=1.
                or y0!=y1 or abs(y0-axis)>.001 or x0>=x1):
            raise ValueError("source_original_opaque_wall_candidate_invalid")
        intervals.append((x0,x1))
    left,right=intervals
    if left[1]>=right[0]:
        raise ValueError("source_original_wall_gap_not_positive")
    # Preserve the wall-centreline gap, do not fabricate a door width from it.
    gap=(left[1],right[0])
    word_index={}
    for w in words:
        if len(w)<8:
            raise ValueError("original_source_word_malformed")
        key=tuple(int(v) for v in w[5:8])
        if key in word_index:
            raise ValueError("duplicate_original_source_word_address")
        word_index[key]=w
    rooms=[]
    for name,word_id in room_word_receipts:
        w=word_index.get(tuple(word_id))
        if w is None or str(w[4]).strip()!=name:
            raise ValueError("independently_owned_room_word_missing")
        bounds=tuple(float(v) for v in w[:4])
        if not all(math.isfinite(v) for v in bounds):
            raise ValueError("original_room_word_bounds_nonfinite")
        if bounds[1]<axis<bounds[3]:
            raise ValueError("original_room_word_crosses_wall_axis")
        if bounds[3]<=axis:
            side="before_wall_axis"
        elif bounds[1]>=axis:
            side="after_wall_axis"
        else:
            raise ValueError("original_room_word_wall_side_unproven")
        rooms.append({
            "original_room_name_untrusted":name,
            "original_room_word_address":(
                original_plan_page_1_based,*tuple(word_id)),
            "original_room_word_bbox_pdf_pts":bounds,
            "original_source_side_of_unproven_wall":side,
            "source_structural_room_owner_authenticated":False,
        })
    if rooms[0]["original_source_side_of_unproven_wall"]==(
            rooms[1]["original_source_side_of_unproven_wall"]):
        raise ValueError("two_original_rooms_not_across_wall_source")
    schedule=census_original_door_schedule_native_source(
        original_pdf_bytes,expected_sha256=expected_sha256,
        schedule_page_1_based=original_door_schedule_page_1_based,
        plan_page_1_based=original_plan_page_1_based,
        requested_door_code=door_code,
        schedule_native_block=original_schedule_native_block,
    )
    if schedule["status"]!="native_original_door_schedule_and_plan_words_only":
        raise ValueError("original_schedule_or_plan_door_source_missing")
    lines=schedule["original_schedule_row_lines"]
    if (len(lines)<3
            or lines[1] not in {tuple(name.split(" ")) for name,_ in room_word_receipts}
            or lines[2] not in (("SINGLE","SWING"),("DOUBLE","SWING"),
                                ("SLIDING","DOOR"),("AS","PER","MANUFACTURER"))):
        raise ValueError("source_schedule_door_room_semantics_conflict")
    door_marks=[]
    competitors=[]
    for item in schedule["all_original_plan_same_door_code_words"]:
        bounds=item["original_word_bbox_pdf_pts"]
        x0,y0,x1,y1=map(float,bounds)
        if x0>=gap[0] and x1<=gap[1] and y0<=axis<=y1:
            door_marks.append(item)
        else:
            competitors.append(item)
    if len(door_marks)!=1:
        raise ValueError("original_wall_gap_door_mark_missing_or_ambiguous")
    return {
        "status":"two_original_room_labels_and_door_wall_gap_source_candidate",
        "original_source_sha256":expected_sha256,
        "original_plan_page_1_based":original_plan_page_1_based,
        "original_source_room_label_candidates":tuple(rooms),
        "source_original_wall_candidate_ink_ids":(
            original_left_wall_ink_id, original_right_wall_ink_id),
        "source_original_wall_ink_endpoints_pdf_pts":tuple(
            tuple(ink["ends"]) for ink in side_ink),
        "original_source_gap_pdf_pts":(
            (gap[0],axis),(gap[1],axis)),
        "source_door_mark_on_original_ink_gap":door_marks[0],
        "source_other_same_code_door_word_competitors":tuple(competitors),
        "source_independent_door_schedule":schedule,
        "source_wall_gap_all_drafting_and_door_ink_candidates_exhausted":False,
        "original_structural_wall_or_door_host_authenticated":False,
        "original_physical_room_cross_view_identity_authenticated":False,
        "original_finished_wall_face_or_threshold_authenticated":False,
        "original_source_metric_scale_authenticated":False,
        "new_firm_quantities":0,
    }
