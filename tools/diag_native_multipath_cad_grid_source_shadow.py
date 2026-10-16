"""Read-only native multi-path orthogonal grid components for CAD schedules.

F.07's vector-frame extractor sees one closed four-line path or rectangle
object, while CAD tables often issue *each edge* as an independent PDF path.
This source diagnostic recovers same-original-style endpoint-connected line
components and audits complete outer borders/internal lines. It keeps every
rival connected grid (including walls/plan grids): a closed orthogonal lattice
is NOT semantic schedule/viewport/material/room/metric authority.

No labels, filenames, page IDs, expected quantities or nearest-frame ranking
are used as classifier inputs. Original native path+item source identities stay
attached to every candidate. Native .001pt indexing is NOT W2 snapping.
"""
from __future__ import annotations

from collections import defaultdict
import math
from typing import Any

NATIVE_SOURCE_COORD_ROUND_DIGITS = 3
MAX_NATIVE_AXIS_STROKE_CANDIDATES = 15000


def _finite(v):
    return isinstance(v, (int,float)) and not isinstance(v, bool) and math.isfinite(float(v))


def _normal_coordinate(value):
    return round(float(value), NATIVE_SOURCE_COORD_ROUND_DIGITS)


def _stroke_style(drawing):
    color = drawing.get("color")
    width = drawing.get("width")
    if not isinstance(color, (tuple,list)) or not color or not _finite(width) or width <= 0:
        return None
    if any(not _finite(v) for v in color):
        return None
    opacity = drawing.get("stroke_opacity", 1.0)
    if not _finite(opacity):
        return None
    return (
        tuple(round(float(c),6) for c in color),
        round(float(width),3),
        repr(drawing.get("dashes")),
        str(drawing.get("layer") or ""),
        round(float(opacity),6),
    )


def _native_axis_line(item):
    try:
        if item[0] != "l":
            return None
        p, q = item[1:3]
        x0,y0,x1,y1 = tuple(map(_normal_coordinate, (p.x,p.y,q.x,q.y)))
    except (IndexError, TypeError, ValueError, OverflowError, AttributeError):
        return None
    if not all(_finite(v) for v in (x0,y0,x1,y1)):
        return None
    if x0 == x1 and y0 != y1:
        return (x0,y0,x1,y1,"native_y")
    if y0 == y1 and x0 != x1:
        return (x0,y0,x1,y1,"native_x")
    return None


def _coverage_complete(intervals, *, lo, hi) -> bool:
    """Exact source interval union, not stroke-width gap bridging."""
    if not intervals:
        return False
    pairs=sorted((min(a,b),max(a,b)) for a,b in intervals)
    if pairs[0][0] > lo:
        return False
    end=pairs[0][1]
    for start,stop in pairs[1:]:
        if start > end:
            return False
        end=max(end,stop)
    return end >= hi


def _two_axis_outer_grid_source_witness(records) -> dict:
    xs={line[1] for line in records if line[5]=="native_y"}
    ys={line[2] for line in records if line[5]=="native_x"}
    xpoints=[p for line in records for p in (line[1],line[3])]
    ypoints=[p for line in records for p in (line[2],line[4])]
    if not xpoints or not ypoints:
        return {"full_native_outer_grid_candidate":False,"reason":"no_original_axis_segments"}
    bbox=(min(xpoints),min(ypoints),max(xpoints),max(ypoints))
    if len(xs)<3 or len(ys)<3:
        return {
            "full_native_outer_grid_candidate":False,
            "reason":"fewer_than_three_original_grid_axes_per_direction",
            "native_bbox_pdf_pts":list(bbox),
        }
    xmin,ymin,xmax,ymax=bbox
    vertical=defaultdict(list)
    horizontal=defaultdict(list)
    for sid,x0,y0,x1,y1,axis in records:
        if axis=="native_y":
            vertical[x0].append((y0,y1))
        elif axis=="native_x":
            horizontal[y0].append((x0,x1))
    outer=all((
        _coverage_complete(vertical[xmin],lo=ymin,hi=ymax),
        _coverage_complete(vertical[xmax],lo=ymin,hi=ymax),
        _coverage_complete(horizontal[ymin],lo=xmin,hi=xmax),
        _coverage_complete(horizontal[ymax],lo=xmin,hi=xmax),
    ))
    interior_x=[
        x for x in xs if xmin<x<xmax
        and _coverage_complete(vertical[x],lo=ymin,hi=ymax)
    ]
    # At least one internal horizontal row must be natively source joined
    # to *distinct* fully-spanning vertical column lines. The title column
    # may be merged (no complete horizontal across full outer frame).
    interior_y=[]
    for y in ys:
        if not (ymin<y<ymax):
            continue
        starts=sorted(set(
            [xmin,xmax,*interior_x]
        ))
        if any(
            _coverage_complete(horizontal[y],lo=start,hi=xmax)
            for start in starts[:-1]
        ):
            interior_y.append(y)
    return {
        "native_bbox_pdf_pts":list(bbox),
        "original_distinct_vertical_axis_count":len(xs),
        "original_distinct_horizontal_axis_count":len(ys),
        "native_complete_outer_border":bool(outer),
        "original_full_height_internal_column_coordinates":interior_x,
        "original_partially_merged_internal_row_coordinates":interior_y,
        "full_native_outer_grid_candidate":bool(outer and interior_x and interior_y),
        "reason":(
            "source_connected_closed_grid_candidate_not_semantic_table"
            if outer and interior_x and interior_y
            else "native_grid_outer_or_inner_source_edges_unresolved"
        ),
    }


