"""Read-only native label candidate versus authenticated viewport boundary census.

A native label inside one physical floor-plan viewport is still ONLY a text
candidate. This module never creates a physical room, canonical ID, quantity,
metric area, material occurrence, or inferred cross-view ownership.
"""
from __future__ import annotations
import math
from typing import Any, Iterable

def classify_native_label_viewport(
    source_native_bbox: Iterable[float],
    viewports: Iterable[Any],
) -> dict[str, object]:
    try:
        native=tuple(float(v) for v in source_native_bbox)
    except (TypeError,ValueError):
        native=()
    if (len(native)!=4 or not all(math.isfinite(v) for v in native)
            or native[2]<=native[0] or native[3]<=native[1]):
        return {"first_gate":"malformed_source_native_label_bbox",
                "candidate_viewport_ids":[],"physical_room_proven":False}
    complete=[]
    unresolved=[]
    for viewport in viewports:
        if getattr(viewport,"status",None)!="resolved":
            if getattr(viewport,"view_type",None)=="floor_plan":
                unresolved.append(str(getattr(viewport,"view_id","")))
            continue
        bounds=getattr(viewport,"bounding_box",None)
        if bounds is None:
            continue
        try:
            bounds=tuple(float(v) for v in bounds)
        except (TypeError,ValueError):
            continue
        if len(bounds)!=4 or not all(math.isfinite(v) for v in bounds):
            continue
        # The ENTIRE raw native source line box must be inside the vector
        # viewport boundary. Center-point proximity cannot authenticate it.
        if all((
            bounds[0] <= native[0],
            bounds[1] <= native[1],
            native[2] <= bounds[2],
            native[3] <= bounds[3],
        )):
            complete.append(viewport)
    ids=sorted(str(getattr(v,"view_id","")) for v in complete)
    floors=[v for v in complete if getattr(v,"view_type",None)=="floor_plan"]
    if len(complete)>1:
        first="competing_source_viewport_owners"
    elif len(floors)==1:
        first="floor_plan_viewport_candidate_only"
    elif complete:
        first="native_label_in_nonfloor_viewport_only"
    elif unresolved:
        first="source_floor_plan_viewport_boundary_unresolved"
    else:
        first="native_label_outside_authenticated_source_viewports"
    return {
        "first_gate":first,
        "candidate_viewport_ids":ids,
        "unresolved_floor_plan_viewport_ids":sorted(unresolved),
        "physical_room_proven":False,
        "metric_area_proven":False,
    }
