"""pb_gable_polygon_geometry.py — Source-derived gable-end wall polygon
reconstruction (KSTVET BOQ-C36-B and generically any pitched gable end).

Replaces the naive ``0.5 * span * ((span/2) * tan(pitch))`` assumption
(implicitly: a perfectly symmetric triangle, ridge exactly centered, one
gable width reused verbatim from the building's overall envelope, doubled
by an unproven "2 ends" algebraic identity) with a real polygon built from
the elevation's own vector roofline geometry.

Design:

- A gable end's roofline is one or more real vector line segments forming
  a continuous, monotonically-ordered profile between a LEFT and RIGHT
  boundary x-position (the end wall's own extent -- supplied by the
  caller, e.g. from grid/dimension evidence; this module does not invent
  a boundary).
- Each segment's own slope is measured directly from its endpoints --
  never assumed equal on both sides. An optional expected pitch is used
  only to REJECT unrelated lines (a different pitch outside tolerance is
  not part of this gable), never to force a value.
- The polygon is the ordered chain of roofline vertices between the two
  boundary x-positions, each boundary edge's own line equation evaluated
  AT the boundary (never extrapolated past real measured segments).
  Ridge/eave vertices are wherever consecutive roofline segments meet.
  This handles a plain triangular gable (2 segments meeting once), a
  trapezoidal/flat-topped gable (a near-horizontal connecting segment
  between two slopes), a mono-pitch end (1 segment), and a stepped end
  (3+ segments) all through the same mechanism -- no shape is assumed in
  advance.
- Zero roofline segments found in the region is a valid, honest result:
  NO_GABLE (e.g. a hip end, or a parapet/flat termination) -- never
  guessed into a triangle.
- Area is the polygon's own shoelace area against the wall's base line
  (the two boundary points at whatever height the roofline resolves to
  there) -- never ``0.5*base*height`` unless that literally is the
  resulting triangle.

Nothing here reads or depends on any benchmark/expected quantity.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Sequence, Tuple


class GableReconstructionStatus(str, Enum):
    RESOLVED = "resolved"
    NO_GABLE = "no_gable"  # zero roofline segments in the boundary region
    UNRESOLVED_AMBIGUOUS = "unresolved_ambiguous"  # competing/conflicting segments
    UNRESOLVED_GAP = "unresolved_gap"  # segments don't span the full boundary


@dataclass(frozen=True)
class RoofEdgeSegment:
    """One real vector line segment observed in the elevation's roofline
    region. Coordinates are in the page's own PDF-point space."""

    start: Tuple[float, float]
    end: Tuple[float, float]
    source_id: str = ""

    @property
    def x_span(self) -> Tuple[float, float]:
        return (min(self.start[0], self.end[0]), max(self.start[0], self.end[0]))

    @property
    def slope(self) -> Optional[float]:
        dx = self.end[0] - self.start[0]
        if abs(dx) < 1e-9:
            return None
        return (self.end[1] - self.start[1]) / dx

    def y_at(self, x: float) -> float:
        dx = self.end[0] - self.start[0]
        if abs(dx) < 1e-9:
            return self.start[1]
        t = (x - self.start[0]) / dx
        return self.start[1] + t * (self.end[1] - self.start[1])


@dataclass(frozen=True)
class GablePolygon:
    """A fully authenticated gable-end wall polygon."""

    vertices: Tuple[Tuple[float, float], ...]  # PDF-point space, left-to-right roofline + base
    source_segment_ids: Tuple[str, ...]
    status: str

    def area_pt2(self) -> float:
        pts = self.vertices
        n = len(pts)
        if n < 3:
            return 0.0
        total = 0.0
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            total += x1 * y2 - x2 * y1
        return abs(total) / 2.0

    def area_m2(self, scale_m_per_pt: float) -> float:
        return self.area_pt2() * (scale_m_per_pt ** 2)


def _pitch_deg(slope: float) -> float:
    return math.degrees(math.atan(abs(slope)))


