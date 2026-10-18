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
