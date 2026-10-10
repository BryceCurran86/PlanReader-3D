"""Conservative experimental source-admission quarantine (NOT host authority).

Never clips a compact candidate into invented edges: if any independently
visible ordinary source observation already owns a nontrivial registered
centerline interval, withhold the entire competing compact nomination.
Does not add geometry, counts, scale, hosts or QuantityEvidence.
"""
from __future__ import annotations

import math


def compact_band_has_partial_original_source_coverage(segment, source_lines, *, dpi: int, source_dpi: int) -> bool:
    """True only for positive ordinary-source pixel-cell/core overlap.

    The spatial registration uses original render pixel footprints, not a
    physical wall, snap, angular or construction measurement tolerance.
    Call only after image-only/full visible-paint equality was authenticated.
    """
    if (not isinstance(dpi, int) or not isinstance(source_dpi, int)
            or dpi <= 0 or source_dpi <= 0):
        return False
    try:
        x0,y0,x1,y1 = (float(v) for v in segment.pixel_support_bounds)
        c = tuple(float(v) for v in segment.pixel_geometry)
        orientation = segment.orientation
    except (TypeError, AttributeError, ValueError, OverflowError):
        return False
    if (len(c) != 4 or not all(math.isfinite(v) for v in (*c,x0,y0,x1,y1))
            or x1 <= x0+2 or y1 <= y0+2):
        return False
    if orientation == "horizontal" and c[1] == c[3]:
        lo,hi,cross = x0+1.,x1-1.,(c[1]+c[3])/2.
    elif orientation == "vertical" and c[0] == c[2]:
        lo,hi,cross = y0+1.,y1-1.,(c[0]+c[2])/2.
    else:
        return False
    source_half_pixel = dpi/(2.*source_dpi)
    for source in source_lines:
        if getattr(source,"orientation",None) != orientation:
            continue
        try:
            q = tuple(float(v)*dpi/72. for v in source.geometry_pt)
        except (TypeError,AttributeError,ValueError,OverflowError):
            continue
        if len(q) != 4 or not all(math.isfinite(v) for v in q):
            continue
        if orientation == "horizontal" and q[1] == q[3]:
            span,normal = sorted((q[0],q[2])),q[1]
        elif orientation == "vertical" and q[0] == q[2]:
            span,normal = sorted((q[1],q[3])),q[0]
        else:
            continue
        # Half of each registered source/destination pixel cell, not a new
        # physical/angular/snap allowance.
        if abs(normal-cross) > source_half_pixel + .5:
            continue
        overlap = min(hi,span[1]+source_half_pixel)-max(lo,span[0]-source_half_pixel)
        if overlap >= 2.*source_half_pixel:
            return True
    return False
