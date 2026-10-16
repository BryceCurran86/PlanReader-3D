"""Read-only original native source stepped partition / recess witness.

A toilet divider may change longitudinal axis at original source-produced
jogs. Detecting vertical strokes at multiple offsets is evidence against
blind rectangular room approximation, NOT proof of walls, room closure, area
or material. Original source path/item, original color/width and missing
join gaps remain visible for independent W2/W3/W4 classification.
"""
from __future__ import annotations

import math
from collections import defaultdict


def _box(v):
    try:
        a=tuple(float(x) for x in v)
    except (ValueError,TypeError,OverflowError):
        return None
    if len(a)!=4 or not all(math.isfinite(t) for t in a) or a[2]<=a[0] or a[3]<=a[1]:
        return None
    return a


def _line(it):
    try:
        if it[0]!="l":return None
        a,b=it[1:3]
        v=tuple(float(x) for x in (a.x,a.y,b.x,b.y))
    except (TypeError,ValueError,AttributeError,IndexError,OverflowError):
        return None
    if not all(math.isfinite(x) for x in v):return None
    if v[0]==v[2] and v[1]!=v[3]:return (*v,"native_y")
    if v[1]==v[3] and v[0]!=v[2]:return (*v,"native_x")
    return None


def audit_native_stepped_partition_source_candidates(
    page, *, candidate_region_bbox, min_source_stroke_length_pt=30.,
    max_native_strokes=20000,
):
    box=_box(candidate_region_bbox)
    if box is None:raise ValueError("valid_source_native_region_required")
    if (not isinstance(min_source_stroke_length_pt,(int,float))
            or type(min_source_stroke_length_pt) is bool
            or not math.isfinite(min_source_stroke_length_pt)
            or min_source_stroke_length_pt<=0):
        raise ValueError("positive_native_source_length_required")
    if type(max_native_strokes) is not int or max_native_strokes<1:
        raise ValueError("positive_source_stroke_cap_required")
    candidates=[]
    visited=0
    for path,d in enumerate(page.get_drawings()):
        for idx,it in enumerate(d.get("items",())):
            v=_line(it)
            if v is None:continue
            visited+=1
            if visited>max_native_strokes:
                return {"status":"original_source_stroke_scope_cap_exceeded",
                        "source_scope_complete":False,
                        "new_published_room_areas":0}
            x0,y0,x1,y1,axis=v
            if (max(x0,x1)<box[0] or min(x0,x1)>box[2]
                    or max(y0,y1)<box[1] or min(y0,y1)>box[3]):
                continue
            length=abs(x1-x0)+abs(y1-y0)
            if length<min_source_stroke_length_pt:continue
            candidates.append({
                "original_source_primitive_id":f"d{path}i{idx}",
                "original_native_line_pdf_pts":[round(n,3) for n in v[:4]],
                "native_axis":axis,
                "source_stroke_length_pdf_pts":round(length,3),
                "source_stroke_width_pdf_pts":d.get("width"),
                "source_stroke_color":d.get("color"),
                "source_ink_type_wall_or_fixture_authenticated":False,
            })
    runs=defaultdict(list)
    for row in candidates:
        if row["native_axis"]!="native_y":continue
        # Native source exact coordinate grouping, not W2 snapping.
        x=round(row["original_native_line_pdf_pts"][0],3)
        runs[x].append(row)
    axis_rows=[]
    for x,fragments in sorted(runs.items()):
        source_y=[z for f in fragments
                  for z in (f["original_native_line_pdf_pts"][1],
                            f["original_native_line_pdf_pts"][3])]
        axis_rows.append({
            "source_vertical_axis_pdf_pt":x,
            "original_source_y_span_pdf_pts":[min(source_y),max(source_y)],
            "original_source_member_ids":[
                f["original_source_primitive_id"] for f in fragments
            ],
            "native_vertical_source_strokes_complete_wall":False,
        })
    horizontal=[
        r for r in candidates if r["native_axis"]=="native_x"
    ]
    return {
        "status":"source_native_stepped_wall_and_recess_candidates_only",
        "candidate_original_native_region_pdf_pts":list(box),
        "original_source_stroke_scope_complete":True,
        "original_source_strokes_visited":visited,
        "original_axis_aligned_ink_candidates":candidates,
        "competing_original_vertical_axes":axis_rows,
        "cross_axis_original_ink_source_ids":[
            r["original_source_primitive_id"] for r in horizontal
        ],
        "source_native_multiple_parallel_axes_present":len(axis_rows)>1,
        "source_stepped_structural_wall_identity_authenticated":False,
        "partition_closes_independent_rooms":False,
        "door_gap_not_filled_or_closed_by_default":True,
        "source_physical_room_ring_complete":False,
        "new_published_room_areas":0,
        "new_floor_finish_quantities":0,
    }
