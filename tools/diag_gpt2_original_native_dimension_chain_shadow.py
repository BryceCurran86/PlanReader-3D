"""Original native dimension-chain ink: printed major dimensions and wall notes.

The actual arrowhead pair, not the full drafting stroke, defines a short
printed dimension's ends: a line may overrun a tick by several PDF points.
Only exact original SHA-pinned path-item and text provenance can contribute.
The result does NOT authenticate structural wall roles, finished faces, room
m², the named room or a cross-sheet correspondence.
"""
from __future__ import annotations

import hashlib
import math
import re

import fitz

from tools.diag_original_room_four_edge_source_ink_shadow import _line


_ROLES=("short_before","main","short_after")


def _word(page, address):
    if (type(address) is not tuple or len(address)!=3 or
            any(type(v) is not int or v<0 for v in address)):
        raise ValueError("original_dimension_chain_word_address_required")
    found=[w for w in page.get_text("words") if
           len(w)>=8 and tuple(w[5:8])==address]
    if len(found)!=1 or not re.fullmatch(r"[1-9][0-9]{0,5}",str(found[0][4])):
        raise ValueError("original_dimension_chain_word_missing_or_not_figured")
    return found[0]


def _anchored_tick_point(drawings, ids, parent, axis):
    if (type(ids) is not tuple or len(ids)!=2 or
            len(set(ids))!=2):
        raise ValueError("two_original_dimension_arrow_source_ids_required")
    a,b=(_line(drawings,item) for item in ids)
    if (a["source_color"]!=parent["source_color"] or
            b["source_color"]!=parent["source_color"] or
            a["stroke_opacity"]!=parent["stroke_opacity"] or
            b["stroke_opacity"]!=parent["stroke_opacity"] or
            min(a["stroke_width"],b["stroke_width"])<=parent["stroke_width"]):
        raise ValueError("original_dimension_arrow_paint_family_conflict")
    shared=set(map(tuple,a["ends"])) & set(map(tuple,b["ends"]))
    if len(shared)!=1:
        raise ValueError("original_dimension_arrow_tip_not_unique")
    center=next(iter(shared))
    v=[]
    for row in (a,b):
        end=next((point for point in row["ends"] if point!=center),None)
        if end is None:
            raise ValueError("original_dimension_arrow_zero_length")
        v.append((end[0]-center[0],end[1]-center[1]))
    if (v[0][0]*v[1][0]+v[0][1]*v[1][1]>=0 or
            (axis=="horizontal" and any(vec[1]==0 for vec in v)) or
            (axis=="vertical" and any(vec[0]==0 for vec in v))):
        raise ValueError("original_dimension_arrow_tip_direction_conflict")
    return center


def _segment(page, record, *, axis):
    if (type(record) is not dict or set(record)!=
            {"line_id","word_address","first_ticks","last_ticks"}):
        raise ValueError("original_dimension_chain_segment_fields_required")
    drawings=page.get_drawings()
    parent=_line(drawings,record["line_id"])
    a,b=parent["ends"]
    if (axis=="horizontal" and (a[1]!=b[1] or a[0]==b[0])
            or axis=="vertical" and (a[0]!=b[0] or a[1]==b[1])):
        raise ValueError("original_dimension_chain_axis_mismatch")
    tips=(
        _anchored_tick_point(drawings,record["first_ticks"],parent,axis),
        _anchored_tick_point(drawings,record["last_ticks"],parent,axis),
    )
    k=0 if axis=="horizontal" else 1
    other=1-k
    lo,hi=sorted((a[k],b[k]))
    coords=sorted((tips[0][k],tips[1][k]))
    if (tips[0]==tips[1] or any(t[other]!=a[other] for t in tips)
            or coords[0]<lo or coords[1]>hi):
        raise ValueError("original_dimension_tip_outside_own_source_line")
    w=_word(page,record["word_address"])
    raw_bbox=tuple(float(v) for v in w[:4])
    if not all(math.isfinite(v) for v in raw_bbox):
        raise ValueError("original_dimension_word_nonfinite")
    midpoint=(raw_bbox[k]+raw_bbox[k+2])/2
    if not coords[0]<midpoint<coords[1]:
        raise ValueError("original_figure_text_outside_arrowhead_interval")
    value=int(w[4])
    actual=round(coords[1]-coords[0],3)
    if not actual:
        raise ValueError("original_dimension_zero_arrowhead_span")
    return {
        "original_literal_mm_untrusted":str(w[4]),
        "original_word_address":list(record["word_address"]),
        "original_source_line_id":record["line_id"],
        "original_arrowhead_native_ids":record["first_ticks"]+record["last_ticks"],
        "source_dimension_axis":axis,
        "source_native_line_extent_pdf_pts":[lo,hi],
        "original_arrowhead_tips_pdf_pts":coords,
        "source_original_line_overhangs_pdf_pts":[
            round(coords[0]-lo,3),round(hi-coords[1],3)],
        "native_printed_dimension_span_pdf_pt":actual,
        "printed_dimension_mm_per_pdf_pt_candidate":value/actual,
        "source_original_dimension_mm":value,
        "finished_face_and_wall_role_proven":False,
    }


