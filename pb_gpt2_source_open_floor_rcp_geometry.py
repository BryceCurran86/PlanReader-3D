"""Original-native OPEN floor wall ink versus ONE virtual doorway chord.

This source-only verifier consumes an independently reissued original page
stroke graph. An unprinted chord is an ink-registration candidate, NOT a
physical wall, actual finished face, threshold, installed door or metric area.
The source visibility / W4 / cross-sheet issuers must authenticate separately.
"""
from __future__ import annotations

import math
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union

_OPEN = "source_open_floor_one_original_door_gap_candidate_only"
_BLOCKED = "source_open_floor_wall_ink_or_gap_unverified"


def audit_source_open_floor_native_ink_virtual_gap(
    graph: dict, *, original_source_edge_ids: tuple[str, ...],
    virtual_floor_vertices_pdf_pts: tuple[tuple[float,float], ...],
) -> dict:
    base = {
        "status": _BLOCKED,
        "first_failure": "original_open_floor_ink_or_virtual_ring_unverified",
        "original_source_floor_gap_endpoints_pdf_pts": (),
        "source_original_physical_wall_closure_authenticated": False,
        "source_doorway_threshold_authenticated": False,
        "source_metric_floor_or_ceiling_issued": False,
        "new_firm_quantities": 0,
    }
    if (type(graph) is not dict
            or graph.get("status") != "original_source_branches_or_open_ends"
            or graph.get("native_candidate_ring_count") != 0
            or graph.get("interior_stroke_intersections_and_overlaps")
            or type(original_source_edge_ids) is not tuple
            or not 3 <= len(original_source_edge_ids) <= 20000
            or len(set(original_source_edge_ids)) != len(original_source_edge_ids)
            or any(type(x) is not str or not x or x != x.strip()
                   for x in original_source_edge_ids)
            or graph.get("original_native_edge_ids")
                != tuple(sorted(original_source_edge_ids))):
        return base
    comps = graph.get("native_components")
    edges = graph.get("original_native_edges")
    if (type(comps) is not tuple or len(comps) != 1
            or type(edges) is not tuple
            or len(edges) != len(original_source_edge_ids)
            or type(comps[0]) is not dict
            or comps[0].get("source_simple_ring_candidate") is not None
            or comps[0].get("source_branch_coordinates_pdf_pts")
            or comps[0].get("source_edge_ids")
                != tuple(sorted(original_source_edge_ids))):
        return base
    degree_receipts = comps[0].get("native_endpoint_degrees")
    if (type(degree_receipts) is not tuple or not degree_receipts
            or len(degree_receipts) > 40000):
        return base
    endpoints = []
    for row in degree_receipts:
        if type(row) is not dict or type(row.get("degree")) is not int:
            return base
        degree = row["degree"]
        if degree not in (1,2):
            return base
        pt = row.get("point_pdf_pt")
        if (type(pt) not in (tuple,list) or len(pt)!=2
                or any(type(v) not in (int,float) or not math.isfinite(v)
                       for v in pt)):
            return base
        if degree == 1:
            endpoints.append(tuple(round(float(v),3) for v in pt))
    original_open_points=comps[0].get("source_open_endpoint_coordinates_pdf_pts")
    if (type(original_open_points) not in (tuple,list)
            or len(original_open_points)!=2
            or any(type(p) not in (tuple,list) or len(p)!=2
                   or any(type(v) not in (int,float) or not math.isfinite(v)
                          for v in p) for p in original_open_points)):
        return base
    if (len(endpoints) != 2 or endpoints[0] == endpoints[1]
            or {tuple(round(float(v),3) for v in p)
                for p in original_open_points} != set(endpoints)):
        return base
    if (type(virtual_floor_vertices_pdf_pts) not in (tuple,list)
            or not 4 <= len(virtual_floor_vertices_pdf_pts) <= 20001):
        return base
    try:
        for p in virtual_floor_vertices_pdf_pts:
            if (type(p) not in (tuple,list) or len(p)!=2
                    or any(type(v) not in (int,float) or not math.isfinite(v)
                           for v in p)):
                return base
        virtual = Polygon(virtual_floor_vertices_pdf_pts)
        if (not virtual.is_valid or virtual.is_empty or virtual.area <= 0
                or len(virtual.interiors) != 0):
            return base
        # Exactly the original source strokes, not a guessed subset.
        strokes = []
        names = set()
        for row in edges:
            if type(row) is not dict:
                return base
            ident = row.get("source_id")
            if (type(ident) is not str or ident not in original_source_edge_ids
                    or ident in names):
                return base
            names.add(ident)
            pts = row.get("endpoints_pdf_pts")
            if (type(pts) not in (tuple,list) or len(pts)!=2
                    or any(type(p) not in (tuple,list) or len(p)!=2
                           or any(type(v) not in (int,float) or not math.isfinite(v)
                                  for v in p) for p in pts)):
                return base
            ls=LineString(tuple(tuple(round(float(x),3) for x in p) for p in pts))
            if (ls.is_empty or ls.length<=0 or not virtual.boundary.covers(ls)):
                return base
            strokes.append(ls)
        if names != set(original_source_edge_ids):
            return base
        gap = LineString(endpoints)
        if (gap.length <= 0 or not virtual.boundary.covers(gap)):
            return base
        # The proposed closed boundary can differ from the ORIGINAL open
        # strokes by precisely ONE unprinted straight chord, and nothing else.
        missing = virtual.boundary.difference(unary_union(strokes))
        if (not missing.equals(gap)
                or missing.length <= 0
                or abs(missing.length-gap.length) > 1e-6):
            return base
    except (TypeError,ValueError,OverflowError):
        return base
    return {
        **base,
        "status": _OPEN,
        "first_failure":"sealed_W4_physical_face_and_source_door_width_still_required",
        "original_source_floor_gap_endpoints_pdf_pts":tuple(sorted(endpoints)),
    }
