"""Generic benchmark-only plan measurement helpers (no PlanReader code, no benchmark values).

Reads vector wall-face lines from a PDF page and measures rectangular room extents by ray
casting from a seed point against MERGED axis-aligned face lines, using several perpendicular
offsets so door/window gaps do not matter. Scale is the plotted scale (default 1:100 on a
72-dpi-point page); the origin is caller-supplied.
"""
from __future__ import annotations

import collections
from dataclasses import dataclass

import fitz

PT_MM_1_TO_100 = 25.4 / 72 * 100


@dataclass(frozen=True)
class Line:
    coord: float      # y for horizontal, x for vertical (pts)
    a: float          # extent start (pts)
    b: float          # extent end (pts)
    width: float


def wall_lines(page, region, widths=(0.96, 1.92, 1.44), min_len=4.0):
    """Axis-aligned black stroke lines of the wall layer, merged by coordinate (0.6 pt) and collinear overlap."""
    H, V = collections.defaultdict(list), collections.defaultdict(list)
    for dr in page.get_drawings():
        w = round(dr.get("width") or 0, 2)
        if dr["type"] not in ("s", "fs") or dr.get("color") != (0.0, 0.0, 0.0) or w not in widths:
            continue
        for it in dr["items"]:
            if it[0] != "l":
                continue
            p, q = it[1], it[2]
            if not (region[0] <= p.x <= region[2] and region[1] <= p.y <= region[3]):
                continue
            if ((p.x - q.x) ** 2 + (p.y - q.y) ** 2) ** 0.5 < min_len:
                continue
            if abs(p.y - q.y) < 0.25:
                H[round((p.y + q.y) / 2 / 0.6)].append((min(p.x, q.x), max(p.x, q.x), w))
            elif abs(p.x - q.x) < 0.25:
                V[round((p.x + q.x) / 2 / 0.6)].append((min(p.y, q.y), max(p.y, q.y), w))

    def merge(buckets):
        lines = []
        for key, ivs in buckets.items():
            ivs = sorted(ivs)
            cur = None
            for a, b, w in ivs:
                if cur and a <= cur[1] + 0.8:
                    cur[1] = max(cur[1], b)
                    cur[2].add(w)
                else:
                    if cur:
                        lines.append(Line(key * 0.6, cur[0], cur[1], max(cur[2])))
                    cur = [a, b, {w}]
            if cur:
                lines.append(Line(key * 0.6, cur[0], cur[1], max(cur[2])))
        return lines

    return merge(H), merge(V)


def _cast(lines, along, across_values, direction, min_cover=0.0):
    """Nearest line in `direction` (+1/-1) along the coordinate axis, for each across-offset; returns hit coords."""
    hits = []
    for across in across_values:
        best = None
        for ln in lines:
            if not (ln.a - 0.3 <= across <= ln.b + 0.3):
                continue
            d = (ln.coord - along) * direction
            if d > 0.4 and (best is None or d < best[0]):
                best = (d, ln.coord)
        if best:
            hits.append(best[1])
    return hits


def mode_coord(vals, tol=0.9):
    """Most frequent coordinate (within tol pts); returns (coord, support, total)."""
    if not vals:
        return None, 0, 0
    vals = sorted(vals)
    best = (None, 0)
    for v in vals:
        sup = sum(1 for u in vals if abs(u - v) <= tol)
        if sup > best[1]:
            best = (v, sup)
    cluster = [u for u in vals if abs(u - best[0]) <= tol]
    return sum(cluster) / len(cluster), best[1], len(vals)


def room_rect(H, V, seed, span=14.0, n=11):
    """Rect (x0, x1, y0, y1) in pts around seed (x, y); each side the modal nearest face over n perpendicular offsets."""
    sx, sy = seed
    offs = [(-span + 2 * span * i / (n - 1)) for i in range(n)]
    west = mode_coord(_cast(V, sx, [sy + o for o in offs], -1))
    east = mode_coord(_cast(V, sx, [sy + o for o in offs], +1))
    north = mode_coord(_cast(H, sy, [sx + o for o in offs], -1))
    south = mode_coord(_cast(H, sy, [sx + o for o in offs], +1))
    return {"W": west, "E": east, "N": north, "S": south}


def rect_mm(r, origin, mm_per_pt=PT_MM_1_TO_100):
    ox, oy = origin
    x0, x1 = (r["W"][0] - ox) * mm_per_pt, (r["E"][0] - ox) * mm_per_pt
    y0, y1 = (r["N"][0] - oy) * mm_per_pt, (r["S"][0] - oy) * mm_per_pt
    return x0, x1, y0, y1


# ---------------------------------------------------------------------------------------------
# Planar-arrangement flood fill (orthogonal plans). Exact areas for rectangles and L-shapes.
# ---------------------------------------------------------------------------------------------
import bisect


