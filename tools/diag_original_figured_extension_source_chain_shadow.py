"""Original figured leader→physical face extension ink first-failure census.

This tool never treats projected wall-face alignment, printed numerical
dimensions or arrow heads as a physical witness. A complete continuous
original native extension line is a necessary but NOT sufficient condition:
the chosen face's structural role, figure and source issuer must separately
pass existing production measurement authority.
"""
from __future__ import annotations
import re
import math

_ID=re.compile(r"^d(\d+)i(\d+)$")


def _item(paths,identity):
    m=_ID.fullmatch(identity) if type(identity) is str else None
    if not m:raise ValueError("original_source_line_id_required")
    p,i=map(int,m.groups())
    if p>=len(paths) or i>=len(paths[p]["items"]):
        raise ValueError("original_native_source_path_missing")
    it=paths[p]["items"][i]
    if it[0]!="l" or len(it)<3:
        raise ValueError("source_line_item_not_straight")
    a,b=it[1:3]
    x,y,X,Y=[round(float(v),3) for v in (a.x,a.y,b.x,b.y)]
    if not all(math.isfinite(v) for v in (x,y,X,Y)):
        raise ValueError("finite_native_line_required")
    return ((x,y),(X,Y))


def _axis(points):
    (x,y),(X,Y)=points
    if x==X and y!=Y:return "vertical"
    if y==Y and x!=X:return "horizontal"
    raise ValueError("original_axis_straight_line_required")


def audit_figured_extension_to_source_face(
    page,*, original_dimension_line_id:str, original_face_line_id:str,
    dimension_endpoint_index:int, max_source_paths:int=120000,
    max_witness_lines:int=20000,
):
    if type(dimension_endpoint_index) is not int or dimension_endpoint_index not in (0,1):
        raise ValueError("explicit_source_dimension_endpoint_required")
    paths=page.get_drawings()
    if len(paths)>max_source_paths:
        return {"status":"native_source_path_cap_exceeded",
                "figured_face_connection_authority":False}
    dim=_item(paths,original_dimension_line_id)
    face=_item(paths,original_face_line_id)
    axis=_axis(dim)
    if _axis(face)==axis:
        raise ValueError("figured_and_face_axes_must_be_opposed")
    start=dim[dimension_endpoint_index]
    if axis=="vertical":
        # Horizontal witness at the figured axis terminal y. The face is
        # horizontal, but choosing its nearest x end is only a candidate
        # for original extension-line connectivity.
        if start[1]!=face[0][1]:
            raise ValueError("no_same_ordinate_figure_face_projection")
        target=min(face,key=lambda q:abs(q[0]-start[0]))
        fixed=start[1]; lo,hi=sorted((start[0],target[0]))
        direction="horizontal"
    else:
        if start[0]!=face[0][0]:
            raise ValueError("no_same_abscissa_figure_face_projection")
        target=min(face,key=lambda q:abs(q[1]-start[1]))
        fixed=start[0]; lo,hi=sorted((start[1],target[1]))
        direction="vertical"
    if hi<=lo:
        raise ValueError("no_positive_source_extension_interval")
    candidates=[]
    for pi,path in enumerate(paths):
        for ii,it in enumerate(path.get("items",())):
            if not it or it[0]!="l":continue
            try:
                a,b=it[1:3]
                x,y,X,Y=(round(float(v),3) for v in (a.x,a.y,b.x,b.y))
            except (TypeError,ValueError,OverflowError,AttributeError):
                continue
            if direction=="horizontal":
                if y!=fixed or Y!=fixed or x==X:continue
                v,w=sorted((x,X))
            else:
                if x!=fixed or X!=fixed or y==Y:continue
                v,w=sorted((y,Y))
            u=max(lo,v);z=min(hi,w)
            if z>u:
                if len(candidates)>=max_witness_lines:
                    return {"status":"native_witness_cap_exceeded",
                            "figured_face_connection_authority":False}
                candidates.append({"original_source_item_id":f"d{pi}i{ii}",
                                   "candidate_intersection_interval_pdf_pts":[u,z],
                                   "extension_ink_role_verified":False})
    # These intervals may be drafting lines, arrowheads or fixtures. Even
    # an interval-connected chain needs independent original extension
    # stroke role/source ownership before granting any figured dimension.
    intervals=sorted(tuple(r["candidate_intersection_interval_pdf_pts"]) for r in candidates)
    missing=[];right=lo
    for a,b in intervals:
        if a>right:missing.append([right,a])
        right=max(right,b)
    if right<hi:missing.append([right,hi])
    return {
        "status":"native_original_figured_extension_source_candidates",
        "dimension_line_id":original_dimension_line_id,
        "face_line_id":original_face_line_id,
        "original_dimension_terminal_pdf_pts":list(start),
        "original_projection_target_pdf_pts":list(target),
        "native_projected_extension_length_pdf_pts":round(hi-lo,3),
        "source_intersecting_straight_ink_candidates":candidates,
        "original_uncovered_projection_intervals_pdf_pts":missing,
        "candidate_native_ink_projection_covered":not missing,
        "figured_extension_source_role_proven":False,
        "physical_finished_face_or_wall_role_proven":False,
        "figured_face_connection_authority":False,
        "new_firm_quantities":0,
    }
