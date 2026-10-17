"""Exact original-source wall-ink correspondence across two pages.

Read-only, caller-supplied candidate path/item identities. A matched source
stroke is not a structural wall, closing doorway, finished face or an area.
All original candidates and gaps remain owned by their original page.
"""
from __future__ import annotations
import hashlib
import math
import re
import fitz

_ID=re.compile(r"^d([0-9]+)i([0-9]+)$")
_ROLES=("left","right","bottom","top_partial")


def _line(drawings, identity):
    match=_ID.fullmatch(identity) if type(identity) is str else None
    if match is None:
        raise ValueError("original_native_path_item_id_required")
    pi,ii=map(int,match.groups())
    if pi>=len(drawings) or ii>=len(drawings[pi].get("items",())):
        raise ValueError("original_native_path_item_missing")
    entry=drawings[pi]
    item=entry["items"][ii]
    if len(item)<3 or item[0]!="l":
        raise ValueError("actual_original_straight_line_required")
    x,y,X,Y=(round(float(z),3) for point in item[1:3] for z in point)
    if not all(math.isfinite(q) for q in (x,y,X,Y)):
        raise ValueError("finite_original_source_line_required")
    ends=sorted(((x,y),(X,Y)))
    color=entry.get("color")
    width=entry.get("width")
    if color is None or width is None:
        raise ValueError("native_source_ink_style_required")
    return {
        "identity":identity,"ends":ends,
        "stroke_width":round(float(width),3),
        "source_color":tuple(round(float(v),5) for v in color),
    }


def audit_source_enclosure_correspondence(
    original_pdf_bytes:bytes, *, expected_sha256:str,
    floor_page_1_based:int, finish_page_1_based:int,
    original_side_pairs:dict[str,tuple[str,str]],
    expected_translation_pdf_pts:tuple[float,float],
    max_native_paths:int=120000,
)->dict:
    if type(original_pdf_bytes) is not bytes or hashlib.sha256(original_pdf_bytes).hexdigest()!=expected_sha256:
        raise ValueError("original_source_sha_mismatch")
    if (type(original_side_pairs) is not dict
            or set(original_side_pairs)!=set(_ROLES)
            or any(type(v) is not tuple or len(v)!=2
                   for v in original_side_pairs.values())):
        raise ValueError("four_explicit_original_edge_pair_candidates_required")
    if (type(expected_translation_pdf_pts) is not tuple or len(expected_translation_pdf_pts)!=2
            or any(not isinstance(n,(int,float)) or not math.isfinite(n)
                   for n in expected_translation_pdf_pts)):
        raise ValueError("finite_source_translation_candidate_required")
    if len({a for v in original_side_pairs.values() for a in v})!=8:
        raise ValueError("distinct_source_path_item_owners_required")
    with fitz.open(stream=original_pdf_bytes,filetype="pdf") as pdf:
        if (type(floor_page_1_based) is not int or type(finish_page_1_based) is not int
                or floor_page_1_based==finish_page_1_based
                or not 1<=floor_page_1_based<=len(pdf)
                or not 1<=finish_page_1_based<=len(pdf)):
            raise ValueError("distinct_original_source_pages_required")
        fa=pdf[floor_page_1_based-1].get_drawings()
        fb=pdf[finish_page_1_based-1].get_drawings()
        if len(fa)>max_native_paths or len(fb)>max_native_paths:
            return {"status":"source_path_cap_exceeded","room_authority_granted":False}
        pairs={}
        for side in _ROLES:
            a_id,b_id=original_side_pairs[side]
            a,b=_line(fa,a_id),_line(fb,b_id)
            dx,dy=expected_translation_pdf_pts
            translated=sorted((round(x+dx,3),round(y+dy,3)) for x,y in a["ends"])
            if (translated!=b["ends"] or a["source_color"]!=b["source_color"]
                    or a["stroke_width"]!=b["stroke_width"]):
                raise ValueError("source_side_ink_or_translation_conflict")
            pairs[side]={"floor_source":a,"finish_source":b,
                          "matched_original_ink_only":True,
                          "physical_wall_role_proven":False}
        left,right,bottom,top=(pairs[x]["floor_source"]["ends"] for x in _ROLES)
        if (left[0][0]!=left[1][0] or right[0][0]!=right[1][0]
                or bottom[0][1]!=bottom[1][1] or top[0][1]!=top[1][1]
                or left[0][0]>=right[0][0] or top[0][1]>=bottom[0][1]):
            raise ValueError("source_enclosure_side_orientation_conflict")
        x_left=left[0][0];x_right=right[0][0]
        y_top=top[0][1];y_bottom=bottom[0][1]
        if (left!=[(x_left,y_top),(x_left,y_bottom)]
                or right!=[(x_right,y_top),(x_right,y_bottom)]
                or bottom!=[(x_left,y_bottom),(x_right,y_bottom)]
                or top[1]!=(x_right,y_top)
                or not x_left<top[0][0]<x_right):
            raise ValueError("native_original_wall_side_or_doorway_gap_conflict")
        return {
            "status":"original_four_edge_ink_correspondence_with_unclosed_doorway",
            "original_floor_page_id":floor_page_1_based,
            "original_finish_page_id":finish_page_1_based,
            "source_translation_candidate_pdf_pts":list(expected_translation_pdf_pts),
            "original_witnesses":pairs,
            "original_top_gap_pdf_pts":[[x_left,y_top],[top[0][0],y_top]],
            "original_top_gap_is_a_door_without_jamb_proof":False,
            "canonical_cross_sheet_physical_room_equality_granted":False,
            "physical_wall_roles_verified":False,
            "source_finished_face_and_area_verified":False,
            "new_firm_quantities":0,
        }
