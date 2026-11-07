"""SHA-pinned native room-door gap ancestry across independent original sheets.

A four-wall room envelope can contain short printed wall stubs at its real
doorway. They are actual source primitives, NOT imputed structural walls.
This adapter compares every source stroke and each remaining gap across two
original pages. A 0.24pt contradiction MUST NOT be snapped away or upgraded
to W4 physical room/finish/ceiling identity.

All coordinates are original PDF points, never mm/m2. Shadow only.
"""
from __future__ import annotations
import hashlib
import math

from tools.diag_gpt2_source_room_graph_shadow import audit_original_room_edge_graph


def _the_one_open_original_room_component(graph):
    if (type(graph) is not dict or graph.get("status")!=
            "original_source_branches_or_open_ends" or
            graph.get("interior_stroke_intersections_and_overlaps") or
            len(graph.get("native_components",()))!=1):
        return None
    comp=graph["native_components"][0]
    rows=comp["native_endpoint_degrees"]
    ends=tuple(sorted(tuple(x["point_pdf_pt"]) for x in rows if x["degree"]==1))
    if (len(ends)!=2 or not (ends[0][0]==ends[1][0] or ends[0][1]==ends[1][1])
            or any(x["degree"]!=2 for x in rows if x["degree"]!=1)):
        return None
    return ends


def _independently_reissued_exact_native_stroke_pairs(
    floor_graph: dict, other_graph: dict, *, translation: tuple[float,float],
) -> tuple[tuple[dict,...], tuple[str,...], bool]:
    """Reconcile full source strokes, not physical wall/finished-face roles.

    Source-positive matching long faces should survive an unrelated 0.24pt
    door-cap dispute, but repeated coincident source ink is never elected as
    one source owner and the comparison does not close an open doorway.
    """
    def source_index(graph, dx, dy):
        rows=graph.get("original_native_edges")
        if type(rows) is not tuple or not 2<=len(rows)<=120000:
            raise ValueError("original_native_stroke_inventory_missing")
        by_line={}
        seen=set()
        for row in rows:
            if type(row) is not dict:
                raise ValueError("source_stroke_receipt_invalid")
            ident=row.get("source_id")
            pts=row.get("endpoints_pdf_pts")
            length=row.get("source_ink_length_pdf_pt")
            if (type(ident) is not str or not ident or ident in seen
                    or type(pts) not in (list,tuple) or len(pts)!=2
                    or type(length) not in (int,float)
                    or not math.isfinite(length) or length<=0):
                raise ValueError("source_stroke_receipt_invalid")
            seen.add(ident)
            points=[]
            for point in pts:
                if (type(point) not in (tuple,list) or len(point)!=2
                        or any(type(v) not in (int,float)
                               or not math.isfinite(v) for v in point)):
                    raise ValueError("source_stroke_endpoint_invalid")
                points.append((
                    round(float(point[0])+dx,3),
                    round(float(point[1])+dy,3),
                ))
            if points[0]==points[1]:
                raise ValueError("source_zero_length_stroke_invalid")
            # The native stroke issuer publishes a length computed from
            # exact rounded source endpoints. A forged/rewritten line must
            # not keep the original source ID yet move the geometry.
            original=tuple(
                (float(point[0]),float(point[1])) for point in pts
            )
            native_length=math.dist(*original)
            if abs(native_length-float(length))>0.001:
                raise ValueError("source_stroke_length_receipt_mismatch")
            key=tuple(sorted(points))
            by_line.setdefault(key,[]).append(ident)
        roster=graph.get("original_native_edge_ids")
        if (type(roster) is not tuple
                or len(roster)!=len(seen)
                or set(roster)!=seen):
            raise ValueError("original_complete_source_stroke_roster_missing")
        return by_line
    try:
        if (type(translation) is not tuple or len(translation)!=2
                or any(type(v) not in (float,int) or not math.isfinite(v)
                       for v in translation)):
            raise ValueError("typed_original_translation_required")
        dx,dy=translation
        a=source_index(floor_graph,dx,dy)
        b=source_index(other_graph,0.0,0.0)
    except (ValueError,TypeError,KeyError,OverflowError):
        return (),("original_source_stroke_inventory_invalid",),False
    pairs=[]
    rivals=[]
    for geometry in sorted(set(a)|set(b)):
        floor_ids=a.get(geometry,())
        second_ids=b.get(geometry,())
        if len(floor_ids)>1 or len(second_ids)>1:
            rivals.extend((*floor_ids,*second_ids))
            continue
        if len(floor_ids)==1 and len(second_ids)==1:
            pairs.append({
                "original_floor_source_edge_id":floor_ids[0],
                "original_second_source_edge_id":second_ids[0],
                "source_exact_native_stroke_geometry_only":True,
                "physical_wall_face_issuer_granted":False,
            })
    return tuple(pairs),tuple(sorted(set(rivals))),not bool(rivals)


