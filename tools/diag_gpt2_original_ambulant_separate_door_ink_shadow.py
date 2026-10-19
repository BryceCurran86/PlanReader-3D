"""One immutable original source, two independently scheduled adjacent doors.

This is SOURCE evidence about separate original printed cubicle candidates.
Neither a word, scheduled door size, nor a corridor ink segment establishes
a closed W4 structural room, internal finished face, or measured area.
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


def audit_original_adjacent_room_door_entrances(
    original_pdf_bytes: bytes, *, expected_sha256: str,
    plan_page_1_based: int, schedule_page_1_based: int,
    original_room_door_word_pairs: tuple[tuple[str, tuple[int,int,int], str, int],...],
    original_corridor_separating_ink_path_id: str,
    source_corridor_axis_y_pdf_pts: float,
    max_original_native_paths: int = 120000,
) -> dict:
    """Require distinct native room/door ancestry on opposite sides of ink."""
    if (type(original_pdf_bytes) is not bytes
            or type(expected_sha256) is not str
            or not re.fullmatch(r"[0-9a-f]{64}",expected_sha256)
            or hashlib.sha256(original_pdf_bytes).hexdigest()!=expected_sha256):
        raise ValueError("immutable_original_room_source_sha256_required")
    if (type(plan_page_1_based) is not int
            or type(schedule_page_1_based) is not int
            or min(plan_page_1_based,schedule_page_1_based)<=0
            or plan_page_1_based==schedule_page_1_based):
        raise ValueError("distinct_original_plan_schedule_pages_required")
    if (type(original_room_door_word_pairs) not in (tuple,list)
            or len(original_room_door_word_pairs)!=2):
        raise ValueError("two_distinct_original_entrances_required")
    if (type(source_corridor_axis_y_pdf_pts) not in (int,float)
            or not math.isfinite(source_corridor_axis_y_pdf_pts)
            or type(max_original_native_paths) is not int
            or max_original_native_paths <= 0):
        raise ValueError("bounded_original_corridor_source_required")
    with fitz.open(stream=original_pdf_bytes,filetype="pdf") as document:
        if max(plan_page_1_based,schedule_page_1_based)>len(document):
            raise ValueError("original_source_page_out_of_bounds")
        page=document[plan_page_1_based-1]
        native_words=page.get_text("words",sort=False)
        drawings=page.get_drawings()
    if len(native_words)>100000 or len(drawings)>max_original_native_paths:
        raise ValueError("original_plan_source_inventory_safety_cap")
    native_index={}
    for word in native_words:
        if len(word)<8:
            raise ValueError("malformed_original_native_room_word")
        identity=tuple(int(v) for v in word[5:8])
        if identity in native_index:
            raise ValueError("original_source_native_word_address_alias")
        native_index[identity]=word
    side=_line(drawings,original_corridor_separating_ink_path_id)
    ends=side["ends"]
    if (side["source_color"]!=(0.,0.,0.)
            or side["stroke_opacity"]!=1.
            or ends[0][1]!=ends[1][1]
            or abs(ends[0][1]-source_corridor_axis_y_pdf_pts)>.001
            or ends[0][0]>=ends[1][0]):
        raise ValueError("authentic_black_horizontal_corridor_ink_missing")
    midpoint=(ends[0][0]+ends[1][0])/2
    occupied_room_ids=set()
    occupied_door_codes=set()
    rooms=[]
    for row in original_room_door_word_pairs:
        if (type(row) not in (tuple,list) or len(row)!=4
                or type(row[0]) is not str or not row[0].strip()
                or row[0]!=row[0].strip()
                or type(row[1]) not in (tuple,list) or len(row[1])!=3
                or any(type(v) is not int or v<0 for v in row[1])
                or type(row[2]) is not str
                or type(row[3]) is not int):
            raise ValueError("source_room_door_pair_receipt_invalid")
        name,word_address,code,schedule_block=row
        word_address=tuple(word_address)
        if word_address in occupied_room_ids or code in occupied_door_codes:
            raise ValueError("original_ambulant_room_door_source_alias")
        occupied_room_ids.add(word_address)
        occupied_door_codes.add(code)
        native=native_index.get(word_address)
        if native is None or str(native[4]).strip()!=name:
            raise ValueError("original_room_label_native_source_missing")
        schedule=census_original_door_schedule_native_source(
            original_pdf_bytes,expected_sha256=expected_sha256,
            schedule_page_1_based=schedule_page_1_based,
            plan_page_1_based=plan_page_1_based,
            requested_door_code=code,schedule_native_block=schedule_block,
        )
        if schedule["status"]!="native_original_door_schedule_and_plan_words_only":
            raise ValueError("original_door_schedule_or_plan_native_word_missing")
        # Match original room word to ORIGINAL room field from the independently
        # printed schedule, not to a nearby drawing text or presumed door host.
        schedule_words=schedule["original_schedule_row_lines"]
        if (len(schedule_words)<3 or schedule_words[1]!=(name,)
                or schedule_words[2] not in (
                    ("SINGLE","SWING"),("DOUBLE","SWING"),
                    ("SLIDING","DOOR"),("AS","PER","MANUFACTURER"))):
            raise ValueError("original_scheduled_room_or_door_type_conflict")
        room_bbox=tuple(float(v) for v in native[:4])
        room_cx=(room_bbox[0]+room_bbox[2])/2
        if room_bbox[0]<=midpoint<=room_bbox[2]:
            raise ValueError("original_room_label_crosses_separating_ink")
        belonging=[]
        competitors=[]
        for candidate in schedule["all_original_plan_same_door_code_words"]:
            bbox=candidate["original_word_bbox_pdf_pts"]
            x0,y0,x1,y1=bbox
            candidate_cx=(x0+x1)/2
            side_consistent=(room_cx<midpoint)==(candidate_cx<midpoint)
            crosses_axis=y0<=source_corridor_axis_y_pdf_pts<=y1
            # Keep every mark competitor. The one on same side and on the
            # corridor ink axis is only a SOURCE doorway text candidate.
            (belonging if side_consistent and crosses_axis else competitors).append(
                candidate)
        if len(belonging)!=1:
            raise ValueError("original_cubicle_door_word_on_corridor_not_unique")
        rooms.append({
            "original_room_name_untrusted":name,
            "original_room_word_address":(
                plan_page_1_based,*word_address),
            "original_room_word_bbox_pdf_pts":room_bbox,
            "source_original_door_code_untrusted":code,
            "original_plan_door_word_on_corridor":belonging[0],
            "all_competing_same_code_source_plan_words":tuple(competitors),
            "original_schedule_source":schedule,
            "structural_cubicle_room_or_door_host_authenticated":False,
        })
    if (rooms[0]["original_room_word_bbox_pdf_pts"][0] < midpoint)==(
            rooms[1]["original_room_word_bbox_pdf_pts"][0] < midpoint):
        raise ValueError("independent_original_room_labels_not_opposite_source_sides")
    return {
        "status":"two_distinct_original_cubicle_door_source_candidates_only",
        "original_source_sha256":expected_sha256,
        "source_plan_page_1_based":plan_page_1_based,
        "original_corridor_separating_ink_path_id":
            original_corridor_separating_ink_path_id,
        "original_corridor_ink_endpoints_pdf_pts":tuple(ends),
        "all_original_distinct_room_door_candidates":tuple(rooms),
        "original_complete_structural_cubicle_wall_ring_authenticated":False,
        "original_finished_face_or_door_threshold_authenticated":False,
        "source_canonical_room_publisher_authority_granted":False,
        "new_firm_quantities":0,
    }