def audit_original_native_orthogonal_dimension_chains(
    original_pdf_bytes:bytes, *, expected_sha256:str,
    page_1_based:int,
    vertical:dict, horizontal:dict,
)->dict:
    """Three printed source dimensions on each independent original axis.

    Each chain is first short / main / last short. The arrow tips of each
    neighbor MUST coincide. Shared arrowheads are intentionally allowed:
    the two adjacent original lines print the SAME terminal tick family.
    """
    if (type(original_pdf_bytes) is not bytes or
            hashlib.sha256(original_pdf_bytes).hexdigest()!=expected_sha256):
        raise ValueError("original_dimension_chain_source_sha_mismatch")
    if (type(vertical) is not dict or type(horizontal) is not dict or
            set(vertical)!=set(_ROLES) or set(horizontal)!=set(_ROLES)):
        raise ValueError("two_original_complete_dimension_chains_required")
    with fitz.open(stream=original_pdf_bytes,filetype="pdf") as doc:
        if type(page_1_based) is not int or not 1<=page_1_based<=len(doc):
            raise ValueError("original_dimension_chain_pdf_page_invalid")
        page=doc[page_1_based-1]
        records={
            axis:{role:_segment(page,config[role],axis=axis)
                  for role in _ROLES}
            for axis,config in (("vertical",vertical),("horizontal",horizontal))
        }
    results={}
    for axis,parts in records.items():
        before,main,after=(parts[r] for r in _ROLES)
        a,b,c=(p["original_arrowhead_tips_pdf_pts"]
               for p in (before,main,after))
        if a[1]!=b[0] or b[1]!=c[0]:
            raise ValueError("source_original_dimensional_chain_terminal_gap")
        all_lines=[parts[r]["original_source_line_id"] for r in _ROLES]
        if len(set(all_lines))!=3:
            raise ValueError("original_source_dimension_line_reused")
        printed=[p["source_original_dimension_mm"] for p in (before,main,after)]
        if printed[0]!=printed[2]:
            # A wall-size note can legitimately vary side to side. Retain
            # the mismatch instead of forcing two wall thicknesses equal.
            equal_outer_notes=False
        else:
            equal_outer_notes=True
        main_ratio=main["printed_dimension_mm_per_pdf_pt_candidate"]
        ratios=[p["printed_dimension_mm_per_pdf_pt_candidate"]
                for p in (before,after)]
        results[axis]={
            "original_source_records":parts,
            "original_dimension_chain_mm":printed,
            "source_adjacent_outer_notes_equal":equal_outer_notes,
            "original_arrowhead_connected_chain_pdf_pts":[a[0],b[0],b[1],c[1]],
            "source_small_figure_ratio_relative_deviations":[
                abs(v-main_ratio)/max(v,main_ratio) for v in ratios],
            "source_wall_material_or_finished_face_proven":False,
            "source_dimension_chain_meaning_as_net_area_proven":False,
        }
    return {
        "status":"source_orthogonal_native_figured_chains_candidate_only",
        "original_source_sha256":expected_sha256,
        "original_detail_page_1_based":page_1_based,
        "native_printed_dimension_chains":results,
        "first_unclosed_gate":"same_W4_finished_face_and_original_wall_build_up_semantics",
        "source_finished_net_area_m2":None,
        "new_firm_quantities":0,
    }
