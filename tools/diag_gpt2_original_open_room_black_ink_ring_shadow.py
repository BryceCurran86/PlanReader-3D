"""Bounded native black-wall ink ring with a real uncovered door interruption.

Original PDF strokes are geometry candidates only. A source black enclosure
is not a producer-issued structural room, a finished internal wall face, an
authenticated door threshold, or a construction/finish area.
"""
from __future__ import annotations

import hashlib
import math
import re

import fitz

from tools.diag_original_room_four_edge_source_ink_shadow import _line


def _merge_source_ink_intervals(spans):
    merged=[]
    for lo,hi in sorted(spans):
        if hi<=lo:
            raise ValueError("degenerate_original_ink_interval")
        if merged and lo <= merged[-1][1] + 0.001:
            merged[-1]=(merged[-1][0],max(merged[-1][1],hi))
        else:
            merged.append((lo,hi))
    return tuple(merged)


def audit_original_room_wall_ink_with_single_door_gap(
    pdf_bytes:bytes, *, expected_sha256:str, page_1_based:int,
    candidate_source_room_bbox_pdf_pts:tuple[float,float,float,float],
    original_side_source_path_ids:dict[str,tuple[str,...]],
    max_native_paths:int=120000,
) -> dict:
    base={
        "status":"original_black_ink_room_ring_source_abstained",
        "first_unclosed_gate":"unverified_original_wall_source_sides",
        "room_structural_wall_role_authenticated":False,
        "source_finished_wall_face_geometry_authenticated":False,
        "source_doorway_is_structural_wall":False,
        "source_doorway_finish_threshold_authenticated":False,
        "new_firm_quantities":0,
    }
    if (type(pdf_bytes) is not bytes or type(expected_sha256) is not str
            or not re.fullmatch(r"[0-9a-f]{64}",expected_sha256)
            or hashlib.sha256(pdf_bytes).hexdigest()!=expected_sha256):
        raise ValueError("immutable_original_room_source_sha256_required")
    if type(page_1_based) is not int or page_1_based<1:
        raise ValueError("original_room_source_page_required")
    if (type(candidate_source_room_bbox_pdf_pts) not in (tuple,list)
            or len(candidate_source_room_bbox_pdf_pts)!=4
            or any(type(v) not in (int,float) or not math.isfinite(v)
                   for v in candidate_source_room_bbox_pdf_pts)):
        raise ValueError("source_room_candidate_bbox_invalid")
    x0,y0,x1,y1=map(float,candidate_source_room_bbox_pdf_pts)
    if x1<=x0 or y1<=y0:
        raise ValueError("source_room_candidate_bbox_invalid")
    roles=("left","right","bottom","top")
    if type(original_side_source_path_ids) is not dict or set(
            original_side_source_path_ids)!=set(roles):
        raise ValueError("four_explicit_source_wall_side_universes_required")
    seen=set()
    for role in roles:
        ids=original_side_source_path_ids[role]
        if (type(ids) not in (tuple,list) or not ids or len(ids)>128
                or any(type(v) is not str or not v or v!=v.strip() for v in ids)):
            raise ValueError("bounded_original_wall_role_source_ids_required")
        for native in ids:
            if native in seen:
                raise ValueError("original_wall_source_id_reused_across_sides")
            seen.add(native)
    if type(max_native_paths) is not int or max_native_paths<=0:
        raise ValueError("bounded_original_native_paths_required")
    with fitz.open(stream=pdf_bytes,filetype="pdf") as doc:
        if page_1_based>len(doc):
            raise ValueError("original_room_source_page_out_of_range")
        drawings=doc[page_1_based-1].get_drawings()
    if len(drawings)>max_native_paths:
        raise ValueError("original_native_paths_safety_cap")
    sides={}
    for role in roles:
        fixed=x0 if role=="left" else x1 if role=="right" else (
            y1 if role=="bottom" else y0
        )
        start,end=(y0,y1) if role in ("left","right") else (x0,x1)
        segments=[]
        for native in original_side_source_path_ids[role]:
            row=_line(drawings,native)
            if row["source_color"]!=(0.,0.,0.):
                return {**base,"first_unclosed_gate":"original_nonblack_wall_ink_source_conflict"}
            (ax,ay),(bx,by)=row["ends"]
            if role in ("left","right"):
                if ax!=bx or ax!=round(fixed,3):
                    return {**base,"first_unclosed_gate":"original_wall_side_axis_conflict"}
                lo,hi=sorted((ay,by))
            else:
                if ay!=by or ay!=round(fixed,3):
                    return {**base,"first_unclosed_gate":"original_wall_side_axis_conflict"}
                lo,hi=sorted((ax,bx))
            if lo < start-0.001 or hi > end+0.001:
                return {**base,"first_unclosed_gate":"original_wall_side_outside_source_bounds"}
            segments.append((lo,hi))
        merged=_merge_source_ink_intervals(segments)
        sides[role]={
            "original_native_source_path_ids":tuple(original_side_source_path_ids[role]),
            "original_source_ink_intervals_pdf_pts":merged,
            "structural_wall_role_authenticated":False,
        }
    for role in ("left","right","bottom"):
        whole=(y0,y1) if role in ("left","right") else (x0,x1)
        if sides[role]["original_source_ink_intervals_pdf_pts"] != (
            tuple(round(v,3) for v in whole),
        ):
            return {**base,"first_unclosed_gate":
                "original_black_source_perimeter_side_unclosed","source_side_evidence":sides}
    top=sides["top"]["original_source_ink_intervals_pdf_pts"]
    if (len(top)!=2 or top[0][0]!=round(x0,3)
            or top[1][1]!=round(x1,3) or top[0][1]>=top[1][0]):
        return {**base,
            "first_unclosed_gate":"original_top_door_ink_gap_not_unique",
            "source_side_evidence":sides}
    gap=((top[0][1],round(y0,3)),(top[1][0],round(y0,3)))
    # The selected *wall candidate* strokes do not cover this interval.
    # Independently inspect every other original native black stroke here:
    # door-leaf, threshold, and drafting strokes may still cross the gap.
    # None is silently assumed structural or discarded as irrelevant.
    chosen={source_id for ids in original_side_source_path_ids.values()
            for source_id in ids}
    ink_rivals=[]
    for native_path_id, path in enumerate(drawings):
        if path.get("color") != (0.,0.,0.):
            continue
        width=path.get("width")
        if type(width) not in (float,int) or not math.isfinite(width) or width<=0:
            continue
        for native_item_id, original_item in enumerate(path.get("items",())):
            native_id=f"d{native_path_id}i{native_item_id}"
            if native_id in chosen or len(original_item)<3 or original_item[0]!="l":
                continue
            a,b=original_item[1:3]
            if (not all(math.isfinite(float(v)) for v in (a.x,a.y,b.x,b.y))
                    or abs(float(a.y)-float(b.y))>0.001
                    or abs(float(a.y)-y0)>0.001):
                continue
            left,right=sorted((float(a.x),float(b.x)))
            lo,hi=max(left,gap[0][0]),min(right,gap[1][0])
            if hi<=lo:
                continue
            ink_rivals.append({
                "original_native_path_item_id":native_id,
                "original_ink_intersection_in_selected_gap_pdf_pts":(
                    round(lo,3),round(hi,3)
                ),
                "original_black_stroke_width_pdf_pts":float(width),
                "physical_wall_role_authenticated":False,
                "source_door_graphic_role_authenticated":False,
            })
            if len(ink_rivals)>4096:
                raise ValueError("original_unclassified_door_gap_ink_safety_cap")
    return {
        **base,
        "status":"original_black_ink_room_ring_with_virtual_door_gap_candidate",
        "first_unclosed_gate":"source_physical_wall_roles_and_door_threshold_unproven",
        "original_source_sha256":expected_sha256,
        "original_source_page_1_based":page_1_based,
        "original_source_candidate_ring_pdf_pts":(
            (x0,y0),(x1,y0),(x1,y1),(x0,y1)
        ),
        "source_side_evidence":sides,
        "original_source_top_ink_door_gap_pdf_pts":gap,
        "source_selected_wall_candidates_gap_pdf_pts":gap,
        "all_original_unclassified_black_ink_in_selected_wall_gap":tuple(ink_rivals),
        "source_gap_absent_of_all_original_ink_proven":not bool(ink_rivals),
        "source_selected_wall_gap_door_semantics_authenticated":False,
        "original_source_candidate_area_pdf_pts2":(x1-x0)*(y1-y0),
        "original_room_source_candidate_only":True,
        "source_doorway_is_structural_wall":False,
        "source_doorway_finish_threshold_authenticated":False,
        "room_structural_wall_role_authenticated":False,
        "source_finished_wall_face_geometry_authenticated":False,
        "new_firm_quantities":0,
    }
