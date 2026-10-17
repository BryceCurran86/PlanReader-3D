"""Original native-PDF room-side graph; diagnostic only, never W4 authority.

Takes exact caller/source-issued primitive IDs, not nearest labels, grid cells,
expected BOQ or screen geometry. Requires one SHA-verified page and returns
all structural candidates/negative evidence without electing a room.
The native PDF-point area is NOT a metric surface or finished floor area.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import math
import re

import fitz
from shapely.geometry import LineString, Polygon

from tools.diag_original_room_four_edge_source_ink_shadow import _line

_NATIVE_ID = re.compile(r"^d(0|[1-9][0-9]*)i(0|[1-9][0-9]*)$")


def _native_page(source: bytes, source_sha256: str, page_1_based: int):
    if (type(source) is not bytes or type(source_sha256) is not str
            or hashlib.sha256(source).hexdigest() != source_sha256):
        raise ValueError("original_graph_source_sha_mismatch")
    doc = fitz.open(stream=source, filetype="pdf")
    if type(page_1_based) is not int or not 1 <= page_1_based <= len(doc):
        doc.close()
        raise ValueError("original_graph_source_page_invalid")
    return doc, doc[page_1_based - 1]


def _segments_from_source(page, source_ids: tuple[str, ...], *, max_paths: int):
    if (type(source_ids) is not tuple or len(source_ids)<2
            or len(source_ids)>max_paths or len(set(source_ids))!=len(source_ids)
            or any(type(s) is not str or _NATIVE_ID.fullmatch(s) is None
                   for s in source_ids)):
        raise ValueError("original_graph_bounded_unique_source_ids_required")
    drawings=page.get_drawings()
    if len(drawings)>max_paths:
        raise ValueError("original_graph_native_path_safety_cap")
    edges={}
    for name in source_ids:
        record=_line(drawings, name)
        a,b=record["ends"]
        if a==b or (a[0]!=b[0] and a[1]!=b[1]):
            raise ValueError("original_graph_nonorthogonal_or_zero_source_edge")
        edges[name]={"ends":(tuple(a),tuple(b)),
                     "source":record,
                     "length_pdf_pt":abs(b[0]-a[0])+abs(b[1]-a[1])}
    return edges


def _intersection_issues(edges):
    """Find T-junctions, real crosses, coincident duplicates, and overlaps.

    End-to-end meeting is permitted, but a crossing at a stroke interior
    is NOT split or silently substituted for a PDF source path endpoint.
    """
    issues=[]
    items=list(sorted(edges.items()))
    for i, (a_id,a) in enumerate(items):
        la=LineString(a["ends"])
        for b_id,b in items[i+1:]:
            lb=LineString(b["ends"])
            if not la.intersects(lb):
                continue
            shared=set(a["ends"]) & set(b["ends"])
            collision=la.intersection(lb)
            if collision.geom_type=="Point" and tuple(collision.coords[0]) in shared:
                continue
            issues.append({"first_source_id":a_id,"second_source_id":b_id,
                           "native_intersection_kind":collision.geom_type,
                           "first_failure":"interior_or_overlapping_source_strokes"})
    return issues


def _components(edges):
    vertices=defaultdict(set)
    for name,edge in edges.items():
        for point in edge["ends"]:
            vertices[point].add(name)
    components=[]
    visited=set()
    for start in sorted(edges):
        if start in visited:continue
        members=set()
        queue=[start]
        while queue:
            current=queue.pop()
            if current in visited:continue
            visited.add(current)
            members.add(current)
            for vertex in edges[current]["ends"]:
                for adjacent in vertices[vertex]:
                    if adjacent not in visited:
                        queue.append(adjacent)
        nodes=defaultdict(list)
        for id in members:
            for end in edges[id]["ends"]:
                nodes[end].append(id)
        components.append({"source_ids":tuple(sorted(members)),
                           "nodes":{pt:tuple(sorted(ids)) for pt,ids in nodes.items()}})
    return tuple(sorted(components,key=lambda c:c["source_ids"]))


def _ring_from_component(component,edges):
    """Recover a ring only from an exact degree-two connected path graph."""
    nodes=component["nodes"]
    if not nodes or any(len(n)!=2 for n in nodes.values()):
        return None
    start=min(nodes)
    ring=[start]
    prev=None
    at=start
    for _ in component["source_ids"]:
        choices=[e for e in nodes[at] if e!=prev]
        if len(choices)!=1 and prev is not None:
            return None
        selected=sorted(choices)[0]
        left,right=edges[selected]["ends"]
        next_pt=right if left==at else left
        if next_pt==start:
            if len(ring)!=len(component["source_ids"]):
                return None
            break
        if next_pt in ring:return None
        ring.append(next_pt)
        prev,at=selected,next_pt
    else:
        return None
    polygon=Polygon(ring)
    if not polygon.is_valid or polygon.is_empty or polygon.area<=0:
        return None
    return {"vertices_pdf_pts":tuple(ring),
            "native_area_pdf_pt2":float(polygon.area),
            "native_perimeter_pdf_pt":float(polygon.length),
            "source_edge_ids":component["source_ids"]}


def _collinear_open_gap_pairs(open_points):
    """All positive on-axis endpoint gaps; never select nearest or bridge."""
    gaps=[]
    for index,p in enumerate(open_points):
        for q in open_points[index+1:]:
            if p==q:continue
            if p[0]==q[0] or p[1]==q[1]:
                gaps.append({"native_gap_start_pdf_pt":list(min(p,q)),
                             "native_gap_end_pdf_pt":list(max(p,q)),
                             "native_gap_distance_pdf_pt":float(
                                 abs(p[0]-q[0])+abs(p[1]-q[1])),
                             "source_gap_filled_by_imputation":False,
                             "physical_door_opening_issued":False})
    return tuple(gaps)


def audit_original_room_edge_graph(
    original_pdf: bytes, *, source_sha256: str,
    page_1_based: int, source_edge_ids: tuple[str, ...],
    max_native_paths: int=120000,
) -> dict:
    """Issue independent source graph and complete failure classifications.

    A simple closed ink loop is only a candidate. It cannot establish
    wall thickness, structural identity, finished face, room name, unit scale,
    FT2/FT3 mark ownership, ceiling finish or quantity.
    """
    if type(max_native_paths) is not int or not 2<=max_native_paths<=120000:
        raise ValueError("original_graph_max_paths_invalid")
    doc,page=_native_page(original_pdf,source_sha256,page_1_based)
    try:
        edges=_segments_from_source(page,source_edge_ids,max_paths=max_native_paths)
        conflicts=_intersection_issues(edges)
        comps=_components(edges)
        details=[]
        for comp in comps:
            nodes=comp["nodes"]
            open_points=sorted(pt for pt,owners in nodes.items() if len(owners)==1)
            branches=sorted(pt for pt,owners in nodes.items() if len(owners)>2)
            ring=None if conflicts else _ring_from_component(comp,edges)
            details.append({
                "source_edge_ids":comp["source_ids"],
                "native_endpoint_degrees":tuple(
                    {"point_pdf_pt":list(pt),"degree":len(owners),
                     "original_source_edge_ids":list(owners)}
                    for pt,owners in sorted(nodes.items())
                ),
                "source_open_endpoint_coordinates_pdf_pts":tuple(
                    list(pt) for pt in open_points),
                "source_branch_coordinates_pdf_pts":tuple(
                    list(pt) for pt in branches),
                "native_unfilled_collinear_gap_candidates":_collinear_open_gap_pairs(
                    open_points),
                "source_simple_ring_candidate":ring,
                "structural_wall_roles_authenticated":False,
                "source_physical_room_closed":False,
                "candidate_pdf_point_area_not_metric_m2":True,
            })
        rings=sum(x["source_simple_ring_candidate"] is not None for x in details)
        status=("original_native_stroke_intersection_competition" if conflicts
                else "original_source_branches_or_open_ends" if any(
                    x["source_open_endpoint_coordinates_pdf_pts"] or
                    x["source_branch_coordinates_pdf_pts"] for x in details)
                else "original_closed_ink_ring_candidates_only" if rings
                else "original_source_room_graph_unresolved")
        return {
            "status":status,
            "source_sha256":source_sha256,
            "page_1_based":page_1_based,
            "original_native_edge_ids":tuple(sorted(source_edge_ids)),
            # Keep every literal path/item endpoint in a typed, deterministic
            # receipt so a second physical doorway stage can reconstruct the
            # exact printed (open) path, not guess a closure from the bbox.
            "original_native_edges":tuple(
                {"source_id":ident,
                 "endpoints_pdf_pts":edges[ident]["ends"],
                 "source_ink_length_pdf_pt":edges[ident]["length_pdf_pt"]}
                for ident in sorted(edges)
            ),
            "native_components":tuple(details),
            "interior_stroke_intersections_and_overlaps":tuple(conflicts),
            "native_candidate_ring_count":rings,
            "source_physical_room_identity_issued":False,
            "original_source_structural_wall_issuer_granted":False,
            "source_room_metric_area_issued":False,
            "source_floor_finish_area_issued":False,
            "new_firm_quantities":0,
        }
    finally:
        doc.close()
