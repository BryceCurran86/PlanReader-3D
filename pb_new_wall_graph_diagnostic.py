"""Source-native wall graph diagnostics; no guessed envelope or metric authority.

Connectivity is computed only between source-backed physical *candidates*, with
the 0.03 PDF-point representation tolerance already used by the original
topology engine. No line extension, outside-site convex hull, or gap closure.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

from shapely.strtree import STRtree


@dataclass(frozen=True)
class NativeWallGraphDiagnostic:
    component_count: int = 0
    largest_component_band_count: int = 0
    largest_component_source_paths: tuple[int, ...] = ()
    largest_component_bbox_pdf_pts: tuple[float, float, float, float] | None = None
    largest_component_open_endpoints_pdf_pts: tuple[tuple[float, float], ...] = ()
    connectivity_status: str = "unavailable"
    measurement_authorized: bool = False
    outside_ink_filter_authorized: bool = False


def inspect_native_wall_graph(bars: Sequence[object]) -> NativeWallGraphDiagnostic:
    """Source structural candidates only; diagnostic if an outer ring fails.

    Endpoints are where the long-axis native wall-band ends do NOT meet any
    other wall-band in the SAME connected graph. They are NOT asserted doors
    or missing walls. A candidate band has exactly its original source IDs.
    """
    valid = [
        s for s in bars if
        getattr(s, "polygon", None) is not None
        and s.polygon.is_valid and not s.polygon.is_empty
        and all(math.isfinite(float(v)) for v in s.polygon.bounds)
    ]
    if not valid:
        return NativeWallGraphDiagnostic()
    # Representation-noise contact only (not the 2.5-pt production snap).
    tol = .03
    geoms = [s.polygon.buffer(tol, join_style=2) for s in valid]
    tree = STRtree(geoms)
    parents = list(range(len(valid)))
    def find(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i
    for i, geom in enumerate(geoms):
        for j in tree.query(geom, predicate="intersects"):
            j = int(j)
            if i == j:
                continue
            a, b = find(i), find(j)
            if a != b:
                parents[max(a,b)] = min(a,b)
    groups = {}
    for i in range(len(valid)):
        groups.setdefault(find(i), []).append(i)
    # The largest group is only a connected structural *candidate*, not an
    # exterior wall or a proxy for the building's real external face.
    parts = sorted(groups.values(), key=lambda indices: (
        -len(indices),
        -sum(valid[i].polygon.area for i in indices),
        min(indices),
    ))
    main = parts[0]
    source_ids = tuple(sorted({
        int(path)
        for i in main for path in valid[i].native_path_indices()
    }))
    bb = tuple(round(float(v), 3) for v in (
        min(valid[i].polygon.bounds[0] for i in main),
        min(valid[i].polygon.bounds[1] for i in main),
        max(valid[i].polygon.bounds[2] for i in main),
        max(valid[i].polygon.bounds[3] for i in main),
    ))
    # A partial open wall network can be visualized by its source-native
    # free endpoints without pretending the bounding box is the footprint.
    endpoints = []
    for i in main:
        strip = valid[i]
        x0, y0, x1, y1 = (float(v) for v in strip.polygon.bounds)
        if x1-x0 > y1-y0:
            tips = (((x0,(y0+y1)/2),(x0,y0,x0,y1)),
                    ((x1,(y0+y1)/2),(x1,y0,x1,y1)))
        else:
            tips = ((((x0+x1)/2,y0),(x0,y0,x1,y0)),
                    (((x0+x1)/2,y1),(x0,y1,x1,y1)))
        for point, edge in tips:
            # A tip must touch ANOTHER source bar to count as joined.
            from shapely.geometry import LineString
            x_a,y_a,x_b,y_b = edge
            tip_edge = LineString(((x_a,y_a),(x_b,y_b)))
            connected = any(
                j != i and tip_edge.distance(valid[j].polygon) <= tol
                for j in main
            )
            if not connected:
                endpoints.append(tuple(round(v,3) for v in point))
    return NativeWallGraphDiagnostic(
        component_count=len(parts),
        largest_component_band_count=len(main),
        largest_component_source_paths=source_ids,
        largest_component_bbox_pdf_pts=bb,
        largest_component_open_endpoints_pdf_pts=tuple(sorted(set(endpoints))),
        connectivity_status=(
            "source_native_network_open"
            if endpoints else "source_native_network_endpoints_joined_not_exterior_verified"
        ),
    )
