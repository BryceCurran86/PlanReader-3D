"""W2 experimental exact source-owned straight-through junction anchoring.

The existing W2 endpoint snap is unchanged. This pass MAY restore a snapped
junction coordinate to an original positive source intersection when two
opposing local edge fragments have EXACT shared raw endpoint, identical sole
primitive ancestor and independently validated contiguous parent-source
coverage through that point. It keeps the branch, every edge, source lineage,
existing snap threshold, and source gaps intact. It does not decide physical
wall sameness, instantiate hosts, or supply QuantityEvidence.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Mapping

from pb_wall_room_topology_primitive_lineage import LINEAGE_KEY

# Arithmetic equality of already split source endpoints, never a construction
# snap/measurement tolerance. The original splitter rounds to 8 decimals.
_COORD_EPS = 1e-7
_SOURCE_ON_SEGMENT_EPS = 1e-5


def _point_on_parent(p, parent, *, interior=False):
    try:
        raw = tuple(float(v) for v in parent)
        p = tuple(float(v) for v in p)
    except (TypeError, ValueError, OverflowError):
        return False
    if (len(raw) != 4 or len(p) != 2 or
            not all(math.isfinite(v) for v in (*raw, *p))):
        return False
    dx, dy = raw[2]-raw[0], raw[3]-raw[1]
    length = math.hypot(dx, dy)
    if length <= _COORD_EPS:
        return False
    along = ((p[0]-raw[0])*dx + (p[1]-raw[1])*dy) / length
    off = abs((p[0]-raw[0])*dy - (p[1]-raw[1])*dx) / length
    if off > _SOURCE_ON_SEGMENT_EPS:
        return False
    if interior:
        return _SOURCE_ON_SEGMENT_EPS < along < length-_SOURCE_ON_SEGMENT_EPS
    return -_SOURCE_ON_SEGMENT_EPS <= along <= length+_SOURCE_ON_SEGMENT_EPS


def _positive_parent(edge, primitive_id, junction, far):
    lineage = edge.get(LINEAGE_KEY) or {}
    ids = lineage.get("source_primitive_ids") or ()
    if tuple(ids) != (primitive_id,):
        return False
    matching = [
        record for record in lineage.get("source_records") or ()
        if isinstance(record, Mapping)
        and record.get("id") == primitive_id
        and record.get("page_coords_present") is True
    ]
    if len(matching) != 1:
        return False
    parent = tuple(matching[0].get(k) for k in ("x1", "y1", "x2", "y2"))
    return (_point_on_parent(junction, parent, interior=True)
            and _point_on_parent(far, parent))


def reanchor_exact_source_through_junctions(graph, *, tolerance_pt):
    """Return a copied graph with only unambiguously exact original anchors.

    Does not alter edge adjacency, split geometry, primitive ancestry,
    opening existence, source measurements, or original source gap coverage.
    Multiple opposing through-pairs demanding different anchor coordinates
    are explicitly left at the original snapped centroid.
    """
    if not isinstance(tolerance_pt, (int, float)) or not math.isfinite(tolerance_pt):
        raise ValueError("invalid existing W2 snap tolerance")
    if tolerance_pt <= 0:
        return graph
    nodes = [dict(row) for row in graph["nodes"]]
    edges = graph["edges"]
    incidence = graph["adjacency"]
    anchors = []
    for node in nodes:
        node_id = node["id"]
        incident = incidence.get(node_id, ())
        if len(incident) < 3:
            continue
        npoint = (float(node["x"]), float(node["y"]))
        if not all(math.isfinite(v) for v in npoint):
            continue
        by_source = defaultdict(list)
        raw_endpoints = []
        valid = True
        for edge_idx in incident:
            edge = edges[edge_idx]
            if edge.get("a") == node_id:
                p=(edge["x1"],edge["y1"])
                far=(edge["x2"],edge["y2"])
            elif edge.get("b") == node_id:
                p=(edge["x2"],edge["y2"])
                far=(edge["x1"],edge["y1"])
            else:
                valid=False
                break
            try:
                p=tuple(float(v) for v in p)
                far=tuple(float(v) for v in far)
            except (TypeError, ValueError, OverflowError):
                valid=False
                break
            if (not all(math.isfinite(v) for v in (*p,*far))
                    or math.dist(p,far)<=_COORD_EPS):
                valid=False
                break
            raw_endpoints.append(p)
            ids=(edge.get(LINEAGE_KEY) or {}).get("source_primitive_ids") or ()
            if len(ids)==1 and isinstance(ids[0],str) and ids[0]:
                by_source[ids[0]].append((edge,p,far))
        if not valid:
            continue
        candidate_points=set()
        for primitive_id, members in by_source.items():
            for i,left in enumerate(members):
                _,p,a=left
                for right in members[i+1:]:
                    _,q,b=right
                    if math.dist(p,q)>_COORD_EPS:
                        continue
                    va=(a[0]-p[0],a[1]-p[1])
                    vb=(b[0]-q[0],b[1]-q[1])
                    length=math.hypot(*va)*math.hypot(*vb)
                    if length<=_COORD_EPS:
                        continue
                    if (va[0]*vb[0]+va[1]*vb[1]>=0
                            or abs(va[0]*vb[1]-va[1]*vb[0])>_COORD_EPS*length):
                        continue
                    if not (_positive_parent(left[0],primitive_id,p,a)
                            and _positive_parent(right[0],primitive_id,q,b)):
                        continue
                    candidate_points.add((round(p[0],8),round(p[1],8)))
        if len(candidate_points)!=1:
            continue
        point=next(iter(candidate_points))
        # This is only reanchoring a node already snapped by W2. No new
        # adjacency is invented, and every incident original endpoint must
        # lie in the *existing* W2 snap footprint of the positive anchor.
        if (math.dist(npoint,point)>tolerance_pt or
                any(math.dist(p,point)>tolerance_pt for p in raw_endpoints)):
            continue
        if math.dist(npoint,point)<=_COORD_EPS:
            continue
        node["x"],node["y"]=point
        node["exact_source_through_anchor"]={"point_pt":point,
            "proof":"opposing_same_original_primitive_contiguous_local_fragments"}
        anchors.append({"node_id":node_id,"positive_original_point_pt":point})
    return {**graph, "nodes":nodes,
            "exact_source_through_junction_anchors": tuple(anchors)}