def bridge_gaps(lines, max_gap_pt):
    """Bridge gaps between collinear wall segments (door/window openings) shorter than max_gap_pt."""
    by = collections.defaultdict(list)
    for ln in lines:
        by[round(ln.coord / 0.6)].append(ln)
    out = []
    for key, group in by.items():
        group = sorted(group, key=lambda l: l.a)
        out.extend(group)
        for g1, g2 in zip(group, group[1:]):
            gap = g2.a - g1.b
            if 0.8 < gap <= max_gap_pt:
                out.append(Line(g1.coord, g1.b, g2.a, 0.0))   # virtual closure
    return out


def flood_room(H, V, seed, max_gap_pt=71.0, max_cells=4000):
    """Area (pt^2) and bounding box of the free region containing `seed`, with openings <= max_gap_pt bridged.
    Returns None if the region is unbounded/leaks (touches the outermost grid cell)."""
    Hb, Vb = bridge_gaps(H, max_gap_pt), bridge_gaps(V, max_gap_pt)
    xs = sorted({round(l.coord, 2) for l in Vb} | {round(l.a, 2) for l in Hb} | {round(l.b, 2) for l in Hb})
    ys = sorted({round(l.coord, 2) for l in Hb} | {round(l.a, 2) for l in Vb} | {round(l.b, 2) for l in Vb})
    nx, ny = len(xs) - 1, len(ys) - 1
    # blocked edges between cells: vertical walls block (i,j)<->(i+1,j); horizontal walls block (i,j)<->(i,j+1)
    vblock, hblock = set(), set()
    for l in Vb:
        i = bisect.bisect_left(xs, round(l.coord, 2))
        j0, j1 = bisect.bisect_left(ys, round(l.a, 2)), bisect.bisect_left(ys, round(l.b, 2))
        for j in range(j0, j1):
            vblock.add((i, j))          # wall at x index i separates cell i-1 and i
    for l in Hb:
        j = bisect.bisect_left(ys, round(l.coord, 2))
        i0, i1 = bisect.bisect_left(xs, round(l.a, 2)), bisect.bisect_left(xs, round(l.b, 2))
        for i in range(i0, i1):
            hblock.add((i, j))          # wall at y index j separates cell j-1 and j
    sx, sy = seed
    si, sj = bisect.bisect_right(xs, sx) - 1, bisect.bisect_right(ys, sy) - 1
    if not (0 <= si < nx and 0 <= sj < ny):
        return None
    seen, stack = {(si, sj)}, [(si, sj)]
    leak = False
    while stack:
        i, j = stack.pop()
        if i in (0, nx - 1) or j in (0, ny - 1):
            leak = True
        for di, dj, blocked in ((1, 0, (i + 1, j) in vblock), (-1, 0, (i, j) in vblock),
                                (0, 1, (i, j + 1) in hblock), (0, -1, (i, j) in hblock)):
            ni, nj = i + di, j + dj
            if blocked or not (0 <= ni < nx and 0 <= nj < ny) or (ni, nj) in seen:
                continue
            seen.add((ni, nj))
            stack.append((ni, nj))
            if len(seen) > max_cells:
                return None
    area = sum((xs[i + 1] - xs[i]) * (ys[j + 1] - ys[j]) for i, j in seen)
    x0 = min(xs[i] for i, _ in seen); x1 = max(xs[i + 1] for i, _ in seen)
    y0 = min(ys[j] for _, j in seen); y1 = max(ys[j + 1] for _, j in seen)
    return {"area_pt2": area, "bbox": (x0, x1, y0, y1), "cells": len(seen), "leak": leak}


# ---------------------------------------------------------------------------------------------
# Snapped digitisation: approximate rectangle -> sides snapped to real wall-face lines
# ---------------------------------------------------------------------------------------------
def snap_side(lines, approx_coord, span, tol, prefer="inner"):
    """Best face line near approx_coord (pts) whose extent covers >= 40% of span=(a,b); returns (coord, coverage, n_candidates)."""
    cands = []
    a, b = span
    for ln in lines:
        if abs(ln.coord - approx_coord) > tol:
            continue
        ov = min(ln.b, b) - max(ln.a, a)
        cov = max(0.0, ov) / max(1e-6, b - a)
        if cov >= 0.4:
            cands.append((ln.coord, cov))
    if not cands:
        return None, 0.0, 0
    # prefer the candidate nearest to the approximate coordinate; ties -> higher coverage
    cands.sort(key=lambda c: (round(abs(c[0] - approx_coord), 1), -c[1]))
    return cands[0][0], cands[0][1], len(cands)


def snap_rect(H, V, approx, tol=3.5):
    """approx = (x0,y0,x1,y1) in pts. Returns dict with snapped rect and per-side coverage."""
    x0, y0, x1, y1 = approx
    W_, cw, nw = snap_side(V, x0, (y0, y1), tol)
    E_, ce, ne = snap_side(V, x1, (y0, y1), tol)
    N_, cn, nn = snap_side(H, y0, (x0, x1), tol)
    S_, cs, ns = snap_side(H, y1, (x0, x1), tol)
    return {"x0": W_, "x1": E_, "y0": N_, "y1": S_, "cov": {"W": cw, "E": ce, "N": cn, "S": cs}}
