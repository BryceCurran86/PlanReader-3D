"""Native construction-sheet registration with retained competing line evidence.

Read-only source witness stage. No nearest-label registration, expected
quantity or source benchmark rows can elect a transform. Source-native
PDF line path identities survive every candidate translation. A matched
drafting stroke is NOT independently authenticated structural wall/face or
crosssheet canonical floor evidence; quantities never published.

All thresholds in this tool are caller-specified diagnostic *scope* limits,
not hidden prediction thresholds; production modules are not wired to it.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import math


def _native_bbox(raw):
    try:
        if isinstance(raw, (str,bytes)): return None
        a=tuple(float(x) for x in raw)
    except (TypeError, ValueError, OverflowError):
        return None
    return a if (len(a)==4 and all(math.isfinite(x) for x in a)
                 and a[0]<a[2] and a[1]<a[3]) else None


def _source_ink_lines(page, *, source_bbox, native_min_line_length_pt=50.,
                      max_source_paths=120000, max_selected_lines=5000):
    """Enumerate every eligible ORIGINAL path and item; never first-match."""
    bounds=_native_bbox(source_bbox)
    if bounds is None: raise ValueError("valid_source_page_candidate_bounds_required")
    if (type(native_min_line_length_pt) not in (int,float)
            or not math.isfinite(native_min_line_length_pt)
            or native_min_line_length_pt<=0):
        raise ValueError("valid_native_diagnostic_line_length_required")
    if (type(max_source_paths) is not int or max_source_paths<1
            or type(max_selected_lines) is not int or max_selected_lines<1):
        raise ValueError("bounded_source_ink_inventory_required")

    drawing_paths=page.get_drawings()
    if len(drawing_paths)>max_source_paths:
        return None
    lines=[]
    for pi, d in enumerate(drawing_paths):
        color=d.get("color")
        width=d.get("width")
        opacity=d.get("stroke_opacity",1.)
        try:
            style=(tuple(round(float(x),6) for x in color),
                   round(float(width),3),
                   round(float(opacity),6),
                   str(d.get("layer") or ""),
                   str(d.get("dashes") or ""))
            if not style[0] or not all(math.isfinite(x) for x in (*style[0],style[1],style[2])):
                continue
        except (TypeError,ValueError,OverflowError):
            continue
        for ii,it in enumerate(d.get("items",())):
            if not it or it[0]!="l":continue
            try:
                u,v=it[1:3]
                x,y,X,Y=(round(float(z),3) for z in (u.x,u.y,v.x,v.y))
            except (IndexError,ValueError,TypeError,OverflowError,AttributeError):
                continue
            if not all(math.isfinite(z) for z in (x,y,X,Y)):continue
            if not (bounds[0]<=x<=bounds[2] and bounds[0]<=X<=bounds[2]
                    and bounds[1]<=y<=bounds[3] and bounds[1]<=Y<=bounds[3]):
                continue
            if x==X and y!=Y:
                axis="native_vertical"
                length=abs(y-Y)
            elif y==Y and x!=X:
                axis="native_horizontal"
                length=abs(x-X)
            else:
                continue
            if length < native_min_line_length_pt:
                continue
            if len(lines)>=max_selected_lines:
                return None
            rows=tuple(sorted(((x,y),(X,Y))))
            lines.append({
                "source_path_item_id":f"d{pi}i{ii}",
                "native_axis":axis,
                "original_endpoints_pdf_pts":[list(rows[0]),list(rows[1])],
                "native_center_pdf_pts":[round((x+X)/2,3),round((y+Y)/2,3)],
                "native_length_pdf_pts":round(length,3),
                "original_ink_style":style,
                "physical_wall_role_authenticated":False,
            })
    return lines


def _style_key(row):
    return (row["native_axis"],row["native_length_pdf_pts"],
            row["original_ink_style"])


def _translation_pairs(left,right,*,max_offset_pdf_pt):
    if (type(max_offset_pdf_pt) not in (float,int)
            or type(max_offset_pdf_pt) is bool
            or not math.isfinite(max_offset_pdf_pt)
            or max_offset_pdf_pt<=0):
        raise ValueError("bounded_candidate_translation_required")
    indexed=defaultdict(list)
    for row in right:
        indexed[_style_key(row)].append(row)
    candidates=defaultdict(list)
    for a in left:
        for b in indexed.get(_style_key(a),()):
            dx=round(b["native_center_pdf_pts"][0]-a["native_center_pdf_pts"][0],3)
            dy=round(b["native_center_pdf_pts"][1]-a["native_center_pdf_pts"][1],3)
            if abs(dx)>max_offset_pdf_pt or abs(dy)>max_offset_pdf_pt:
                continue
            # Candidate translation must make BOTH original source endpoints
            # equal, not just length/center; this catches aliased linework.
            expected=[(round(v[0]+dx,3),round(v[1]+dy,3))
                      for v in a["original_endpoints_pdf_pts"]]
            observed=[tuple(v) for v in b["original_endpoints_pdf_pts"]]
            if expected != observed:
                continue
            candidates[(dx,dy)].append({
                "source_original_a_path_item_id":a["source_path_item_id"],
                "source_original_b_path_item_id":b["source_path_item_id"],
                "original_a_native_endpoints_pdf_pts":a["original_endpoints_pdf_pts"],
                "original_b_native_endpoints_pdf_pts":b["original_endpoints_pdf_pts"],
                "physical_wall_identity_proven":False,
            })
    return candidates


def audit_original_cross_sheet_source_translation(
    page_a, page_b, *, native_candidate_bbox_a,
    native_candidate_bbox_b, native_min_line_length_pt=50.,
    max_offset_pdf_pt=200., max_source_paths=120000,
    max_selected_lines=5000, max_matched_pairs=100000,
):
    if type(max_matched_pairs) is not int or max_matched_pairs<1:
        raise ValueError("bounded_candidate_pair_universe_required")
    a=_source_ink_lines(page_a,source_bbox=native_candidate_bbox_a,
        native_min_line_length_pt=native_min_line_length_pt,
        max_source_paths=max_source_paths,max_selected_lines=max_selected_lines)
    b=_source_ink_lines(page_b,source_bbox=native_candidate_bbox_b,
        native_min_line_length_pt=native_min_line_length_pt,
        max_source_paths=max_source_paths,max_selected_lines=max_selected_lines)
    if a is None or b is None:
        return {
            "status":"original_source_scope_cap_exceeded",
            "source_candidate_universe_complete":False,
            "newly_authenticated_physical_walls":0,
            "newly_authenticated_room_matches":0,
            "new_quantities":0,
        }
    candidate_map=_translation_pairs(a,b,max_offset_pdf_pt=max_offset_pdf_pt)
    if sum(len(x) for x in candidate_map.values())>max_matched_pairs:
        return {
            "status":"original_source_pair_scope_cap_exceeded",
            "source_candidate_universe_complete":False,
            "newly_authenticated_physical_walls":0,
            "newly_authenticated_room_matches":0,
            "new_quantities":0,
        }
    groups=[]
    for (dx,dy),pairs in candidate_map.items():
        ida=Counter(p["source_original_a_path_item_id"] for p in pairs)
        idb=Counter(p["source_original_b_path_item_id"] for p in pairs)
        unique=[p for p in pairs if ida[p["source_original_a_path_item_id"]]==1
                and idb[p["source_original_b_path_item_id"]]==1]
        groups.append({
            "original_source_translation_pdf_pts":[dx,dy],
            "all_original_candidate_pairs":sorted(pairs,key=lambda z:(
                z["source_original_a_path_item_id"],z["source_original_b_path_item_id"])),
            "original_source_pair_count":len(pairs),
            "unambiguous_local_source_ink_pairs":unique,
            "locally_unique_source_ink_pair_count":len(unique),
            "candidate_translation_geometry_positive":True,
            "global_source_registration_authority_granted":False,
            "structural_wall_identity_granted":False,
            "page7_to_page11_physical_room_join_granted":False,
        })
    groups.sort(key=lambda g:(-g["locally_unique_source_ink_pair_count"],
                              -g["original_source_pair_count"],
                              g["original_source_translation_pdf_pts"]))
    return {
        "status":"original_source_crosssheet_translation_candidate_census",
        "source_candidate_universe_complete":True,
        "source_a_native_line_count":len(a),
        "source_b_native_line_count":len(b),
        "all_competing_translation_groups":groups,
        "source_original_a_rows":a,
        "source_original_b_rows":b,
        "first_remaining_gate":"unique_structural_wall_ancestry_and_same_physical_floor_identity",
        "source_pdf_bytes_modified":False,
        "newly_authenticated_physical_walls":0,
        "newly_authenticated_room_matches":0,
        "new_floor_finish_quantities":0,
        "new_quantities":0,
    }
