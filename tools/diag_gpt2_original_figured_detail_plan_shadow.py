"""Original native figured dimension-pair audit for an independent detail plan.

This source-only issuer reads the actual printed mm words, the full original
continuous dimension lines and BOTH original arrow/tick pairs at each end.
A value is NEVER caller-supplied. Two independently figured orthogonal lengths
can yield a numeric m² CANDIDATE, not a physical room, finished face or signed
customer takeoff. The detail-to-main-plan identity is a separate gate.

No drawing-specific dimensions/codes, global snapping or benchmark truth here.
"""
from __future__ import annotations
import hashlib
import math
import re

import fitz
from tools.diag_original_room_four_edge_source_ink_shadow import _line


def _word_at(words, address):
    if (type(address) is not tuple or len(address)!=3
            or any(type(n) is not int or n<0 for n in address)):
        raise ValueError("original_figure_native_word_address_required")
    found=[word for word in words if tuple(word[5:8])==address]
    if len(found)!=1:
        raise ValueError("original_figure_native_word_not_unique")
    return found[0]


def _source_dimension(page, *, label_address, line_id, first_ticks, last_ticks):
    drawings=page.get_drawings()
    line=_line(drawings,line_id)
    ends=line["ends"]
    if ends[0]==ends[1] or not (ends[0][0]==ends[1][0] or ends[0][1]==ends[1][1]):
        raise ValueError("original_figure_line_not_axis_aligned")
    if line["source_color"]!=(0.,0.,0.) or line["stroke_width"]<=0:
        raise ValueError("original_figure_line_paint_mismatch")
    if (type(first_ticks) is not tuple or type(last_ticks) is not tuple
            or len(first_ticks)!=2 or len(last_ticks)!=2
            or len({line_id,*first_ticks,*last_ticks})!=5):
        raise ValueError("four_distinct_native_dimension_arrowheads_required")
    arrowheads=[]
    for endpoint, ids in ((ends[0],first_ticks),(ends[1],last_ticks)):
        for tick_id in ids:
            tick=_line(drawings,tick_id)
            if endpoint not in tick["ends"]:
                raise ValueError("source_figure_arrowhead_endpoint_not_bound")
            if (tick["source_color"]!=line["source_color"]
                    or tick["stroke_opacity"]!=line["stroke_opacity"]
                    or tick["stroke_width"]<=line["stroke_width"]):
                raise ValueError("original_figure_arrowhead_paint_family_conflict")
            arrowheads.append(tick)
        if (arrowheads[-1]["ends"]==arrowheads[-2]["ends"]):
            raise ValueError("duplicate_original_figure_arrowhead_geometry")
        other_points=[]
        for arrow in arrowheads[-2:]:
            tip=[p for p in arrow["ends"] if p!=endpoint]
            if len(tip)!=1:
                raise ValueError("source_figure_arrowhead_not_nonzero")
            other_points.append(tip[0])
        vectors=[(pt[0]-endpoint[0],pt[1]-endpoint[1])
                 for pt in other_points]
        if (vectors[0][0]*vectors[1][0]+vectors[0][1]*vectors[1][1]>=0
                or (ends[0][1]==ends[1][1]
                    and (vectors[0][1]==0 or vectors[1][1]==0))
                or (ends[0][0]==ends[1][0]
                    and (vectors[0][0]==0 or vectors[1][0]==0))):
            # Both printed arrow ticks must independently point away from
            # their own terminal. Two coincident or collinear dimension
            # strokes must not counterfeit actual original end marks.
            raise ValueError("original_figure_arrowhead_direction_conflict")
    word=_word_at(page.get_text("words"),label_address)
    text=str(word[4])
    if re.fullmatch(r"[1-9][0-9]{1,5}",text) is None:
        raise ValueError("source_figure_text_not_integer_mm")
    x0,y0,x1,y1=tuple(float(w) for w in word[:4])
    if not (all(math.isfinite(v) for v in (x0,y0,x1,y1))
            and x0<x1 and y0<y1):
        raise ValueError("source_figure_text_bbox_invalid")
    horizontal=ends[0][1]==ends[1][1]
    axis_value=ends[0][1] if horizontal else ends[0][0]
    label_mid=((x0+x1)/2,(y0+y1)/2)
    # Text must be over its original dimension stroke, in the plotted span.
    # Typographic offset is bounded by its own actual printed glyph height,
    # not a project-specific "nearest room" proximity tolerance.
    mid=label_mid[0] if horizontal else label_mid[1]
    lo=min(ends[0][0 if horizontal else 1],
           ends[1][0 if horizontal else 1])
    hi=max(ends[0][0 if horizontal else 1],
           ends[1][0 if horizontal else 1])
    off=abs(label_mid[1 if horizontal else 0]-axis_value)
    if not (lo<mid<hi and off<=2*(y1-y0)):
        raise ValueError("original_figure_not_printed_on_own_dimension_line")
    length=math.dist(*ends)
    value_mm=float(text)
    return {
        "original_figured_mm":value_mm,
        "original_native_figure_literal":text,
        "original_native_word_address":list(label_address),
        "original_native_word_bbox_pdf_pts":[x0,y0,x1,y1],
        "original_dimension_line_source_id":line_id,
        "original_dimension_line_source_endpoints_pdf_pts":[list(v) for v in ends],
        "original_source_arrowhead_ids":tuple((*first_ticks,*last_ticks)),
        "original_source_dimension_axis":"horizontal" if horizontal else "vertical",
        "source_figured_line_span_pdf_pts":length,
        "source_figured_mm_per_native_pdf_pt":value_mm/length,
        "original_figure_source_ink_but_not_room_binding":True,
    }


