"""Source-native six-edge callout ink witness, strictly diagnostic.

This proves only that an original text bbox is enclosed by exactly one native
closed six-segment polygon. It does NOT associate a physical aperture, wall,
opening kind, schedule row, measurement, customer output or benchmark target.
"""
from __future__ import annotations

from collections import defaultdict
from math import isfinite
from typing import Iterable


def native_line_segments(page) -> tuple[tuple[int, float, float, float, float], ...]:
    """Keep original PyMuPDF drawing seqnos; no raster or OCR reconstruction."""
    lines = []
    for drawing in page.get_drawings():
        seqno = drawing.get("seqno")
        if type(seqno) is not int:
            continue
        for item in drawing.get("items", ()):
            if item[0] != "l":
                continue
            a, b = item[1:3]
            values = (float(a.x), float(a.y), float(b.x), float(b.y))
            if all(isfinite(x) for x in values):
                lines.append((seqno, *values))
    return tuple(lines)


def _cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])


def _strictly_inside(point, polygon):
    signs = [_cross(polygon[i], polygon[(i+1)%len(polygon)], point)
             for i in range(len(polygon))]
    return all(x > 1e-5 for x in signs) or all(x < -1e-5 for x in signs)


def _convex(polygon):
    signs = [_cross(polygon[i], polygon[(i+1)%6], polygon[(i+2)%6])
             for i in range(6)]
    return all(x > 1e-5 for x in signs) or all(x < -1e-5 for x in signs)


def diagnose_hex_ink_for_text_bbox(
    bbox: tuple[float, float, float, float],
    source_lines: Iterable[tuple[int, float, float, float, float]],
) -> dict:
    """Require one uniquely closed convex six-edge source loop around the word.

    Candidate search is relative to native word dimensions, not a global PDF
    snap or project-specific pixel/point distance. Duplicated original strokes
    are retained as source identities, but count as one geometrical edge.
    """
    if len(bbox) != 4 or not all(isfinite(x) for x in bbox):
        raise ValueError("finite original word bbox required")
    x0, y0, x1, y1 = bbox
    if x1 <= x0 or y1 <= y0:
        raise ValueError("nonempty original word bbox required")
    span = max(x1-x0, y1-y0)
    margin = span * 1.5
    bounds = (x0-margin, y0-margin, x1+margin, y1+margin)
    edges: dict[tuple[tuple[float,float], tuple[float,float]], set[int]] = defaultdict(set)
    for row in source_lines:
        if len(row) != 5 or type(row[0]) is not int:
            continue
        seqno, ax, ay, bx, by = row
        if not all(isfinite(v) for v in (ax, ay, bx, by)):
            continue
        if not (bounds[0] <= ax <= bounds[2] and bounds[0] <= bx <= bounds[2]
                and bounds[1] <= ay <= bounds[3] and bounds[1] <= by <= bounds[3]):
            continue
        a, b = (round(ax,3), round(ay,3)), (round(bx,3), round(by,3))
        if a != b:
            edges[tuple(sorted((a,b)))].add(seqno)
    if len(edges) > 250:
        return {"status":"CONFLICT", "reason":"local_source_ink_unbounded", "source_seqnos":[]}
    neighbors: dict[tuple[float,float], set[tuple[float,float]]] = defaultdict(set)
    for a,b in edges:
        neighbors[a].add(b)
        neighbors[b].add(a)
    cycles: dict[tuple[tuple[float,float],...], tuple] = {}
    # A native callout has six physical ink edges. Do not close a gap or
    # interpolate a missing segment from text/shape resemblance.
    for start in sorted(neighbors):
        stack = [(start,(start,))]
        while stack:
            node, path = stack.pop()
            if len(path) == 6:
                if start not in neighbors[node]:
                    continue
                polygon = path
                if not _convex(polygon):
                    continue
                corners = ((x0,y0),(x0,y1),(x1,y0),(x1,y1))
                # Rotated native text may have one glyph-envelope corner just
                # outside a sloping hex side: require centre plus 3 corners.
                if not (_strictly_inside(((x0+x1)/2,(y0+y1)/2),polygon)
                        and sum(_strictly_inside(c,polygon) for c in corners)>=3):
                    continue
                xs=[p[0] for p in polygon]; ys=[p[1] for p in polygon]
                if max(xs)-min(xs) > 3.5*span or max(ys)-min(ys)>3.5*span:
                    continue
                canon=tuple(sorted(polygon))
                cycles[canon]=polygon
                continue
            for nxt in sorted(neighbors[node]):
                if nxt not in path and nxt >= start:
                    stack.append((nxt,path+(nxt,)))
    if len(cycles)!=1:
        return {"status":"ABSTAIN" if not cycles else "CONFLICT",
                "reason":"no_unique_closed_native_six_edge_callout",
                "source_seqnos":[]}
    polygon=next(iter(cycles.values()))
    seqnos=sorted(set().union(*(
        edges[tuple(sorted((polygon[i],polygon[(i+1)%6])))]
        for i in range(6)
    )))
    return {"status":"SOURCE_NATIVE_HEX_INK_ONLY", "reason":"six_source_edges_closed",
            "source_seqnos":seqnos,
            "polygon_bbox_pt":[min(p[0] for p in polygon),min(p[1] for p in polygon),
                               max(p[0] for p in polygon),max(p[1] for p in polygon)],
            "physical_opening_bound":False, "measurement_granted":False,
            "customer_seal_granted":False}