def audit_native_multipath_orthogonal_grid_components(
    page: Any, *, max_source_line_candidates=MAX_NATIVE_AXIS_STROKE_CANDIDATES,
):
    """Enumerate all independent native-style source grids; no selected frame."""
    if type(max_source_line_candidates) is not int or max_source_line_candidates < 1:
        raise ValueError("positive_bounded_source_line_scope_required")
    styles=defaultdict(list)
    count=0
    for path_index,drawing in enumerate(page.get_drawings()):
        style=_stroke_style(drawing)
        if style is None:
            continue
        for item_index,item in enumerate(drawing.get("items", ())):
            line=_native_axis_line(item)
            if line is None:
                continue
            count+=1
            if count>max_source_line_candidates:
                return {
                    "status":"original_axis_source_scope_exceeds_cap",
                    "source_line_universe_complete":False,
                    "candidate_native_grids":[],
                    "new_authoritative_viewports":0,
                    "new_source_material_or_quantities":0,
                }
            styles[style].append((f"d{path_index}i{item_index}",*line))
    grids=[]
    for style,records in styles.items():
        n=len(records)
        parent=list(range(n))
        def root(k):
            while parent[k]!=k:
                parent[k]=parent[parent[k]]
                k=parent[k]
            return k
        def union(a,b):
            ra,rb=root(a),root(b)
            if ra!=rb:
                parent[rb]=ra
        endpoints=defaultdict(list)
        horizontals=defaultdict(list)
        verticals=defaultdict(list)
        for i,(_sid,x0,y0,x1,y1,axis) in enumerate(records):
            endpoints[(x0,y0)].append(i)
            endpoints[(x1,y1)].append(i)
            if axis=="native_y":
                verticals[x0].append(i)
            else:
                horizontals[y0].append(i)
        for node_ids in endpoints.values():
            for j in node_ids[1:]:
                union(node_ids[0],j)
        for i,(_sid,x0,y0,x1,y1,axis) in enumerate(records):
            for x,y in ((x0,y0),(x1,y1)):
                if axis=="native_y":
                    for j in horizontals.get(y,()):
                        other=records[j]
                        if min(other[1],other[3]) <= x <= max(other[1],other[3]):
                            union(i,j)
                else:
                    for j in verticals.get(x,()):
                        other=records[j]
                        if min(other[2],other[4]) <= y <= max(other[2],other[4]):
                            union(i,j)
        components=defaultdict(list)
        for i in range(n):
            components[root(i)].append(i)
        for component in components.values():
            if len(component)<8:
                continue
            source=[records[i] for i in component]
            witness=_two_axis_outer_grid_source_witness(source)
            if not witness["full_native_outer_grid_candidate"]:
                continue
            grids.append({
                "original_ink_class": {
                    "stroke_color":list(style[0]),
                    "native_stroke_width_pdf_pts":style[1],
                    "original_dash_state":style[2],
                    "original_layer_name":style[3],
                    "native_stroke_opacity":style[4],
                },
                "original_source_primitive_ids":sorted(row[0] for row in source),
                "original_native_line_segments_pdf_pts":[
                    list(row[1:5]) for row in source
                ],
                "original_source_primitive_count":len(source),
                "native_component_witness":witness,
                "native_table_text_or_title_owner_proven":False,
                "original_pdf_clip_paint_source_role_proven":False,
                "view_extent_or_ceiling_authority_granted":False,
            })
    grids.sort(key=lambda row:(
        tuple(row["native_component_witness"]["native_bbox_pdf_pts"]),
        row["original_source_primitive_ids"],
    ))
    return {
        "status":"read_only_original_native_multipath_grid_candidates",
        "source_line_universe_complete":True,
        "original_axis_line_candidate_count":count,
        "candidate_native_grids":grids,
        "new_authoritative_viewports":0,
        "new_source_material_or_quantities":0,
        "source_pdf_mutated":False,
    }
