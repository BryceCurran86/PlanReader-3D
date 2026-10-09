"""Conservative source projection; no authority or publication on its own.

Only sealed wall records and authenticated raster lines may reach a producer
consumer. These geometry checks do not authenticate those inputs themselves.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from pb_wall_room_topology_stage_a import DEFAULT_GAP_SNAP_TOLERANCE_PT

_COORD_TOL = 1e-6


def source_edge_axis_projection(record, geometry, source_lines: Mapping[str, Sequence[float]]):
    """Return the continuous, locally owned source interval, or unknown.

    Never extend a local edge to its ancestor's full extent, bridge a source
    gap, flatten a source bend or choose between different source offsets.
    """
    wall = record.wall_candidate
    identity = record.physical_identity
    fragments = record.source_edge_fragments
    if (not identity.usable or wall.is_curved or len(wall.centerline_pts) < 2
            or "non_simple_chain_topology_fallback_ordering" in wall.reason_codes
            or not fragments):
        return None
    edge_ids = tuple(str(f.edge_id) for f in fragments)
    if (len(set(edge_ids)) != len(edge_ids)
            or set(edge_ids) != set(identity.edge_ids)):
        return None
    primitive_ids = set(identity.source_primitive_ids)
    if not primitive_ids or primitive_ids != {
        p for fragment in fragments for p in fragment.source_primitive_ids
    }:
        return None

    def project(point, axis):
        return sum((float(point[i]) - geometry.origin[i]) * axis[i] for i in (0, 1))

    def line_data(line):
        try:
            line = tuple(float(v) for v in line)
        except (TypeError, ValueError, OverflowError):
            return None
        if len(line) != 4 or not all(math.isfinite(v) for v in line):
            return None
        a, b = line[:2], line[2:]
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        if length <= _COORD_TOL:
            return None
        across = (b[0] - a[0]) * geometry.axis[1] - (b[1] - a[1]) * geometry.axis[0]
        if abs(across) > _COORD_TOL * length:
            return None
        offsets = (project(a, geometry.normal), project(b, geometry.normal))
        if abs(offsets[0] - offsets[1]) > _COORD_TOL:
            return None
        along = (project(a, geometry.axis), project(b, geometry.axis))
        return min(along), max(along), offsets[0]

    intervals = []
    offsets = []
    for fragment in fragments:
        data = line_data(fragment.geometry)
        if data is None or not fragment.source_primitive_ids:
            return None
        lo, hi, offset = data
        coverage = []
        for primitive_id in fragment.source_primitive_ids:
            source = source_lines.get(primitive_id)
            parent = None if source is None else line_data(source)
            if parent is None or abs(parent[2] - offset) > _COORD_TOL:
                return None
            start, end = max(lo, parent[0]), min(hi, parent[1])
            # Every claimed ancestor must contribute to this local edge.
            # Clip first: a remote parent extent never enlarges ownership.
            if end - start <= _COORD_TOL:
                return None
            coverage.append((start, end))
        start, covered_end = sorted(coverage)[0]
        if start > lo + _COORD_TOL:
            return None
        for start, end in sorted(coverage)[1:]:
            if start > covered_end + _COORD_TOL:
                return None
            covered_end = max(covered_end, end)
        if covered_end < hi - _COORD_TOL:
            return None
        intervals.append((lo, hi))
        offsets.append(offset)
    if max(offsets) - min(offsets) > _COORD_TOL:
        return None
    lo, hi = sorted(intervals)[0]
    for start, end in sorted(intervals)[1:]:
        if start > hi + _COORD_TOL:
            return None
        hi = max(hi, end)

    points = wall.centerline_pts
    if any(not all(math.isfinite(float(v)) for v in p) for p in points):
        return None
    along = tuple(project(p, geometry.axis) for p in points)
    differences = tuple(b - a for a, b in zip(along, along[1:]))
    if (not all(d > _COORD_TOL for d in differences)
            and not all(d < -_COORD_TOL for d in differences)):
        return None
    snap = DEFAULT_GAP_SNAP_TOLERANCE_PT + _COORD_TOL
    if abs(min(along) - lo) > snap or abs(max(along) - hi) > snap:
        return None
    if any(abs(project(p, geometry.normal) - offsets[0]) > snap for p in points):
        return None
    # The source projection and the snapped path must stay inside the same
    # aperture thickness. This fallback grants no larger band allowance.
    half_band = geometry.thickness / 2.0 + _COORD_TOL
    if abs(offsets[0]) > half_band or any(
        abs(project(p, geometry.normal)) > half_band for p in points
    ):
        return None
    return lo, hi, offsets[0]