def audit_original_figured_detail_plan_pair(
    original_pdf_bytes:bytes, *, expected_sha256:str,
    page_1_based:int,
    first_dimension:dict, second_dimension:dict,
    original_room_word_address:tuple[int,int,int],
    original_finish_word_address:tuple[int,int,int],
    plan_enclosure_bbox_pdf_pts:tuple[float,float,float,float],
)->dict:
    """Original printed word+two end-arrow pairs + same-scale evidence.

    The two printed lengths are independent mm measurements. Native planar
    coordinates do NOT confer physical W4 room identity or infer floor finish.
    """
    if (type(original_pdf_bytes) is not bytes or
            hashlib.sha256(original_pdf_bytes).hexdigest()!=expected_sha256):
        raise ValueError("original_source_sha_mismatch")
    if type(page_1_based) is not int or page_1_based<1:
        raise ValueError("original_detail_source_page_invalid")
    if (type(first_dimension) is not dict or type(second_dimension) is not dict
            or set(first_dimension)!={"label_address","line_id","first_ticks","last_ticks"}
            or set(second_dimension)!=set(first_dimension)):
        raise ValueError("two_independent_original_figures_required")
    id_list=[item
             for row in (first_dimension,second_dimension)
             for item in (row["line_id"],*row["first_ticks"],*row["last_ticks"])]
    if len(set(id_list))!=len(id_list):
        raise ValueError("figure_line_or_tick_source_owner_reused")
    if type(plan_enclosure_bbox_pdf_pts) is not tuple or len(plan_enclosure_bbox_pdf_pts)!=4:
        raise ValueError("explicit_source_detail_plan_bbox_required")
    try:
        box=tuple(float(x) for x in plan_enclosure_bbox_pdf_pts)
    except (TypeError,ValueError,OverflowError):
        raise ValueError("explicit_source_detail_plan_bbox_required") from None
    if not (all(math.isfinite(v) for v in box)
            and box[0]<box[2] and box[1]<box[3]):
        raise ValueError("explicit_source_detail_plan_bbox_required")
    with fitz.open(stream=original_pdf_bytes,filetype="pdf") as pdf:
        if page_1_based>len(pdf):
            raise ValueError("original_detail_source_page_invalid")
        page=pdf[page_1_based-1]
        first=_source_dimension(page,**first_dimension)
        second=_source_dimension(page,**second_dimension)
        if first["original_source_dimension_axis"]==second["original_source_dimension_axis"]:
            raise ValueError("printed_figures_not_independent_orthogonal_axes")
        words=page.get_text("words")
        marks=[]
        for address in (original_room_word_address,original_finish_word_address):
            word=_word_at(words,address)
            wbox=tuple(float(v) for v in word[:4])
            if not (box[0]<wbox[0]<wbox[2]<box[2] and
                    box[1]<wbox[1]<wbox[3]<box[3]):
                raise ValueError("source_room_or_finish_word_outside_detail_plan")
            marks.append({
                "original_word_address":list(address),
                "original_literal_untrusted":str(word[4]),
                "original_bbox_pdf_pts":list(wbox),
            })
    if first["original_native_word_address"]==second["original_native_word_address"]:
        raise ValueError("duplicate_original_dimension_word")
    ratio1=first["source_figured_mm_per_native_pdf_pt"]
    ratio2=second["source_figured_mm_per_native_pdf_pt"]
    relative_difference=abs(ratio1-ratio2)/max(ratio1,ratio2)
    # 1% is a CANDIDATE-quality contradiction gate only; not an
    # authoritative drawing scale nor a global geometry tolerance.
    if relative_difference>.01:
        return {
            "status":"original_orthogonal_figures_source_scale_conflict",
            "first_failure":"two_original_dimension_lines_disagree",
            "original_figured_source_records":(first,second),
            "scale_ratio_relative_disagreement":relative_difference,
            "new_firm_quantities":0,
        }
    return {
        "status":"original_figured_orthogonal_detail_area_candidate_only",
        "first_failure":"same_W4_physical_room_and_finished_face_identity_unverified",
        "original_source_sha256":expected_sha256,
        "original_page_1_based":page_1_based,
        "original_figured_source_records":(first,second),
        "original_room_and_finish_mark_candidates":tuple(marks),
        "source_detail_plan_bbox_pdf_pts":box,
        "source_figured_line_scales_agree_as_candidate":True,
        "scale_ratio_relative_disagreement":relative_difference,
        "candidate_orthogonal_area_m2_not_signed":
            round(first["original_figured_mm"]*second["original_figured_mm"]/1_000_000,9),
        "source_finished_face_ownership_authenticated":False,
        "source_physical_room_crosssheet_identity_authenticated":False,
        "new_firm_quantities":0,
    }
