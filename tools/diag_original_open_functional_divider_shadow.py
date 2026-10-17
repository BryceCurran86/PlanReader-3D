"""Original-source partial divider between functional floor-finish sections.

A partial structural-looking partition cannot split one connected floor into
two finished physical rooms. This source-ink audit preserves the actual
north opening and original code-word parents. It does not grant structural
W4 wall ownership or a material-occurrence/area quantity.
"""
from __future__ import annotations
import hashlib
import re
import math
import fitz

_PATH=re.compile(r"^d([0-9]+)i([0-9]+)$")


def _native_line(paths,source_id):
    match=_PATH.fullmatch(source_id) if type(source_id) is str else None
    if match is None:raise ValueError("original_source_path_item_id_required")
    i,j=map(int,match.groups())
    if i>=len(paths) or j>=len(paths[i].get("items",())):
        raise ValueError("original_source_stroke_missing")
    it=paths[i]["items"][j]
    if it[0]!="l" or len(it)<3:
        raise ValueError("original_straight_ink_required")
    a,b=it[1:3]
    nums=[round(float(v),3) for v in (a.x,a.y,b.x,b.y)]
    if not all(math.isfinite(v) for v in nums):raise ValueError("finite_original_ink_required")
    parent=paths[i]
    try:
        width=float(parent.get("width") or 0)
        opacity=float(parent.get("stroke_opacity") or 0)
        color=tuple(float(v) for v in (parent.get("color") or ()))
    except (TypeError, ValueError, OverflowError):
        raise ValueError("original_divider_paint_ink_untrusted") from None
    if (not math.isfinite(width) or width<=0
            or not math.isfinite(opacity) or not 0<opacity<=1
            or not color or any(not math.isfinite(c) or not 0<=c<=1 for c in color)
            or "s" not in str(parent.get("type") or "")
            or "".join(str(parent.get("dashes") or "").split()) not in {"[]0",""}):
        raise ValueError("original_divider_paint_ink_untrusted")
    return nums,round(width,3),tuple(round(c,5) for c in color),round(opacity,6)


def audit_original_open_functional_divider(
    original_pdf:bytes,*,expected_sha256:str,page_1_based:int,
    shared_north_source_id:str,
    two_competing_divider_face_ids:tuple[str,str],
    left_mark_word_address:tuple[int,int,int],
    right_mark_word_address:tuple[int,int,int],
    expected_original_mark_literal:str,
    max_original_paths:int=120000,
):
    if type(original_pdf) is not bytes or hashlib.sha256(original_pdf).hexdigest()!=expected_sha256:
        raise ValueError("original_source_sha_mismatch")
    if (type(two_competing_divider_face_ids) is not tuple
            or len(two_competing_divider_face_ids)!=2
            or len(set(two_competing_divider_face_ids))!=2
            or any(type(a) is not tuple or len(a)!=3 for a in
                   (left_mark_word_address,right_mark_word_address))):
        raise ValueError("distinct_source_divider_and_mark_owners_required")
    with fitz.open(stream=original_pdf,filetype="pdf") as d:
        if not isinstance(page_1_based,int) or not 1<=page_1_based<=len(d):
            raise ValueError("source_page_required")
        p=d[page_1_based-1]
        drawings=p.get_drawings()
        if len(drawings)>max_original_paths:
            return {"status":"source_scope_cap_exceeded",
                    "structural_room_split_authenticated":False,
                    "new_firm_quantities":0}
        roof,width,north_color,north_opacity=_native_line(
            drawings,shared_north_source_id)
        faces=[_native_line(drawings,ref) for ref in two_competing_divider_face_ids]
        x,y,X,Y=roof
        if y!=Y or x==X or width<=0:
            raise ValueError("shared_original_north_ink_not_horizontal")
        north_y=y
        dividers=[]
        for (xx,yy,XX,YY),weight,color,opacity in faces:
            if xx!=XX or yy==YY or weight<=0:
                raise ValueError("original_divider_face_not_vertical")
            dividers.append({"x":xx,"y_start":min(yy,YY),
                             "y_end":max(yy,YY),"width":weight,
                             "source_color":color,"source_opacity":opacity})
        if (dividers[0]["source_color"]!=dividers[1]["source_color"]
                or dividers[0]["source_opacity"]!=dividers[1]["source_opacity"]):
            raise ValueError("original_competing_divider_paint_roles_conflict")
        if (dividers[0]["y_start"]!=dividers[1]["y_start"]
                or dividers[0]["y_end"]!=dividers[1]["y_end"]
                or dividers[0]["width"]!=dividers[1]["width"]
                or dividers[0]["x"]==dividers[1]["x"]):
            raise ValueError("original_competing_divider_ancestry_not_parallel")
        xl,xr=sorted(dv["x"] for dv in dividers)
        if not min(x,X)<xl<xr<max(x,X) or north_y>dividers[0]["y_start"]:
            raise ValueError("north_structural_ink_outside_competing_divider_scope")
        words={}
        for w in p.get_text("words"):
            if len(w)<8:continue
            key=tuple(int(v) for v in w[5:8])
            words.setdefault(key,[]).append(w)
        marks=[]
        for address in (left_mark_word_address,right_mark_word_address):
            matches=words.get(address,())
            if len(matches)!=1 or str(matches[0][4])!=expected_original_mark_literal:
                raise ValueError("exact_original_finish_word_missing_or_competing")
            w=matches[0]
            marks.append({
                "source_native_address":list(address),
                "raw_code_untrusted":str(w[4]),
                "original_word_bbox_pdf_pts":[float(v) for v in w[:4]],
                "native_text_issuer_authenticated":False,
            })
        if (marks[0]["original_word_bbox_pdf_pts"][2]>=xl
                or marks[1]["original_word_bbox_pdf_pts"][0]<=xr
                or any(z["original_word_bbox_pdf_pts"][1]<dividers[0]["y_start"]
                       or z["original_word_bbox_pdf_pts"][3]>dividers[0]["y_end"]
                       for z in marks)):
            raise ValueError("original_mark_not_in_opposing_partition_sections")
        gap=round(dividers[0]["y_start"]-north_y,3)
        return {
            "status":("original_partial_divider_has_open_north_connection"
                      if gap>0 else "original_divider_contacts_north_ink_candidate"),
            "original_shared_north_source":shared_north_source_id,
            "original_divider_face_source_ids":list(two_competing_divider_face_ids),
            "original_north_open_span_pdf_pts":gap,
            "open_passage_functional_zone_connection_candidate":gap>0,
            "source_connected_floor_space_candidate_only":gap>0,
            # Explicit original PDF-space corridor through which the two
            # functional zones remain connected at the divider's north tip.
            # A vertical partition cannot close this gap without INVENTING
            # missing ink between its start and the shared north edge.
            "source_unclosed_north_passage_bbox_pdf_pts":(
                [xl,north_y,xr,dividers[0]["y_start"]] if gap>0 else None
            ),
            "source_missing_north_divider_segments_pdf_pts":(
                [[[dv["x"],north_y],[dv["x"],dv["y_start"]]]
                 for dv in dividers] if gap>0 else []
            ),
            "source_connected_floor_space_structural_topology_proven":False,
            "original_competing_divider_face_separation_pdf_pts":round(xr-xl,3),
            "opposite_side_original_same_finish_marks":marks,
            "source_wall_structural_role_issued":False,
            "source_floors_separated_or_room_split_proven":False,
            "source_finish_zone_limits_issued":False,
            "new_firm_quantities":0,
        }
