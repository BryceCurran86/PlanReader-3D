"""Conservative source projection; no authority or publication on its own.

Only sealed wall records and authenticated raster lines may reach a producer
consumer. These geometry checks do not authenticate those inputs themselves.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pb_wall_room_topology_stage_a import DEFAULT_GAP_SNAP_TOLERANCE_PT

_COORD_TOL = 1e-6


def source_edge_axis_projection(record, geometry, source_lines: Mapping[str, Sequence[float]]):
    """Return the continuous, locally owned source interval, or unknown.

    Never extend a local edge to its ancestor's full extent, bridge a source
    gap, flatten a source bend or choose between different source offsets.
    """
    return _source_edge_axis_projection(record, geometry, source_lines, require_band=True)


def _source_edge_axis_projection(record, geometry, source_lines, *, require_band):
    """Common ancestry proof; only the public positive constrains wall-band membership."""
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
    if require_band and (abs(offsets[0]) > half_band or any(
        abs(project(p, geometry.normal)) > half_band for p in points
    )):
        return None
    return lo, hi, offsets[0]


def exact_raster_rectangle_holes(image_png: bytes, *, dpi: int):
    """Exact closed pixel rectangles, with only the raster's one-cell corners.

    These are source geometry observations, not furniture/room/wall roles.
    No polygon approximation, morphology, gap filling or nearest box selection.
    The caller must authenticate the PNG and its native page frame.
    """
    import cv2
    import numpy as np
    from pb_raster_opening_source_primitives import LINE_THRESHOLD

    if type(image_png) is not bytes or not image_png or type(dpi) is not int or dpi <= 0:
        return ()
    gray = cv2.imdecode(np.frombuffer(image_png, np.uint8), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        return ()
    contours, hierarchy = cv2.findContours(
        (gray < LINE_THRESHOLD).astype(np.uint8), cv2.RETR_TREE,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    if hierarchy is None or len(contours) > 20_000:
        return ()
    result = set()
    for index, contour in enumerate(contours):
        depth, parent = 0, int(hierarchy[0, index, 3])
        while parent >= 0:
            depth += 1
            parent = int(hierarchy[0, parent, 3])
        if depth % 2 != 1:
            continue
        x, y, width, height = cv2.boundingRect(contour)
        if min(width, height) < 4:
            continue
        right, bottom = x + width - 1, y + height - 1
        points = tuple(tuple(map(int, p)) for p in contour.reshape(-1, 2))
        square = {(x, y), (right, y), (right, bottom), (x, bottom)}
        corners = {(x, y+1), (x+1, y), (right-1, y), (right, y+1),
                   (right, bottom-1), (right-1, bottom),
                   (x+1, bottom), (x, bottom-1)}
        # All edges must be present in the original contour. A broken or
        # stepped box is never converted into a rectangle by approximation.
        if ((len(points) == 4 and set(points) == square)
                or (len(points) == 8 and set(points) == corners)):
            result.add(tuple(float(v) * 72.0 / dpi
                             for v in (x, y, right, bottom)))
    return tuple(sorted(result))


def source_equipment_border_support(
    record, geometry, source_lines, flanks, *, rectangles, words,
    image_png: bytes, full_png: bytes, dpi: int, source_equality_tolerance: float,
):
    """Pure support check; only its producer may authenticate inputs/issue an atom.

    A complete original source candidate must lie on one uniquely labelled
    equipment rectangle wholly outside, and along, a G17 solid flank. An
    actual blank source pixel row/column separates the candidate from that
    flank in BOTH original renders. This is local nonparticipation evidence;
    it does not classify physical wall equivalence or close a wall terminal.
    """
    import cv2
    import numpy as np
    from pb_raster_opening_source_primitives import MASS_THRESHOLD

    data = _source_edge_axis_projection(
        record, geometry, source_lines, require_band=False,
    )
    if data is None or type(dpi) is not int or dpi <= 0:
        return None
    lo, hi, offset = data
    axis, normal = tuple(geometry.axis), tuple(geometry.normal)
    if axis not in ((1., 0.), (-1., 0.), (0., 1.), (0., -1.)):
        return None
    if normal != (-axis[1], axis[0]):
        return None
    matching_flanks = []
    for flank in flanks.values():
        a, b, n0, n1, _jamb = flank
        if lo >= a-_COORD_TOL and hi <= b+_COORD_TOL:
            if offset < n0-_COORD_TOL or offset > n1+_COORD_TOL:
                matching_flanks.append(flank)
    if len(matching_flanks) != 1:
        return None
    flank_lo, flank_hi, n0, n1, _jamb = matching_flanks[0]
    snapped_offsets = [sum((p[i]-geometry.origin[i])*normal[i] for i in (0, 1))
                       for p in record.wall_candidate.centerline_pts]
    if (max(snapped_offsets)-min(snapped_offsets) > _COORD_TOL
            or abs(snapped_offsets[0]-offset) > source_equality_tolerance+_COORD_TOL
            or not (max(snapped_offsets) < n0-_COORD_TOL
                    or min(snapped_offsets) > n1+_COORD_TOL)):
        return None
    pixel = 72.0 / dpi
    proposals = []
    for box in rectangles:
        x0, y0, x1, y1 = box
        corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
        projected = [(
            sum((p[i]-geometry.origin[i])*axis[i] for i in (0, 1)),
            sum((p[i]-geometry.origin[i])*normal[i] for i in (0, 1)),
        ) for p in corners]
        us, ns = zip(*projected)
        if min(us) < flank_lo-_COORD_TOL or max(us) > flank_hi+_COORD_TOL:
            continue
        # Enlarge by one original pixel for the enclosing border, never
        # shrink the source-proven physical wall band to admit the symbol.
        if not (min(ns)-pixel > n1+_COORD_TOL
                or max(ns)+pixel < n0-_COORD_TOL):
            continue
        tol = source_equality_tolerance + _COORD_TOL
        if (lo < min(us)-tol or hi > max(us)+tol
                or min(abs(offset-min(ns)), abs(offset-max(ns))) > tol):
            continue
        contained = []
        uncertain = False
        for word in words:
            wx0, wy0, wx1, wy1 = word['bbox']
            intersects = (min(x1, wx1) > max(x0, wx0)+_COORD_TOL
                          and min(y1, wy1) > max(y0, wy0)+_COORD_TOL)
            if not intersects:
                continue
            if (not word['trusted'] or wx0 <= x0 or wy0 <= y0
                    or wx1 >= x1 or wy1 >= y1):
                uncertain = True
                break
            contained.append(word)
        if uncertain or not contained:
            continue
        addresses = [(w['block'], w['line'], w['word']) for w in contained]
        if (any(any(type(v) is not int for v in address) for address in addresses)
                or len(set(addresses)) != len(addresses)
                or len({a[:2] for a in addresses}) != 1):
            continue
        ordered = sorted(contained, key=lambda w: w['word'])
        if ([w['word'] for w in ordered] != list(range(
                ordered[0]['word'], ordered[0]['word']+len(ordered)))
                or ' '.join(w['text'].strip().upper() for w in ordered)
                    not in ('AC UNIT', 'A/C UNIT')):
            continue
        proposals.append((tuple(box), tuple(sorted(w['id'] for w in ordered)),
                          tuple(sorted(w['receipt'] for w in ordered))))
    # Source candidates and labelled rectangles remain rivals. No first,
    # nearest, smallest or duplicate-provenance label election is permitted.
    if len(proposals) != 1:
        return None
    if any(type(png) is not bytes or not png for png in (image_png, full_png)):
        return None
    images = [cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
              for png in (image_png, full_png)]
    if any(im is None for im in images) or images[0].shape != images[1].shape:
        return None
    boundary = n0 if offset < n0 else n1
    points = [tuple(geometry.origin[i] + u*axis[i] + n*normal[i]
                    for i in (0, 1))
              for u in (lo, hi) for n in (boundary, offset)]
    xs, ys = zip(*points)
    x0, x1 = math.ceil(min(xs)/pixel), math.floor(max(xs)/pixel)
    y0, y1 = math.ceil(min(ys)/pixel), math.floor(max(ys)/pixel)
    # Work only on real pixel centres strictly between the two source lines.
    if axis[0]:
        y0, y1 = math.floor(min(ys)/pixel)+1, math.ceil(max(ys)/pixel)-1
    else:
        x0, x1 = math.floor(min(xs)/pixel)+1, math.ceil(max(xs)/pixel)-1
    if (x0 < 0 or y0 < 0 or x1 < x0 or y1 < y0
            or x1 >= images[0].shape[1] or y1 >= images[0].shape[0]):
        return None
    equal = images[0][y0:y1+1, x0:x1+1] == images[1][y0:y1+1, x0:x1+1]
    clear = equal & (images[0][y0:y1+1, x0:x1+1] >= MASS_THRESHOLD)
    if not np.any(np.all(clear, axis=1 if axis[0] else 0)):
        return None
    return proposals[0]


@dataclass(frozen=True)
class SourceClosedPierFaceChain:
    """Verified *local source faces*, not W4 equivalence or a whole-wall frame.

    The caller must have authenticated `source_lines` and the G17 source
    flank with the original SourceVisibilityProducer before using this
    observation. This is deliberately not a QuantityEvidence issuer.
    """

    face_wall_ids: tuple[tuple[str, ...], tuple[str, ...]]
    face_edge_ids: tuple[tuple[str, ...], tuple[str, ...]]
    face_primitive_ids: tuple[tuple[str, ...], tuple[str, ...]]
    right_flank_interval_pt: tuple[float, float]
    wall_face_offsets_pt: tuple[float, float]


def source_closed_pier_face_chains(
    records,
    geometry,
    source_lines: Mapping[str, Sequence[float]],
    right_flank,
) -> SourceClosedPierFaceChain | None:
    """Prove complete opposing original ink chains for one G17 right flank.

    The flank must come from independently authenticated two-face G17 source
    ink and its right jamb endcap. Every participating W2 edge has to pass
    `source_edge_axis_projection`, including exact source-parent containment.
    All intervals on each face must cover the full original flank continuously
    without snap-bridged gaps, overlaps, skipped fragments, or a competing
    aligned offset. A positive remains **local face evidence only**; the
    full physical wall, terminal beyond this flank, and installed quantity
    retain their separate source authority gates.
    """
    try:
        lo, hi, low_face, high_face, jamb = tuple(float(x) for x in right_flank)
        thickness = float(geometry.thickness)
        opening_length = float(geometry.length)
    except (TypeError, ValueError, OverflowError, AttributeError):
        return None
    if not all(math.isfinite(v) for v in (lo, hi, low_face, high_face, jamb,
                                           thickness, opening_length)):
        return None
    if (hi - lo <= _COORD_TOL or high_face-low_face <= _COORD_TOL
            or thickness <= _COORD_TOL or opening_length <= _COORD_TOL
            or abs(lo - jamb) > _COORD_TOL
            or abs(jamb-opening_length) > _COORD_TOL
            or abs((high_face-low_face)-thickness) > _COORD_TOL
            or not (low_face < 0.0 < high_face)):
        return None

    faces: list[list[tuple[float, float, str, tuple[str, ...], tuple[str, ...]]]] = [[], []]
    seen_walls: set[str] = set()
    seen_edges: set[str] = set()
    for record in tuple(records):
        wall_id = str(getattr(record, "wall_candidate_id", ""))
        fragments = tuple(getattr(record, "source_edge_fragments", ()) or ())
        if not wall_id or wall_id in seen_walls:
            return None
        seen_walls.add(wall_id)
        if not fragments:
            # A source-less W4 wall overlapping this local aperture flank
            # remains a real rival. Never treat it as absent evidence.
            try:
                points=tuple(record.wall_candidate.centerline_pts)
                local_wall=False
                for p0,p1 in zip(points,points[1:]):
                    u0=sum((float(p0[i])-geometry.origin[i])*geometry.axis[i]
                           for i in (0,1))
                    u1=sum((float(p1[i])-geometry.origin[i])*geometry.axis[i]
                           for i in (0,1))
                    n0=sum((float(p0[i])-geometry.origin[i])*geometry.normal[i]
                           for i in (0,1))
                    n1=sum((float(p1[i])-geometry.origin[i])*geometry.normal[i]
                           for i in (0,1))
                    if (min(hi,max(u0,u1))-max(lo,min(u0,u1))>_COORD_TOL
                            and min(n0,n1)<=thickness/2.0+_COORD_TOL
                            and max(n0,n1)>=-thickness/2.0-_COORD_TOL):
                        local_wall=True
                        break
            except (AttributeError,TypeError,ValueError,OverflowError,IndexError):
                return None
            if local_wall:
                return None
            continue
        # A candidate overlapping the sealed local source band cannot vanish
        # because its W2 path is malformed or its parent was not re-proved.
        local = False
        for fragment in fragments:
            try:
                line = tuple(float(value) for value in fragment.geometry)
                if len(line) != 4 or not all(math.isfinite(v) for v in line):
                    return None
                origin = geometry.origin
                axis = geometry.axis
                normal = geometry.normal
                p0 = (line[0]-origin[0], line[1]-origin[1])
                p1 = (line[2]-origin[0], line[3]-origin[1])
                u0, u1 = (p0[0]*axis[0]+p0[1]*axis[1],
                          p1[0]*axis[0]+p1[1]*axis[1])
                n0, n1 = (p0[0]*normal[0]+p0[1]*normal[1],
                          p1[0]*normal[0]+p1[1]*normal[1])
            except (TypeError, ValueError, OverflowError, AttributeError, IndexError):
                return None
            if (min(hi,max(u0,u1))-max(lo,min(u0,u1)) > _COORD_TOL
                    and min(n0,n1) <= thickness/2.0+_COORD_TOL
                    and max(n0,n1) >= -thickness/2.0-_COORD_TOL):
                local = True
        if not local:
            continue
        projection = source_edge_axis_projection(record, geometry, source_lines)
        if projection is None:
            return None
        start, end, offset = projection
        if end <= lo + _COORD_TOL or start >= hi-_COORD_TOL:
            continue
        if start < lo-_COORD_TOL or end > hi+_COORD_TOL:
            # Parent ink cannot be clipped down to an aperture-friendly size.
            return None
        if abs(offset - low_face) <= _COORD_TOL:
            face_index = 0
        elif abs(offset - high_face) <= _COORD_TOL:
            face_index = 1
        else:
            return None
        edge_ids = tuple(str(fragment.edge_id) for fragment in fragments)
        if any(not edge or edge in seen_edges for edge in edge_ids):
            return None
        seen_edges.update(edge_ids)
        primitive_ids = tuple(sorted(str(x) for x in
                              record.physical_identity.source_primitive_ids))
        if not primitive_ids or any(not p for p in primitive_ids):
            return None
        faces[face_index].append((start, end, wall_id,
                                  tuple(sorted(edge_ids)), primitive_ids))

    face_walls = []
    face_edges = []
    face_primitives = []
    for group in faces:
        if not group:
            return None
        ordered = sorted(group, key=lambda item: (item[0], item[1], item[2]))
        if abs(ordered[0][0]-lo) > _COORD_TOL:
            return None
        limit = lo
        for start, end, *_rest in ordered:
            # An overlap also abstains: it might be duplicate source ink or a
            # second competing physical face and cannot be silently elected.
            if abs(start-limit) > _COORD_TOL or end <= start+_COORD_TOL:
                return None
            limit = end
        if abs(limit-hi) > _COORD_TOL:
            return None
        face_walls.append(tuple(sorted(item[2] for item in ordered)))
        face_edges.append(tuple(sorted(x for item in ordered for x in item[3])))
        face_primitives.append(tuple(sorted({x for item in ordered for x in item[4]})))
    if set(face_primitives[0]) & set(face_primitives[1]):
        return None
    return SourceClosedPierFaceChain(
        face_wall_ids=(face_walls[0], face_walls[1]),
        face_edge_ids=(face_edges[0], face_edges[1]),
        face_primitive_ids=(face_primitives[0], face_primitives[1]),
        right_flank_interval_pt=(lo, hi),
        wall_face_offsets_pt=(low_face, high_face),
    )