def audit_gpt2_original_room_doorway_ancestry_pair(
    original_pdf_bytes: bytes, *, expected_sha256: str,
    floor_page_1_based: int, second_page_1_based: int,
    original_floor_source_edge_ids: tuple[str,...],
    original_second_source_edge_ids: tuple[str,...],
    original_translation_pdf_pts: tuple[float,float],
) -> dict:
    """Exact original 5+ stroke room comparison, with typed source rivals."""
    if (type(original_pdf_bytes) is not bytes
            or hashlib.sha256(original_pdf_bytes).hexdigest()!=expected_sha256):
        raise ValueError("original_source_sha_mismatch")
    if (type(original_translation_pdf_pts) is not tuple
            or len(original_translation_pdf_pts)!=2
            or any(type(v) not in (int,float) or not math.isfinite(v)
                   for v in original_translation_pdf_pts)):
        raise ValueError("original_source_translation_invalid")
    if floor_page_1_based==second_page_1_based:
        raise ValueError("two_distinct_original_plan_pages_required")
    floor=audit_original_room_edge_graph(
        original_pdf_bytes,source_sha256=expected_sha256,
        page_1_based=floor_page_1_based,
        source_edge_ids=original_floor_source_edge_ids,
    )
    other=audit_original_room_edge_graph(
        original_pdf_bytes,source_sha256=expected_sha256,
        page_1_based=second_page_1_based,
        source_edge_ids=original_second_source_edge_ids,
    )
    first_gap=_the_one_open_original_room_component(floor)
    second_gap=_the_one_open_original_room_component(other)
    output={
        "status":"original_doorway_ancestry_unresolved",
        "first_unclosed_gate":"source_both_room_door_endpoints_not_unique",
        "original_source_sha256":expected_sha256,
        "original_floor_page":floor_page_1_based,
        "original_other_plan_page":second_page_1_based,
        "floor_source_graph":floor,
        "second_plan_source_graph":other,
        "original_translation_pdf_pts":list(original_translation_pdf_pts),
        "source_cross_sheet_physical_wall_issuer_granted":False,
        "source_room_finished_face_binding_granted":False,
        "source_virtual_closing_wall_painted":False,
        "new_firm_quantities":0,
    }
    if first_gap is None or second_gap is None:
        return output
    dx,dy=original_translation_pdf_pts
    translate=lambda point:(round(point[0]+dx,3),round(point[1]+dy,3))
    first_set={translate(p) for p in first_gap}
    other_set=set(second_gap)
    # Preserve BOTH endpoint sets and the precise residual differences. No
    # W2 2.5pt global snap, 0.24pt correction, nearest choice, or guessing.
    source_pairs=tuple(sorted(
        (p,translate(p)) for p in first_gap
    ))
    endpoint_rivals=tuple({
        "source_floor_endpoint_pdf_pts":list(p),
        "source_transferred_endpoint_pdf_pts":list(q),
        "second_original_endpoint_pdf_pts":list(second_gap[i]),
        "coordinate_residual_pdf_pts":[
            round(second_gap[i][0]-q[0],3),
            round(second_gap[i][1]-q[1],3),
        ],
    } for i,(p,q) in enumerate(source_pairs))
    output.update({
        "original_floor_unclosed_gap_endpoints_pdf_pts":[list(x) for x in first_gap],
        "original_second_unclosed_gap_endpoints_pdf_pts":[list(x) for x in second_gap],
        "original_door_gap_length_floor_pdf_pts":round(
            math.dist(*first_gap),3),
        "original_door_gap_length_second_pdf_pts":round(
            math.dist(*second_gap),3),
        "original_gap_endpoint_rivals":endpoint_rivals,
    })
    floor_lines={
        tuple(sorted(translate(tuple(p)) for p in edge["endpoints_pdf_pts"]))
        for edge in floor["original_native_edges"]
    }
    other_lines={
        tuple(sorted(tuple(p) for p in edge["endpoints_pdf_pts"]))
        for edge in other["original_native_edges"]
    }
    output["original_unmatched_second_side_ink_pdf_pts"]=tuple(
        sorted(other_lines-floor_lines))
    output["original_unmatched_transferred_floor_ink_pdf_pts"]=tuple(
        sorted(floor_lines-other_lines))
    exact_pairs,duplicate_source_ink,unambiguous=(
        _independently_reissued_exact_native_stroke_pairs(
            floor,other,translation=original_translation_pdf_pts,
        )
    )
    output.update({
        "original_exact_native_stroke_source_pairs":exact_pairs,
        "original_duplicate_painted_stroke_source_rivals":duplicate_source_ink,
        "original_exact_stroke_pair_universe_unambiguous":unambiguous,
        "source_exact_stroke_matches_do_not_authenticate_wall_roles":True,
        "source_W4_room_or_doorway_threshold_issuer_granted":False,
    })
    if first_set!=other_set:
        output["status"]="original_doorway_source_endpoint_rival_conflict"
        output["first_unclosed_gate"]="original_short_wall_stub_disagrees_across_sheets"
    elif floor_lines!=other_lines:
        output["status"]="original_doorway_source_stroke_ancestry_conflict"
        output["first_unclosed_gate"]="original_source_wall_fragment_geometry_differs"
    else:
        output["status"]="original_doorway_all_printed_wall_strokes_match_candidate"
        output["first_unclosed_gate"]="independent_W3_W4_structural_wall_and_jamb_roles"
    return output