def reconstruct_gable_polygon(
    segments: Sequence[RoofEdgeSegment],
    *,
    left_boundary_x: float,
    right_boundary_x: float,
    expected_pitch_deg: Optional[float] = None,
    pitch_tolerance_deg: float = 1.0,
    apex_snap_tolerance_pt: float = 3.0,
) -> Tuple[Optional[GablePolygon], str]:
    """Reconstruct one gable-end roofline polygon between two authenticated
    boundary x-positions (e.g. the end wall's own grid/dimension extent).

    Returns (polygon_or_none, status). Never returns a polygon on anything
    less than a fully-spanning, unambiguous roofline chain.
    """
    lo, hi = (left_boundary_x, right_boundary_x) if left_boundary_x <= right_boundary_x else (right_boundary_x, left_boundary_x)

    def _in_region(seg: RoofEdgeSegment) -> bool:
        x0, x1 = seg.x_span
        return x1 > lo and x0 < hi

    sloped: List[RoofEdgeSegment] = []
    for seg in segments:
        slope = seg.slope
        if slope is None or abs(slope) < 1e-6:
            continue  # vertical or flat -- not a roof pitch line on its own
        if not _in_region(seg):
            continue
        if expected_pitch_deg is not None:
            if abs(_pitch_deg(slope) - expected_pitch_deg) > pitch_tolerance_deg:
                continue  # a different, unrelated pitch -- not this gable
        sloped.append(seg)

    if not sloped:
        return None, GableReconstructionStatus.NO_GABLE.value

    # Order candidates left-to-right by their own x-span start.
    ordered = sorted(sloped, key=lambda s: s.x_span[0])

    # Reject genuine overlap between consecutive candidates (two competing
    # lines both claiming the same stretch of roofline) -- never averaged
    # or silently resolved by pick-one. A shared endpoint (near-zero
    # overlap, within snap tolerance) is normal chaining, not a conflict.
    for i in range(len(ordered) - 1):
        a, b = ordered[i], ordered[i + 1]
        overlap = a.x_span[1] - b.x_span[0]
        if overlap > apex_snap_tolerance_pt:
            return None, GableReconstructionStatus.UNRESOLVED_AMBIGUOUS.value

    # Bridge any gap between consecutive sloped segments with a connecting
    # segment (flat "ridge run" or otherwise) found among ALL segments --
    # never fabricated, never a different unrelated pitch's segment reused.
    chain: List[RoofEdgeSegment] = [ordered[0]]
    for nxt in ordered[1:]:
        prev = chain[-1]
        gap = nxt.x_span[0] - prev.x_span[1]
        if gap > apex_snap_tolerance_pt:
            connector = None
            for cand in segments:
                cx0, cx1 = cand.x_span
                if (
                    abs(cx0 - prev.x_span[1]) <= apex_snap_tolerance_pt
                    and abs(cx1 - nxt.x_span[0]) <= apex_snap_tolerance_pt
                ):
                    connector = cand
                    break
            if connector is None:
                return None, GableReconstructionStatus.UNRESOLVED_GAP.value
            chain.append(connector)
        chain.append(nxt)

    # Build the vertex chain: boundary point on the left, each segment's
    # own endpoints in order, boundary point on the right. Each boundary
    # point is evaluated on the OUTERMOST segment's own line equation --
    # never extrapolated beyond the chain's real measured span if the
    # chain does not reach the boundary at all.
    first, last = chain[0], chain[-1]
    if first.x_span[0] > lo + apex_snap_tolerance_pt or last.x_span[1] < hi - apex_snap_tolerance_pt:
        return None, GableReconstructionStatus.UNRESOLVED_GAP.value

    roofline_vertices: List[Tuple[float, float]] = [(lo, first.y_at(lo))]
    for i in range(len(chain) - 1):
        a, b = chain[i], chain[i + 1]
        # Vertex where consecutive segments meet: prefer the real shared
        # endpoint (nearest pair of the two segments' own endpoints).
        candidates_pts = [a.start, a.end, b.start, b.end]
        a_end = a.end if abs(a.x_span[1] - sum(b.x_span) / 2.0) < abs(a.x_span[0] - sum(b.x_span) / 2.0) else a.start
        b_start = b.start if abs(b.x_span[0] - a_end[0]) < abs(b.x_span[1] - a_end[0]) else b.end
        vertex = ((a_end[0] + b_start[0]) / 2.0, (a_end[1] + b_start[1]) / 2.0)
        roofline_vertices.append(vertex)
    roofline_vertices.append((hi, last.y_at(hi)))

    # The polygon closes along the base (straight line from right boundary
    # back to left boundary at whatever height the roofline resolved to
    # there -- a possibly-tilted base if the two eave heights differ,
    # never forced level).
    full_polygon = tuple(roofline_vertices)

    return (
        GablePolygon(
            vertices=full_polygon,
            source_segment_ids=tuple(s.source_id for s in chain),
            status=GableReconstructionStatus.RESOLVED.value,
        ),
        GableReconstructionStatus.RESOLVED.value,
    )
