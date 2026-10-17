"""Source-only same-room evidence between original amenity inset and floor plan.

Unlike equal labels, native page numbers or similar rectangle aspect ratios,
the original source proof requires ALL of:
- exact same immutable source SHA;
- complete original p7 source edge graph (including real door interruption);
- re-read original source plan caption independently of nearby elevations;
- room and door printed words authenticated only as native lexical candidates;
- competing original printed detail face families retained, never discarded;
- both independently drawn axes compared with no assumed 1:25/1:50 scale.

This is NOT W4 physical identity or finish/metric quantity. It is a typed
first-failure handoff for GPT2 original room topology and GPT1 measurement.
"""
from __future__ import annotations
import hashlib
import math

import fitz

from tools.diag_gpt2_source_room_graph_shadow import audit_original_room_edge_graph


def _original_word(page, address):
    if (type(address) is not tuple or len(address)!=3
            or any(type(v) is not int or v<0 for v in address)):
        raise ValueError("source_native_word_address_required")
    matches=[w for w in page.get_text("words")
             if len(w)>=8 and tuple(w[5:8])==address]
    if len(matches)!=1:
        raise ValueError("original_native_word_address_missing_or_competing")
    return matches[0]


def _unique_original_plan_caption(page, *, source_room_literal: str):
    """Printed 'PROP. <room> PLAN' vs distinct source ELEVATION captions."""
    grouped={}
    for word in page.get_text("words"):
        if len(word)<8:
            continue
        grouped.setdefault(tuple(word[5:7]),[]).append(word)
    qualifying=[]
    elevations=[]
    for addr,words in grouped.items():
        ordered=tuple(w[4].strip().upper() for w in sorted(words,key=lambda w:w[7]))
        if ordered==("PROP.",source_room_literal.upper(),"PLAN"):
            qualifying.append((addr,words))
        if (len(ordered)>=3 and ordered[0]==source_room_literal.upper()
                and "ELEVATION" in ordered):
            elevations.append(addr)
    if len(qualifying)!=1:
        raise ValueError("original_local_plan_caption_missing_or_competing")
    return {
        "source_native_caption_line_address":list(qualifying[0][0]),
        "source_caption_literal_text":" ".join(
            w[4] for w in sorted(qualifying[0][1],key=lambda x:x[7])),
        "source_competing_local_elevation_caption_count":len(elevations),
        "source_detail_viewport_structural_owner_proven":False,
    }


