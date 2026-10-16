"""Read-only original-PDF figured dimension -> physical witness-chain gate.

Unlike coordinate projections, figure *extensions* require a continuous
source-owned chain in the drawing. This diagnostic records every original
competing perpendicular stroke, exact segment support and gaps. It cannot
prove finished-face semantics, text integrity, wall role or room identity.
No expected room dimensions or source labels are used in decisions.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Any

_ID=re.compile(r"^d(0|[1-9][0-9]*)i(0|[1-9][0-9]*)$")
_SOURCE_PRECISION_PT=.001
_MAX_SOURCE_LINES=20000


def _source_axis_segment(item):
    try:
        if item[0]!="l": return None
        a,b=item[1:3]
        nums=tuple(round(float(x),3) for x in (a.x,a.y,b.x,b.y))
        if not all(math.isfinite(x) for x in nums):return None
        if nums[:2]==nums[2:]:return None
        if nums[0]==nums[2]:return (*nums,"native_y")
        if nums[1]==nums[3]:return (*nums,"native_x")
    except (TypeError,ValueError,IndexError,AttributeError,OverflowError):
        pass
    return None


def _source_line_inventory(page,*,max_original_lines=_MAX_SOURCE_LINES):
    if type(max_original_lines) is not int or max_original_lines<1:
        raise ValueError("positive_bounded_source_inventory_required")
    rows=[]
    for path,d in enumerate(page.get_drawings()):
        for i,item in enumerate(d.get("items",())):
            segment=_source_axis_segment(item)
            if segment is None:continue
            if len(rows)>=max_original_lines:
                return None
            rows.append({
                "original_source_primitive_id":f"d{path}i{i}",
                "native_line_pdf_pts":list(segment[:4]),
                "source_native_axis":segment[4],
                "source_stroke_width":d.get("width"),
                "source_stroke_color":d.get("color"),
                "original_structural_or_dimension_role_authenticated":False,
            })
    return rows


def _original_line(rows,source_id):
    if type(source_id) is not str or not _ID.fullmatch(source_id):
        raise ValueError("original_source_primitive_identity_required")
    hit=[row for row in rows if row["original_source_primitive_id"]==source_id]
    if len(hit)!=1:
        raise ValueError("original_source_primitive_unavailable_or_ambiguous")
    return hit[0]


def _interval_merge(intervals):
    """Closed exact intervals. A drafting gap cannot become physical ink."""
    intervals=sorted((min(a,b),max(a,b)) for a,b in intervals)
    merged=[]
    for a,b in intervals:
        if merged and a<=merged[-1][1]:
            merged[-1]=(merged[-1][0],max(merged[-1][1],b))
        else: merged.append((a,b))
    return merged


def _witness_gap(endpoint,candidate,perpendicular_rows,dim_axis):
    """Return actual line support/gap, not projected ordinate equality."""
    ex,ey=endpoint
    x0,y0,x1,y1=candidate
    if dim_axis=="native_y":
        # Dimension is vertical. Perpendicular horizontal source strokes
        # must cover the transverse x gap exactly at candidate face y.
        face_axis=y0 if y0==y1 else None
        if face_axis is None:return None
        target=min(max(ex,min(x0,x1)),max(x0,x1))
        along="native_x";ordinate=ey
        start,end=sorted((ex,target))
    else:
        face_axis=x0 if x0==x1 else None
        if face_axis is None:return None
        target=min(max(ey,min(y0,y1)),max(y0,y1))
        along="native_y";ordinate=ex
        start,end=sorted((ey,target))
    if abs(face_axis-ordinate)>_SOURCE_PRECISION_PT:
        return None
    supported=[]
    evidence=[]
    for row in perpendicular_rows:
        if row["source_native_axis"]!=along:continue
        v=row["native_line_pdf_pts"]
        if along=="native_x" and abs(v[1]-ordinate)<=_SOURCE_PRECISION_PT:
            supported.append((v[0],v[2]));evidence.append(row["original_source_primitive_id"])
        if along=="native_y" and abs(v[0]-ordinate)<=_SOURCE_PRECISION_PT:
            supported.append((v[1],v[3]));evidence.append(row["original_source_primitive_id"])
    merged=_interval_merge(supported)
    # An interval may contain both endpoints, or abut across original ink.
    contiguous=any(lo<=start and hi>=end for lo,hi in merged)
    if start==end:contiguous=True
    remaining=end-start
    for lo,hi in merged:
        remaining-=max(0,min(end,hi)-max(start,lo))
    return {
        "native_target_span_pdf_pts":[start,end],
        "matched_original_perpendicular_ink_ids":sorted(set(evidence)),
        "original_native_gap_pdf_pts":max(0,round(remaining,6)),
        "original_source_contiguous_ink_witness":bool(contiguous),
        "source_witness_graph_complete":False,
        "source_face_role_proven":False,
    }


def audit_figure_endpoint_witnesses(
    page: Any, *, dimension_source_id: str,
    candidate_wall_source_ids: tuple[str,...],
    max_original_lines:int=_MAX_SOURCE_LINES,
):
    """Explicit competitor set; missing true roles cannot be invented."""
    if (type(candidate_wall_source_ids) is not tuple
            or not candidate_wall_source_ids
            or len(set(candidate_wall_source_ids))!=len(candidate_wall_source_ids)):
        raise ValueError("explicit_competing_native_face_ids_required")
    rows=_source_line_inventory(page,max_original_lines=max_original_lines)
    if rows is None:
        return {
            "status":"original_line_universe_exceeds_shadow_cap",
            "source_universe_complete":False,
            "new_authoritative_dimensions":0,
            "new_physical_faces":0,
        }
    dim=_original_line(rows,dimension_source_id)
    v=dim["native_line_pdf_pts"]
    axis=dim["source_native_axis"]
    targets=[_original_line(rows,id) for id in candidate_wall_source_ids]
    ends=((v[0],v[1]),(v[2],v[3]))
    result=[]
    for end in ends:
        alternatives=[]
        for wall in targets:
            if wall["source_native_axis"]==axis:continue
            w=wall["native_line_pdf_pts"]
            witness=_witness_gap(end,w,rows,axis)
            if witness is None:continue
            alternatives.append({
                "original_competing_wall_ink_id":wall["original_source_primitive_id"],
                "source_candidate_line_pdf_pts":w,
                "source_style_color":wall["source_stroke_color"],
                "source_style_width":wall["source_stroke_width"],
                **witness,
                "finished_interior_face_or_wall_role_authenticated":False,
            })
        result.append({
            "original_dimension_endpoint_pdf_pts":list(end),
            "original_projected_wall_candidates":alternatives,
            "source_figure_to_face_witness_proven":False,
        })
    return {
        "status":"original_source_witness_candidates_only",
        "original_source_dimension_line_id":dimension_source_id,
        "source_dimension_line_native_axis":axis,
        "source_dimension_line_pdf_pts":v,
        "source_dimension_endpoints":result,
        "native_line_universe_examined":len(rows),
        "source_face_candidate_set_user_explicit_not_complete":True,
        "dimension_semantic_witness_proven":False,
        "original_physical_finished_faces_authenticated":False,
        "original_page_to_page_room_identity_authenticated":False,
        "new_authoritative_dimensions":0,
        "new_physical_faces":0,
        "new_quantities":0,
    }
