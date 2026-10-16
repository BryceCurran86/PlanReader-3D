"""Six independent default-unwired original-PDF source-ownership guards.

All return trace evidence, NEVER an authenticated SourceRoomFace, material,
measurement, opening or QuantityEvidence. Caller scopes are supplied source
candidate regions, NOT secretly elected viewports. Original native words can
be legible yet fail PDF text integrity. No nearest-label / default counts.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict


def _bbox(values):
    try:
        if isinstance(values,(str,bytes)):return None
        v=tuple(float(x) for x in values)
    except (TypeError,ValueError,OverflowError):
        return None
    if len(v)!=4 or not all(math.isfinite(t) for t in v) or v[0]>=v[2] or v[1]>=v[3]:
        return None
    return v


def _contains(box,point):
    return box[0]<=point[0]<=box[2] and box[1]<=point[1]<=box[3]


def _source_words(page):
    rows=[]
    for w in page.get_text("words"):
        if len(w)<8:continue
        bbox=_bbox(w[:4])
        if bbox is None:continue
        rows.append({
            "original_pdf_native_word_id":list(w[5:8]),
            "source_literal_untrusted":str(w[4]),
            "original_pdf_word_bbox_pts":list(bbox),
            "source_text_clip_unicode_paint_verified":False,
        })
    return rows


def _scope_rows(page,*,original_literal, candidate_scopes):
    if type(original_literal) is not str or not original_literal:
        raise ValueError("original_printed_literal_required")
    if not isinstance(candidate_scopes,dict) or not candidate_scopes:
        raise ValueError("explicit_competing_source_scopes_required")
    boxes={}
    for key,raw in candidate_scopes.items():
        if not isinstance(key,str) or not key or (box:=_bbox(raw)) is None:
            raise ValueError("valid_native_candidate_scope_required")
        boxes[key]=box
    words=[w for w in _source_words(page)
           if w["source_literal_untrusted"]==original_literal]
    rows=[]
    for w in words:
        b=w["original_pdf_word_bbox_pts"]
        centre=((b[0]+b[2])/2,(b[1]+b[3])/2)
        owners=[name for name,box in boxes.items() if _contains(box,centre)]
        rows.append({
            **w,
            "source_candidate_scopes_containing_word_center":owners,
            "source_physical_occurrence_owner_proven":False,
            "same_root_scope_source_authenticated":False,
            "competing_scope_count":len(owners),
        })
    return rows


def audit_floor_finish_mark_scope_candidates(
    page, *, source_finish_code:str, candidate_scopes:dict,
):
    """1. Enumerate every printed floor finish word, including schedules."""
    rows=_scope_rows(page,original_literal=source_finish_code,
                     candidate_scopes=candidate_scopes)
    return {
        "gate":"floor_finish_definition_vs_plan_occurrence_source_scope",
        "raw_finish_literal":source_finish_code,
        "original_source_mark_candidates":rows,
        "count_of_original_raw_words_not_quantity":len(rows),
        "authenticated_source_floor_finish_occurrences":0,
        "authenticated_floor_finish_area_m2":0,
    }


def audit_ceiling_material_mark_scope_candidates(
    page, *, source_material_literals:tuple[str,...],
    candidate_scopes:dict,
):
    """2. Distinguish schedule, legend, and in-plan ceiling code locations."""
    if (type(source_material_literals) is not tuple or not source_material_literals
            or len(set(source_material_literals))!=len(source_material_literals)):
        raise ValueError("distinct_raw_material_literals_required")
    rows=[]
    for code in source_material_literals:
        rows.extend(_scope_rows(page,original_literal=code,
                                candidate_scopes=candidate_scopes))
    return {
        "gate":"source_plan_ceiling_material_vs_legend_schedule_scope",
        "source_untrusted_ceiling_code_candidates":rows,
        "source_material_definition_trust_granted":False,
        "authentic_ceiling_zone_material_assignments":0,
        "authentic_ceiling_area_m2":0,
    }


def _native_source_stroke(page,source_id):
    match=re.fullmatch(r"d(0|[1-9][0-9]*)i(0|[1-9][0-9]*)",source_id) if isinstance(source_id,str) else None
    if not match:raise ValueError("exact_original_native_stroke_id_required")
    path,item=(int(x) for x in match.groups())
    drawings=page.get_drawings()
    if path>=len(drawings) or item>=len(drawings[path].get("items",())):
        raise ValueError("source_stroke_unavailable")
    d=drawings[path]
    it=d["items"][item]
    if it[0]!="l":raise ValueError("native_line_stroke_required")
    a,b=it[1:3]
    v=tuple(round(float(x),3) for x in (a.x,a.y,b.x,b.y))
    if not all(math.isfinite(x) for x in v):raise ValueError("finite_native_source_line_required")
    return {
        "original_native_id":source_id,
        "endpoints":v,
        "source_color":d.get("color"),
        "source_width":d.get("width"),
        "native_role_structural_wall_proven":False,
    }


def audit_coincident_native_stroke_ancestry(
    page, *, original_source_ids:tuple[str,...],
):
    """3. Three original paths over one location are not three physical walls."""
    if (type(original_source_ids) is not tuple or len(set(original_source_ids))!=len(original_source_ids)
            or not original_source_ids):raise ValueError("distinct_native_stroke_ids_required")
    parents=[_native_source_stroke(page,id) for id in original_source_ids]
    groups=defaultdict(list)
    for p in parents:
        x0,y0,x1,y1=p["endpoints"]
        canonical=tuple(sorted(((x0,y0),(x1,y1))))
        key=(canonical,repr(p["source_color"]),round(float(p["source_width"] or 0),3))
        groups[key].append(p["original_native_id"])
    return {
        "gate":"original_ink_path_multiplicity_vs_distinct_physical_wall",
        "all_source_line_parents":parents,
        "original_coincident_geometry_groups":[
            {"original_source_ids":ids,"one_geometrical_stroke_shape_not_wall_count":True}
            for ids in groups.values()
        ],
        "source_paths_are_distinct_walls_proven":False,
        "wall_count_published":0,
    }


def audit_shell_versus_room_face_source_conflict(
    page, *, shell_stroke_id:str, interior_stroke_ids:tuple[str,...],
    old_corner_native_xy:tuple[float,float]|None=None,
):
    """4. A nearby external shell must not silently replace room inner wall."""
    if not interior_stroke_ids or type(interior_stroke_ids) is not tuple:
        raise ValueError("independent_internal_face_candidates_required")
    shell=_native_source_stroke(page,shell_stroke_id)
    others=[_native_source_stroke(page,id) for id in interior_stroke_ids]
    if old_corner_native_xy is not None:
        if (type(old_corner_native_xy) is not tuple or len(old_corner_native_xy)!=2
                or not all(isinstance(x,(int,float)) and math.isfinite(x)
                           for x in old_corner_native_xy)):
            raise ValueError("valid_original_corner_coordinates_required")
    x0,y0,x1,y1=shell["endpoints"]
    shell_axis_x=x0 if x0==x1 else None
    distances=[]
    for row in others:
        ax,ay,bx,by=row["endpoints"]
        distances.append({
            "competing_original_interior_candidate_id":row["original_native_id"],
            "native_parallel_axis_displacement_pdf_pts":(
                abs(shell_axis_x-ax)
                if shell_axis_x is not None and ax==bx else None
            ),
            "source_wall_role_and_ring_owner_authenticated":False,
        })
    return {
        "gate":"external_building_shell_vs_interior_room_wall_owner",
        "original_shell_stroke_candidate":shell,
        "original_competing_room_stroke_candidates":others,
        "candidate_parallel_source_displacements":distances,
        "original_old_corner_candidate_native_xy":list(old_corner_native_xy)
            if old_corner_native_xy else None,
        "self_intersection_or_shell_alias_eliminated_by_source":False,
        "physical_closed_room_ring_granted":False,
        "new_room_area_m2":0,
    }


def audit_shared_figured_dimension_scope(
    page, *, figured_literal:str, room_name_literals:tuple[str,...],
    candidate_local_plan_scope,
):
    """5. A dimension spanning a Laundry/Airlock unit is not one room area."""
    box=_bbox(candidate_local_plan_scope)
    if box is None:raise ValueError("valid_local_plan_scope_required")
    if not room_name_literals or len(set(room_name_literals))!=len(room_name_literals):
        raise ValueError("distinct_room_label_candidates_required")
    words=_source_words(page)
    contained=[w for w in words if _contains(box,(
        (w["original_pdf_word_bbox_pts"][0]+w["original_pdf_word_bbox_pts"][2])/2,
        (w["original_pdf_word_bbox_pts"][1]+w["original_pdf_word_bbox_pts"][3])/2
    ))]
    numbers=[w for w in contained if w["source_literal_untrusted"]==figured_literal]
    labels={name:[w for w in contained if w["source_literal_untrusted"]==name]
            for name in room_name_literals}
    return {
        "gate":"figured_span_vs_multi_room_physical_source_owner",
        "original_raw_figure_word_candidates":numbers,
        "original_competing_room_words":labels,
        "one_room_only_dimension_owner_authenticated":False,
        "source_witness_endpoints_to_finished_faces_proven":False,
        "new_room_areas":0,
    }


def audit_cross_sheet_label_identity_candidates(
    original_pages:tuple, *, room_literal:str,
    source_candidate_scopes:tuple,
):
    """6. Same room word on two sheets is not authenticated wall topology."""
    if (type(original_pages) is not tuple or type(source_candidate_scopes) is not tuple
            or len(original_pages)!=len(source_candidate_scopes)
            or len(original_pages)<2):
        raise ValueError("independent_source_pages_and_scopes_required")
    receipts=[]
    for index,(page,scope) in enumerate(zip(original_pages,source_candidate_scopes)):
        box=_bbox(scope)
        if box is None:raise ValueError("valid_independent_source_scope_required")
        words=_source_words(page)
        hits=[w for w in words if w["source_literal_untrusted"]==room_literal
              and _contains(box,(
                  (w["original_pdf_word_bbox_pts"][0]+w["original_pdf_word_bbox_pts"][2])/2,
                  (w["original_pdf_word_bbox_pts"][1]+w["original_pdf_word_bbox_pts"][3])/2,
              ))]
        receipts.append({
            "input_independent_source_page_index":index,
            "original_same_label_word_candidates":hits,
            "source_page_viewport_and_room_ring_authenticated":False,
        })
    return {
        "gate":"two_independent_room_label_strings_not_physical_crossview_join",
        "room_name_literal_untrusted":room_literal,
        "independent_original_page_receipts":receipts,
        "same_label_word_in_all_scopes":all(
            r["original_same_label_word_candidates"] for r in receipts
        ),
        "unique_corresponding_physical_room_identity_granted":False,
        "cross_sheet_floor_or_ceiling_quantity_granted":False,
    }