def audit_original_detail_vs_main_source_room_candidate(
    original_pdf: bytes, *, source_sha256: str,
    original_floor_page: int,
    original_detail_page: int,
    floor_source_edge_ids: tuple[str,...],
    original_floor_room_word_address: tuple[int,int,int],
    original_detail_room_word_address: tuple[int,int,int],
    original_floor_door_word_address: tuple[int,int,int],
    original_detail_door_word_address: tuple[int,int,int],
    original_detail_figure_face_receipt: dict,
    source_room_literal: str,
    original_door_code_literal: str,
) -> dict:
    """Original same-room candidates: wall axes, mark ownership, view type."""
    if (type(original_pdf) is not bytes
            or hashlib.sha256(original_pdf).hexdigest()!=source_sha256):
        raise ValueError("original_same_room_source_sha_mismatch")
    if (type(source_room_literal) is not str or not source_room_literal
            or type(original_door_code_literal) is not str
            or not original_door_code_literal):
        raise ValueError("source_room_and_door_literals_required")
    face=original_detail_figure_face_receipt
    if (type(face) is not dict or
            face.get("status")!="original_figured_face_source_rivals_only"
            or face.get("original_source_sha256")!=source_sha256
            or face.get("original_detail_page_1_based")!=original_detail_page
            or not face.get("original_source_candidate_face_families")):
        raise ValueError("original_source_figured_face_rival_receipt_required")
    floor_graph=audit_original_room_edge_graph(
        original_pdf,source_sha256=source_sha256,
        page_1_based=original_floor_page,
        source_edge_ids=floor_source_edge_ids,
    )
    with fitz.open(stream=original_pdf,filetype="pdf") as pdf:
        if (type(original_detail_page) is not int or
                not 1<=original_detail_page<=len(pdf)):
            raise ValueError("original_detail_pdf_page_invalid")
        detail=pdf[original_detail_page-1]
        floor=pdf[original_floor_page-1]
        caption=_unique_original_plan_caption(
            detail,source_room_literal=source_room_literal)
        fw=_original_word(floor,original_floor_room_word_address)
        dw=_original_word(detail,original_detail_room_word_address)
        fd=_original_word(floor,original_floor_door_word_address)
        dd=_original_word(detail,original_detail_door_word_address)
        labels=(
            (fw,source_room_literal,"floor_room"),
            (dw,source_room_literal,"detail_room"),
            (fd,original_door_code_literal,"floor_door"),
            (dd,original_door_code_literal,"detail_door"),
        )
        for word,expected,_ in labels:
            if word[4]!=expected:
                raise ValueError("original_room_or_door_source_literal_mismatch")
        # All native words are still untrusted until the independent
        # source text/clip and physical line-owner producers authenticate.
        marks=tuple({
            "original_source_role":role,
            "original_source_page_1_based":(
                original_floor_page if role.startswith("floor")
                else original_detail_page),
            "original_native_word_address":list(word[5:8]),
            "original_raw_literal":word[4],
            "original_word_bbox_pdf_pts":[round(v,3) for v in word[:4]],
            "original_source_text_clip_and_glyph_integrity_proven":False,
        } for word,_,role in labels)
        original_rotations=(floor.rotation,detail.rotation)
    if (floor_graph["status"]!="original_source_branches_or_open_ends"
            or len(floor_graph["native_components"])!=1
            or floor_graph["interior_stroke_intersections_and_overlaps"]
            or floor_graph["native_candidate_ring_count"]!=0):
        return {
            "status":"original_detail_to_floor_source_shape_unresolved",
            "first_failure":"original_floor_source_room_wall_path_not_unique",
            "original_floor_source_graph":floor_graph,
            "new_firm_quantities":0,
        }
    source_edges=floor_graph["original_native_edges"]
    points=[tuple(p) for e in source_edges for p in e["endpoints_pdf_pts"]]
    x0=min(p[0] for p in points)
    x1=max(p[0] for p in points)
    y0=min(p[1] for p in points)
    y1=max(p[1] for p in points)
    if not x0<x1 or not y0<y1:
        raise ValueError("original_floor_source_bounds_not_real")
    floor_x=x1-x0
    floor_y=y1-y0
    # Printed PWD room words must be wholly INSIDE their own plan's
    # source ink; printed D13 must touch the actual top doorway edge.
    # A separate PWD ELEVATION on the same A502 sheet also prints D13;
    # label equality with the floor plan is therefore not enough.
    def inside_room(word,bounds):
        l,t,r,bot=bounds
        return l<float(word[0])<float(word[2])<r and (
            t<float(word[1])<float(word[3])<bot)
    def printed_door_at_top(word,bounds):
        l,t,r,_=bounds
        midpoint=(float(word[0])+float(word[2]))/2
        return l<midpoint<r and float(word[1])<=t<=float(word[3])
    source_boxes=tuple(
        candidate["original_source_native_bbox_pdf_pts"]
        for candidate in face["original_source_candidate_face_families"]
    )
    floor_box=(x0,y0,x1,y1)
    if (not inside_room(fw,floor_box)
            or not all(inside_room(dw,b) for b in source_boxes)
            or not printed_door_at_top(fd,floor_box)
            or not any(printed_door_at_top(dd,b) for b in source_boxes)):
        raise ValueError("original_plan_word_or_door_boundary_not_source_owned")
    geometries=[]
    for candidate in face["original_source_candidate_face_families"]:
        cx0,cy0,cx1,cy1=candidate["original_source_native_bbox_pdf_pts"]
        scale_x=(cx1-cx0)/floor_x
        scale_y=(cy1-cy0)/floor_y
        disagreement=abs(scale_x-scale_y)/max(scale_x,scale_y)
        geometries.append({
            "original_detail_face_family":candidate[
                "source_native_family_id_untrusted"],
            "original_floor_source_bbox_pdf_pts":[x0,y0,x1,y1],
            "original_detail_source_bbox_pdf_pts":[cx0,cy0,cx1,cy1],
            "source_independent_axis_scale_x":scale_x,
            "source_independent_axis_scale_y":scale_y,
            "source_original_axes_relative_disagreement":disagreement,
            "source_original_scale_ratio_is_not_calibration":True,
            "same_physical_room_issuer_granted":False,
        })
    return {
        "status":"original_detail_floor_source_coincidence_candidates_only",
        "first_failure":"same_W4_wall_face_and_canonical_room_decision_scope_unverified",
        "original_source_sha256":source_sha256,
        "original_floor_page_1_based":original_floor_page,
        "original_detail_page_1_based":original_detail_page,
        "original_page_rotations_degrees":original_rotations,
        "source_original_plan_caption_evidence":caption,
        "source_original_room_and_door_word_candidates":marks,
        "original_source_plan_words_inside_own_physical_ink_candidates":True,
        "original_source_door_word_intersects_printed_top_boundary":True,
        "source_original_room_ink_graph":floor_graph,
        "source_all_figured_inner_outer_axis_correspondence_candidates":
            tuple(geometries),
        "original_source_figured_area_m2_candidate_not_signed":face[
            "original_source_figured_area_m2_candidate_not_signed"],
        "source_original_detail_to_main_floor_same_room_authenticated":False,
        "source_W4_finished_floor_or_wall_role_authenticated":False,
        "new_firm_quantities":0,
    }
