"""Reconstruct a dimensioned site traverse in the registered dwelling model frame.
No OCR guesses, scale from house bounds, or implied missing boundary segments.
The caller must obtain the ordered lengths/bearings and registration from the
actual site drawing; this module does not authenticate or extract PDF labels.
"""
from __future__ import annotations
import math
from dataclasses import dataclass

@dataclass(frozen=True)
class BoundaryLeg:
    length_m: float
    bearing_deg: float  # clockwise from registered plan north

def reconstruct_site_boundary(legs: tuple[BoundaryLeg, ...], *,
                              origin_xz: tuple[float, float],
                              north_rotation_deg: float = 0.0,
                              closure_tolerance_m: float = 0.02) -> dict:
    if not 3 <= len(legs) <= 100:
        raise ValueError("site_boundary_leg_count")
    if (len(origin_xz) != 2 or not all(math.isfinite(v) and abs(v) <= 10000 for v in origin_xz)
            or not math.isfinite(north_rotation_deg)
            or not 0 < closure_tolerance_m <= 0.05):
        raise ValueError("site_boundary_registration_invalid")
    points = [tuple(origin_xz)]
    for leg in legs:
        if not (math.isfinite(leg.length_m) and 0.1 <= leg.length_m <= 1000
                and math.isfinite(leg.bearing_deg) and 0 <= leg.bearing_deg < 360):
            raise ValueError("site_boundary_dimension_invalid")
        theta = math.radians(leg.bearing_deg + north_rotation_deg)
        x, z = points[-1]
        points.append((x + leg.length_m * math.sin(theta), z - leg.length_m * math.cos(theta)))
    error = math.dist(points[0], points[-1])
    if error > closure_tolerance_m:
        raise ValueError("site_boundary_does_not_close")
    vertices = points[:-1]
    # Reject repeated vertices and non-adjacent intersecting edges.
    def cross(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    def intersects(a,b,c,d):
        def on(p,q,r):
            return (abs(cross(p,q,r)) <= 1e-8
                    and min(p[0],q[0])-1e-8 <= r[0] <= max(p[0],q[0])+1e-8
                    and min(p[1],q[1])-1e-8 <= r[1] <= max(p[1],q[1])+1e-8)
        return (cross(a,b,c)*cross(a,b,d)<0 and cross(c,d,a)*cross(c,d,b)<0
                or on(a,b,c) or on(a,b,d) or on(c,d,a) or on(c,d,b))
    n = len(vertices)
    for i,a in enumerate(vertices):
        if any(math.dist(a,b)<0.1 for b in vertices[i+1:]):
            raise ValueError("site_boundary_repeated_vertex")
        for j in range(i+2,n):
            if i==0 and j==n-1:
                continue
            if intersects(a,vertices[(i+1)%n],vertices[j],vertices[(j+1)%n]):
                raise ValueError("site_boundary_self_intersection")
    area = abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(vertices,vertices[1:]+vertices[:1])))/2
    if area < 1 or not all(abs(v)<=10000 for p in vertices for v in p):
        raise ValueError("site_boundary_area_or_extent_invalid")
    return {"verticesXZ":[list(p) for p in vertices], "areaM2":area,
            "perimeterM":sum(leg.length_m for leg in legs), "closureErrorM":error,
            "status":"review_only"}
