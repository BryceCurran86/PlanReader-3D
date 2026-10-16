"""Original source-sided structural ink pairing (read-only, fail-closed).

Eight independently checkable gates: (1) exact path/item ancestry, (2) original
stroke style, (3) axis/finite geometry, (4) interval continuity without bridging
openings, (5) opposed parallel coordinates, (6) common physical extent,
(7) competing source interval leftovers, (8) no wall/room/ceiling promotion.
Caller supplies competing candidate families; neither coordinates nor widths
elect a physical wall. No source PDF mutation or W2 2.5pt snapping.
"""
from __future__ import annotations

from collections import defaultdict
import math
import re

ID = re.compile(r"^d(0|[1-9][0-9]*)i(0|[1-9][0-9]*)$")


def native_ink_record(page, source_id):
    if type(source_id) is not str or ID.fullmatch(source_id) is None:
        raise ValueError("exact_source_native_path_item_required")
    path, item = (int(x) for x in ID.fullmatch(source_id).groups())
    drawings = page.get_drawings()
    if path >= len(drawings) or item >= len(drawings[path].get("items",())):
        raise ValueError("original_source_primitive_not_present")
    parent = drawings[path]
    stroke = parent["items"][item]
    if stroke[0] != "l":
        raise ValueError("source_primitive_not_native_line")
    a,b = stroke[1:3]
    values = tuple(round(float(x),3) for x in (a.x,a.y,b.x,b.y))
    if not all(math.isfinite(x) for x in values):
        raise ValueError("nonfinite_original_ink")
    if values[0] == values[2] and values[1] != values[3]:
        axis,coordinate,start,stop = "native_y",values[0],values[1],values[3]
    elif values[1] == values[3] and values[0] != values[2]:
        axis,coordinate,start,stop = "native_x",values[1],values[0],values[2]
    else:
        raise ValueError("source_primitive_not_nonzero_orthogonal_line")
    color = parent.get("color")
    width = parent.get("width")
    opacity = parent.get("stroke_opacity",1.)
    if (color is None or width is None or opacity is None
            or not isinstance(color,(tuple,list))
            or not all(math.isfinite(float(c)) for c in color)
            or not math.isfinite(float(width))
            or not math.isfinite(float(opacity))):
        raise ValueError("source_paint_role_unreadable")
    return {
        "original_source_primitive_id":source_id,
        "original_native_endpoints_pdf_pts":list(values),
        "native_line_axis":axis,
        "native_axis_coordinate_pdf_pt":coordinate,
        "native_interval_pdf_pts":[min(start,stop),max(start,stop)],
        "original_color":list(color),
        "original_stroke_width_pdf_pt":float(width),
        "original_opacity":float(opacity),
        "original_stroke_is_structural_wall_authenticated":False,
    }


def union_source_intervals(rows):
    intervals = sorted((r[0],r[1]) for r in rows)
    out = []
    for start,stop in intervals:
        if start >= stop:
            continue
        if out and start <= out[-1][1]:
            out[-1][1]=max(out[-1][1],stop)
        else:
            out.append([start,stop])
    return out


def _intersect_intervals(left,right):
    result=[]
    for a,b in left:
        for c,d in right:
            lo,hi=max(a,c),min(b,d)
            if hi>lo:
                result.append([lo,hi])
    return union_source_intervals(result)


def source_parallel_face_candidates(
    page, *, native_side_a:tuple[str,...], native_side_b:tuple[str,...],
):
    if (type(native_side_a) is not tuple or type(native_side_b) is not tuple
            or not native_side_a or not native_side_b
            or len(set(native_side_a+native_side_b))!=len(native_side_a+native_side_b)):
        raise ValueError("distinct_explicit_competing_source_faces_required")
    a=[native_ink_record(page,x) for x in native_side_a]
    b=[native_ink_record(page,x) for x in native_side_b]
    sides=(a,b)
    axes={row["native_line_axis"] for side in sides for row in side}
    if len(axes)!=1:
        return {"status":"source_face_axis_conflict","original_candidate_rows":a+b,
                "new_wall_authority":0,"new_room_authority":0}
    coords=[{r["native_axis_coordinate_pdf_pt"] for r in side}
            for side in sides]
    if len(coords[0])!=1 or len(coords[1])!=1 or coords[0]==coords[1]:
        return {"status":"source_face_ordinate_nonunique_or_same","original_candidate_rows":a+b,
                "new_wall_authority":0,"new_room_authority":0}
    style_sets=[
        {(tuple(r["original_color"]),round(r["original_stroke_width_pdf_pt"],3),
          round(r["original_opacity"],3)) for r in side}
        for side in sides
    ]
    style_matches=style_sets[0]==style_sets[1] and len(style_sets[0])==1
    spans=[union_source_intervals([
        r["native_interval_pdf_pts"] for r in side
    ]) for side in sides]
    overlap=_intersect_intervals(*spans)
    full_a=sum(e-s for s,e in spans[0])
    full_b=sum(e-s for s,e in spans[1])
    shared=sum(e-s for s,e in overlap)
    return {
        "status":"source_paint_consistent_parallel_candidate_pair" if style_matches else "source_paint_mismatch_competing_parallel_lines",
        "original_native_axis":next(iter(axes)),
        "source_parallel_axis_coordinates":[next(iter(cs)) for cs in coords],
        "source_parallel_face_separation_pdf_pts":abs(next(iter(coords[0]))-next(iter(coords[1]))),
        "source_unbridged_side_intervals_pdf_pts":spans,
        "source_shared_opposed_intervals_pdf_pts":overlap,
        "source_shared_opposed_length_pdf_pt":shared,
        "source_side_lengths_pdf_pt":[full_a,full_b],
        "source_complete_opposed_intervals_without_added_ink":shared==full_a==full_b,
        "original_candidate_rows":a+b,
        "competing_line_roles_must_be_reviewed":True,
        "original_native_endpoint_contacts_only":True,
        "source_ink_style_consistent_not_wall_role":style_matches,
        "original_structural_wall_role_authenticated":False,
        "physical_room_ring_source_closed":False,
        "ceiling_plan_metric_area_authority_granted":False,
        "new_wall_authority":0,
        "new_room_authority":0,
        "new_quantities":0,
    }
