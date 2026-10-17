"""Source-root-bound doorway interruption of an otherwise open room ink ring.

No source wall is fabricated through an actual door. The hypothetical path
closing its gap is marked VIRTUAL for *geometry diagnostics only*, not W4
structural proof, room area, door count, finished floor or customer export.
"""
from __future__ import annotations
import hashlib
import math

import fitz
from shapely.geometry import Polygon

from tools.diag_original_room_four_edge_source_ink_shadow import _line


def audit_original_doorway_ring_candidate(
    original_pdf_bytes: bytes, *, expected_sha256: str,
    original_page_1_based: int, source_room_graph: dict,
    original_jamb_source_receipt: dict,
) -> dict:
    base={
        "status":"original_doorway_room_ring_unavailable",
        "first_failure":"independent_source_wall_doorway_binding_unavailable",
        "source_virtual_door_connector_is_structural_wall":False,
        "source_room_physical_identity_proved":False,
        "source_metric_area_issued":False,
        "source_finished_floor_area_issued":False,
        "new_firm_quantities":0,
    }
    if (type(original_pdf_bytes) is not bytes or type(expected_sha256) is not str
            or hashlib.sha256(original_pdf_bytes).hexdigest()!=expected_sha256):
        raise ValueError("source_root_document_sha_mismatch")
    if (type(original_page_1_based) is not int or original_page_1_based<1
            or type(source_room_graph) is not dict or
            source_room_graph.get("source_sha256")!=expected_sha256 or
            source_room_graph.get("page_1_based")!=original_page_1_based):
        return {**base,"first_failure":"doorway_graph_original_source_page_or_root_mismatch"}
    witness=original_jamb_source_receipt
    if (type(witness) is not dict or
            witness.get("status")!="exact_original_native_jamb_endpoint_chain_candidate"
            or witness.get("native_ink_contact_proved") is not True or
            witness.get("original_pdf_page_index_zero_based")!=original_page_1_based-1):
        return {**base,"first_failure":"original_native_jamb_contact_not_proved"}
    if (source_room_graph.get("interior_stroke_intersections_and_overlaps")
            or len(source_room_graph.get("native_components",()))!=1):
        return {**base,"first_failure":"competing_source_room_perimeter_or_crossing"}
    component=source_room_graph["native_components"][0]
    if component.get("source_simple_ring_candidate") is not None:
        return {**base,"first_failure":"native_room_is_already_closed_without_door_gap"}
    degrees=component["native_endpoint_degrees"]
    openings=[tuple(a["point_pdf_pt"]) for a in degrees if a["degree"]==1]
    if len(openings)!=2 or any(a["degree"]>2 for a in degrees):
        return {**base,"first_failure":"source_room_has_more_than_one_unclosed_gap"}
    if set(witness["original_primitive_paths"][role]["original_source_primitive_id"]
           for role in ("left_wall","right_wall")) - set(
               source_room_graph["original_native_edge_ids"]):
        return {**base,"first_failure":"original_wall_fragment_not_in_room_chain"}
    axis=witness.get("source_native_wall_run_axis")
    ordinate=witness.get("source_original_wall_axis_pdf_pt")
    interval=witness.get("source_native_unbridged_wall_gap_pdf_pts")
    if (axis not in {"native_x","native_y"} or
            type(interval) not in (tuple,list) or len(interval)!=2
            or any(type(v) not in (int,float) or not math.isfinite(v) for v in interval)
            or type(ordinate) not in (int,float) or not math.isfinite(ordinate)):
        return {**base,"first_failure":"original_jamb_gap_axis_unavailable"}
    expected=(
        {(interval[0],ordinate),(interval[1],ordinate)}
        if axis=="native_x" else
        {(ordinate,interval[0]),(ordinate,interval[1])}
    )
    if set(openings)!=expected:
        return {**base,"first_failure":"native_jamb_gap_not_room_endpoint_pair"}

    # Re-read all FOUR doorway primitives against the actual SHA-pinned PDF.
    # A page-local dNNiMM ID is not a document identity by itself.
    with fitz.open(stream=original_pdf_bytes,filetype="pdf") as doc:
        if original_page_1_based>len(doc):
            return {**base,"first_failure":"original_page_outside_document"}
        page=doc[original_page_1_based-1]
        drawings=page.get_drawings()
        actual_roles={}
        for role in ("left_wall","right_wall","left_jamb","right_jamb"):
            row=witness["original_primitive_paths"].get(role)
            if type(row) is not dict:
                return {**base,"first_failure":"original_doorway_source_role_unavailable"}
            ident=row.get("original_source_primitive_id")
            original=_line(drawings,ident)
            actual=set(tuple(v) for v in original["ends"])
            ends=row.get("original_native_endpoints_pdf_pts")
            if type(ends) not in (tuple,list) or len(ends)!=4:
                return {**base,"first_failure":"native_jamb_receipt_source_root_conflict"}
            claimed=set(tuple(v) for v in (ends[:2],ends[2:]))
            if (actual!=claimed or not original.get("original_source_continuous_painted_stroke")
                    or original["source_color"]!=(0.,0.,0.)):
                return {**base,"first_failure":"native_jamb_receipt_source_root_conflict"}
            actual_roles[role]=original
        walls=[actual_roles[role] for role in ("left_wall","right_wall")]
        jambs=[actual_roles[role] for role in ("left_jamb","right_jamb")]
        if (walls[0]["stroke_width"]!=walls[1]["stroke_width"]
                or jambs[0]["stroke_width"]!=jambs[1]["stroke_width"]
                or walls[0]["stroke_opacity"]!=walls[1]["stroke_opacity"]
                or jambs[0]["stroke_opacity"]!=jambs[1]["stroke_opacity"]):
            return {**base,"first_failure":"original_doorway_paint_family_conflict"}
        for i, wall in enumerate(walls):
            (a,b)=wall["ends"]
            if axis=="native_x":
                if a[1]!=ordinate or b[1]!=ordinate or (
                        (max(a[0],b[0]) if i==0 else min(a[0],b[0]))!=interval[i]):
                    return {**base,"first_failure":"original_doorway_wall_endpoint_conflict"}
            else:
                if a[0]!=ordinate or b[0]!=ordinate or (
                        (max(a[1],b[1]) if i==0 else min(a[1],b[1]))!=interval[i]):
                    return {**base,"first_failure":"original_doorway_wall_endpoint_conflict"}
        cross_intervals=[]
        for i, jamb in enumerate(jambs):
            a,b=jamb["ends"]
            if axis=="native_x":
                if a[0]!=interval[i] or b[0]!=interval[i]:
                    return {**base,"first_failure":"original_doorway_jamb_not_perpendicular"}
                cross=(a[1],b[1])
            else:
                if a[1]!=interval[i] or b[1]!=interval[i]:
                    return {**base,"first_failure":"original_doorway_jamb_not_perpendicular"}
                cross=(a[0],b[0])
            cross_intervals.append(tuple(sorted(cross)))
        if (cross_intervals[0]!=cross_intervals[1]
                or ordinate not in cross_intervals[0]
                or cross_intervals[0][0]==cross_intervals[0][1]):
            return {**base,"first_failure":"original_doorway_jamb_crosswall_role_conflict"}
    edges={e["source_id"]:tuple(tuple(p) for p in e["endpoints_pdf_pts"])
           for e in source_room_graph["original_native_edges"]}
    adjacent={}
    for ident,(p,q) in edges.items():
        adjacent.setdefault(p,[]).append((ident,q))
        adjacent.setdefault(q,[]).append((ident,p))
    start=min(openings)
    finish=max(openings)
    chain=[start]
    used=set()
    at=start
    while at!=finish:
        choices=[(name,nxt) for name,nxt in adjacent[at] if name not in used]
        if len(choices)!=1:
            return {**base,"first_failure":"native_perimeter_nonunique_path"}
        ident,nxt=choices[0]
        used.add(ident)
        chain.append(nxt)
        at=nxt
        if len(chain)>len(edges)+1 or (at in chain[:-1]):
            return {**base,"first_failure":"native_perimeter_self_touching"}
    if len(used)!=len(edges) or len(chain)<4:
        return {**base,"first_failure":"original_room_perimeter_incomplete"}
    polygon=Polygon(chain)
    if not polygon.is_valid or polygon.area<=0:
        return {**base,"first_failure":"virtual_door_gap_floor_ring_not_simple"}
    return {
        **base,
        "status":"source_jamb_bound_open_door_perimeter_candidate_only",
        "first_failure":"W4_physical_room_issuer_and_face_area_measurement",
        "original_source_sha256":expected_sha256,
        "original_page_1_based":original_page_1_based,
        "original_source_perimeter_side_ids":tuple(sorted(used)),
        "source_virtual_door_connector_pdf_pts":[list(finish),list(start)],
        "source_open_door_native_gap_axis":axis,
        "source_ink_ring_with_explicit_virtual_door_gap_pdf_pts":
            tuple(chain),
        "source_only_native_polygon_area_pdf_pt2_not_m2":polygon.area,
        "source_jamb_roles_same_sha_rechecked":True,
        "source_wall_and_jamb_geometry_independently_recomputed":True,
    }
