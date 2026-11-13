"""Doorway-closed room rings as a ``SourceRoomFaceScopeResult`` (SHADOW ONLY, default-off).

``pb_layered_wall_doorway_room_ring_shadow`` finds rooms enclosed by layered native wall ink
plus source-attested doorway closures. This module only re-expresses those rings in the
EXISTING room-face vocabulary so the unchanged downstream chain (room labels, canonical
rooms and floors, the area bridge) can consume them:

* a CANDIDATE ring becomes a ``SourceRoomFaceRecord`` whose wall edges are owned by wall strips
  (native path index). A doorway closure is a planarization chord only: it is NEVER listed as a
  wall owner (not in ``bounding_wall_ids``, not in ``boundary_wall_edges``), so it cannot become
  wall length, a host or an opening deduction. A chord edge is exactly a polygon edge that has no
  wall owner; its identity is bound into the record id. In the live
  path a ring is a record only if EXACTLY ONE authenticated figured (horizontal, vertical)
  pair has the ring's bounding box as its witness box: a closed ring that no printed figure
  corroborates (for example a region that leaks through openings with no closure evidence)
  stays an abstention and can never be measured as a room;
* a ring that stays open, or is not so corroborated, becomes a ``SourceRoomFaceAbstention``;
* the scope is always partial (``source_room_face_universe_partial``): a ring scope never
  claims the face universe, and it carries ``LAYERED_RING_SCOPE_REASON`` so a consumer can
  tell the provenance.

It never reads or changes the W2/W4 wall scope that walls and openings use. It issues no
scale, area, finish or quantity.
"""
from __future__ import annotations

import math
from typing import Mapping, Optional, Sequence

from shapely.geometry import LineString, Polygon
from shapely.geometry import box as shapely_box

from pb_layered_wall_doorway_partition_witness_shadow import partition_groups
from pb_layered_wall_doorway_room_ring_shadow import (
    NOISE_PT,
    _DARK_FILL_THICK_MAX,
    LayeredRoomRingRecord,
    LayeredRoomRingResult,
    _orthogonal_wall_fill_strips,
    _runs,
    build_from_pdf_bytes,
)
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_source_room_face_authority import (
    SCOPE_OVERRIDE_SEAL,
    SOURCE_ROOM_FACE_BOUNDARY_UNRESOLVED,
    SOURCE_ROOM_FACE_SCOPE_RESOLVED,
    SOURCE_ROOM_FACE_UNIVERSE_PARTIAL,
    SourceRoomFaceAbstention,
    SourceRoomFaceRecord,
    SourceRoomFaceScopeOverride,
    SourceRoomFaceScopeResult,
    _canonical_polygon,
    _edge,
    _polygon_area,
    scope_override_digest,
)

LAYERED_RING_SCOPE_REASON = "layered_wall_doorway_room_ring_scope"
# Per-record token: the face is not its own bounding rectangle (a wall return, an alcove split off by a
# closure). A bounding box may corroborate the topology; it can never set such a face's metric area.
RING_NOT_A_RECTANGLE_PREFIX = "layered_ring_not_a_rectangle:"
# Distinct provenance for the opt-in sliding-leaf partition witness: the scope still never claims the face
# universe, and a part is corroborated only by its group's union envelope, never by its own box.
LAYERED_RING_PARTITION_REASON = "layered_wall_doorway_room_ring_partition_witness"
RING_PARTITION_PART_PREFIX = "layered_ring_partition_part:"
# Opt-in finished-face gate: a ring follows the DRAWN wall face. Unless the original establishes that this is the
# exposed finished face, the face is a noncommercial candidate: no documented area, no room-area quantity.
LAYERED_RING_FINISHED_FACE_GATE_REASON = "layered_wall_doorway_room_ring_finished_face_gate"
RING_FINISHED_FACE_REQUIRED_PREFIX = "layered_ring_finished_face_required:"
# Witness line to drawn face: representation noise, far below the 2.5 pt production snap, a hard bound.
RING_FIGURED_BOX_TOLERANCE_PT = 0.5
# Collinear hashed figures on one dimension line. Not the 2.5 pt production snap.
RING_CHAIN_LINE_PT = 2.0
# Printed millimetres of an overall figure vs the sum of hashed parts on that run.
RING_CHAIN_MM_AGREE = 1.0
# A figured tick may land through the thickness of the wall that owns that inner face
# (frame face vs lining face of the same strip). Never the 2.5 pt production snap.
RING_OWNING_WALL_THICKNESS_MAX_PT = _DARK_FILL_THICK_MAX
# The decision scope the live room composition resolves per page (``wall-source:page-N``).
_PAGE_DECISION_SCOPE = "wall-source:page-{page_id}"
_CLOSURE_OWNER_PREFIX = "layered_doorway_closure:"


def _face_ids(ring: LayeredRoomRingRecord, polygon: tuple, *, scope: Sequence[str]) -> tuple[str, dict]:
    payload = {
        "document_id": scope[0], "revision_id": scope[1], "source_sha256": scope[2],
        "snapshot_id": scope[3], "page_id": scope[4], "decision_scope_id": scope[5],
        "polygon": polygon,
    }
    return stable_contract_id("layered_ring_source_room_face", payload, digest_chars=32), payload


def _boundary_edges(ring: LayeredRoomRingRecord) -> tuple[tuple[str, tuple], ...]:
    points = ring.polygon_pdf_pts
    edges = [(points[i], points[(i + 1) % len(points)]) for i in range(len(points))]
    owners = ring.edge_owner_ids if len(ring.edge_owner_ids) == len(edges) else tuple(() for _ in edges)
    pairs: list[tuple[str, tuple]] = []
    for (first, second), edge_owners in zip(edges, owners):
        for owner in edge_owners:
            if owner.startswith(_CLOSURE_OWNER_PREFIX):
                continue  # a doorway chord is not a wall: no wall owner is ever recorded for it
            pairs.append((owner, _edge(first, second)))
    return tuple(pairs)


def _figured_span_token(dimension: object, span: tuple[float, float]) -> object:
    """Identity of one printed figure on a span: millimetres, else text, else the span itself.

    Parallel copies of the same ticks are one figure. Distinct observation ids of that same
    span are not competing pairs. Two different millimetre values on one span are a conflict.
    """
    millimetres = _dimension_mm(dimension)
    if millimetres is not None:
        return ("mm", millimetres)
    text = getattr(dimension, "raw_text", None) or getattr(dimension, "text", None)
    if text is not None:
        return ("text", str(text))
    return ("span", span)


def _face_mid_on_inner(
    polygon: Sequence[Sequence[float]], inner: float, *, vertical_face: bool,
) -> Optional[float]:
    """Midpoint along the inner face, or None when that face is not drawn."""
    other: list[float] = []
    points = [(float(p[0]), float(p[1])) for p in polygon]
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        if vertical_face:
            if abs(start[0] - inner) <= NOISE_PT * 2 and abs(end[0] - inner) <= NOISE_PT * 2:
                other.extend((start[1], end[1]))
        elif abs(start[1] - inner) <= NOISE_PT * 2 and abs(end[1] - inner) <= NOISE_PT * 2:
            other.extend((start[0], end[0]))
    if not other:
        return None
    return (min(other) + max(other)) / 2.0


def _extent_through_owning_wall(
    extent: float,
    inner: float,
    face_polygon: Sequence[Sequence[float]],
    *,
    vertical_face: bool,
    toward_min: bool,
    tolerance_pt: float,
) -> bool:
    """True when ``extent`` is the inner face, or through the wall that owns that face.

    Exterior-side only, and only as far as a source wall strip can be thick. A tick
    inside the room, on a neighbour's far wall, or past the strip-thickness cap is not
    this face's witness.
    """
    if abs(extent - inner) <= tolerance_pt:
        return True
    if toward_min:
        if extent > inner + tolerance_pt:
            return False
    elif extent < inner - tolerance_pt:
        return False
    if abs(extent - inner) > RING_OWNING_WALL_THICKNESS_MAX_PT:
        return False
    mid = _face_mid_on_inner(face_polygon, inner, vertical_face=vertical_face)
    if mid is None:
        return False
    try:
        face = Polygon([(float(p[0]), float(p[1])) for p in face_polygon])
        if not face.is_valid or face.is_empty:
            return False
        if vertical_face:
            line = LineString([(extent, mid), (inner, mid)])
        else:
            line = LineString([(mid, extent), (mid, inner)])
        # A tick through the owning wall stays outside the room interior.
        return not face.buffer(-NOISE_PT, join_style=2).intersects(line)
    except (TypeError, ValueError):
        return False


def _span_witnesses_box(
    span: tuple[float, float],
    inner_lo: float,
    inner_hi: float,
    *,
    vertical_faces: bool,
    face_polygon: Optional[Sequence[Sequence[float]]],
    tolerance_pt: float,
) -> bool:
    if face_polygon is None:
        return abs(span[0] - inner_lo) <= tolerance_pt and abs(span[1] - inner_hi) <= tolerance_pt
    return (
        _extent_through_owning_wall(
            span[0], inner_lo, face_polygon,
            vertical_face=vertical_faces, toward_min=True, tolerance_pt=tolerance_pt,
        )
        and _extent_through_owning_wall(
            span[1], inner_hi, face_polygon,
            vertical_face=vertical_faces, toward_min=False, tolerance_pt=tolerance_pt,
        )
    )


def _witness_spans_for_axis(
    dimensions: Sequence[object],
    *,
    orientation: str,
    inner_lo: float,
    inner_hi: float,
    vertical_faces: bool,
    face_polygon: Optional[Sequence[Sequence[float]]],
    tolerance_pt: float,
) -> dict[tuple[float, float], set[object]]:
    """Inner-face spans if any exist on this axis; else ticks through the owning walls.

    An outer/frame figure does not compete with a unique inner-face figure of the
    same axis. Through-wall matching is only the fallback when the inner face has
    no printed tick.
    """
    inner: dict[tuple[float, float], set[object]] = {}
    through: dict[tuple[float, float], set[object]] = {}
    for dimension in dimensions:
        if dimension.orientation != orientation:  # type: ignore[attr-defined]
            continue
        ends = _dimension_endpoints_pt(dimension)
        if ends is None:
            continue
        (ax, ay), (bx, by) = ends
        if _rail_mid(ends, vertical_faces=vertical_faces) is None:
            continue
        span = tuple(sorted((float(ax), float(bx)) if vertical_faces else (float(ay), float(by))))
        token = _figured_span_token(dimension, span)
        if _span_witnesses_box(
            span, inner_lo, inner_hi, vertical_faces=vertical_faces,
            face_polygon=None, tolerance_pt=tolerance_pt,
        ):
            inner.setdefault(span, set()).add(token)
        elif face_polygon is not None and _span_witnesses_box(
            span, inner_lo, inner_hi, vertical_faces=vertical_faces,
            face_polygon=face_polygon, tolerance_pt=tolerance_pt,
        ):
            through.setdefault(span, set()).add(token)
    return inner if inner else through


def _dimension_mm(dimension: object) -> Optional[float]:
    unit = str(getattr(dimension, "unit", "mm") or "mm").lower()
    for attr in ("value_mm", "value"):
        raw = getattr(dimension, attr, None)
        if raw is None:
            continue
        try:
            millimetres = float(raw)
        except (TypeError, ValueError):
            continue
        if attr == "value" and unit == "m":
            millimetres *= 1000.0
        if math.isfinite(millimetres) and millimetres > 0.0:
            return millimetres
    return None


def _dimension_endpoints_pt(
    dimension: object,
) -> Optional[tuple[tuple[float, float], tuple[float, float]]]:
    raw = getattr(dimension, "endpoints_pt", None)
    if raw is None:
        raw = getattr(dimension, "endpoints", None)
    try:
        (ax, ay), (bx, by) = raw  # type: ignore[misc]
        return (float(ax), float(ay)), (float(bx), float(by))
    except (TypeError, ValueError):
        return None


def _rail_mid(
    ends: tuple[tuple[float, float], tuple[float, float]],
    *,
    vertical_faces: bool,
) -> Optional[float]:
    """Perpendicular coordinate of one dimension rail, or None if the two hashes are not on it."""
    (ax, ay), (bx, by) = ends
    first = float(ay) if vertical_faces else float(ax)
    second = float(by) if vertical_faces else float(bx)
    if not math.isfinite(first) or not math.isfinite(second):
        return None
    if abs(first - second) > RING_CHAIN_LINE_PT:
        return None
    return (first + second) / 2.0


def _chain_line_key(dimension: object, *, vertical_faces: bool) -> Optional[float]:
    """Return the actual rail coordinate, never an origin-dependent grid bin."""
    ends = _dimension_endpoints_pt(dimension)
    if ends is None:
        return None
    return _rail_mid(ends, vertical_faces=vertical_faces)


def _chain_rail_groups(
    entries: Sequence[tuple[float, float, float, float]],
    *,
    tolerance_pt: float,
) -> tuple[tuple[tuple[float, float, float, float], ...], ...]:
    """Group nearby rails only where their figured spans overlap or abut.

    Connected components retain ambiguous transitive matches; callers reject
    components whose complete rail spread exceeds the existing rail tolerance.
    Sorting and exact duplicate removal make grouping input-order independent.
    Nothing is snapped and unrelated figures outside a run cannot move its rail.
    """
    ordered = sorted(set(entries))
    parents = list(range(len(ordered)))

    def root(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for index, (rail, lo, hi, _mm) in enumerate(ordered):
        for other in range(index + 1, len(ordered)):
            other_rail, other_lo, other_hi, _other_mm = ordered[other]
            if other_rail - rail > RING_CHAIN_LINE_PT:
                break
            if lo <= other_hi + tolerance_pt and other_lo <= hi + tolerance_pt:
                first, second = root(index), root(other)
                if first != second:
                    parents[second] = first
    groups: dict[int, list[tuple[float, float, float, float]]] = {}
    for index, entry in enumerate(ordered):
        groups.setdefault(root(index), []).append(entry)
    return tuple(tuple(group) for group in groups.values())


def _hits_matching_hash(
    extent: float,
    inner: float,
    *,
    vertical_faces: bool,
    toward_min: bool,
    face_polygon: Optional[Sequence[Sequence[float]]],
    tolerance_pt: float,
) -> bool:
    if abs(extent - inner) <= tolerance_pt:
        return True
    if face_polygon is None:
        return False
    return _extent_through_owning_wall(
        extent, inner, face_polygon,
        vertical_face=vertical_faces, toward_min=toward_min, tolerance_pt=tolerance_pt,
    )


def _walk_hashed_parts(
    parts: Sequence[tuple[float, float, float]],
    inner_lo: float,
    inner_hi: float,
    *,
    vertical_faces: bool,
    face_polygon: Optional[Sequence[Sequence[float]]],
    tolerance_pt: float,
) -> Optional[float]:
    """Sum unique abutting parts from the matching start hash to the matching end hash."""
    if not parts:
        return None
    used: list[tuple[float, float, float]] = []
    position = inner_lo
    remaining = list(parts)
    while position < inner_hi - tolerance_pt:
        if not used:
            nxt = [
                part for part in remaining
                if _hits_matching_hash(
                    part[0], inner_lo, vertical_faces=vertical_faces, toward_min=True,
                    face_polygon=face_polygon, tolerance_pt=tolerance_pt,
                )
            ]
        else:
            nxt = [part for part in remaining if abs(part[0] - position) <= tolerance_pt]
        nxt = [part for part in nxt if part[1] > position + tolerance_pt]
        if len(nxt) != 1:
            return None
        part = nxt[0]
        used.append(part)
        remaining.remove(part)
        position = part[1]
    if not used:
        return None
    last = used[-1]
    if not _hits_matching_hash(
        last[1], inner_hi, vertical_faces=vertical_faces, toward_min=False,
        face_polygon=face_polygon, tolerance_pt=tolerance_pt,
    ):
        return None
    return sum(part[2] for part in used)


def _unique_hashed_chain_mm(
    dimensions: Sequence[object],
    *,
    orientation: str,
    inner_lo: float,
    inner_hi: float,
    vertical_faces: bool,
    face_polygon: Optional[Sequence[Sequence[float]]],
    tolerance_pt: float,
) -> Optional[float]:
    """Unique sum of collinear hashed parts between two matching wall hashes, or None.

    Both end hashes must sit on the same dimension rail. Nested hashes on that
    rail add. An overall figure that already spans both hashes is not added again.
    Two disagreeing sums abstain. A gap, overlap, or fork abstains. A hash on a
    different rail is a different chain.
    """
    entries: list[tuple[float, float, float, float]] = []
    for dimension in dimensions:
        if dimension.orientation != orientation:  # type: ignore[attr-defined]
            continue
        millimetres = _dimension_mm(dimension)
        if millimetres is None:
            continue
        ends = _dimension_endpoints_pt(dimension)
        if ends is None:
            continue
        if _rail_mid(ends, vertical_faces=vertical_faces) is None:
            continue
        (ax, ay), (bx, by) = ends
        span = tuple(sorted((float(ax), float(bx)) if vertical_faces else (float(ay), float(by))))
        if span[1] - span[0] <= tolerance_pt:
            continue
        # A single figure that already spans both matching hashes is the overall,
        # not a part to add.
        if _span_witnesses_box(
            span, inner_lo, inner_hi, vertical_faces=vertical_faces,
            face_polygon=face_polygon, tolerance_pt=tolerance_pt,
        ):
            continue
        # Parts live strictly between the matching hashes (ends may sit in the wall).
        if span[0] < inner_lo - RING_OWNING_WALL_THICKNESS_MAX_PT:
            continue
        if span[1] > inner_hi + RING_OWNING_WALL_THICKNESS_MAX_PT:
            continue
        if span[0] > inner_hi - tolerance_pt or span[1] < inner_lo + tolerance_pt:
            continue
        key = _chain_line_key(dimension, vertical_faces=vertical_faces)
        if key is None:
            continue
        entries.append((key, span[0], span[1], millimetres))
    sums: set[float] = set()
    for group in _chain_rail_groups(entries, tolerance_pt=tolerance_pt):
        rails = [entry[0] for entry in group]
        if max(rails) - min(rails) > RING_CHAIN_LINE_PT:
            return None
        parts = sorted({(lo, hi, mm) for _rail, lo, hi, mm in group})
        hashes = [extent for part in parts for extent in (part[0], part[1])]
        start_hits = [
            extent for extent in hashes
            if _hits_matching_hash(
                extent, inner_lo, vertical_faces=vertical_faces, toward_min=True,
                face_polygon=face_polygon, tolerance_pt=tolerance_pt,
            )
        ]
        end_hits = [
            extent for extent in hashes
            if _hits_matching_hash(
                extent, inner_hi, vertical_faces=vertical_faces, toward_min=False,
                face_polygon=face_polygon, tolerance_pt=tolerance_pt,
            )
        ]
        if not start_hits or not end_hits:
            continue
        # Overlays that contain a shorter part on this line are overalls of a sub-run, not addends.
        addends = [
            part for part in parts
            if not any(
                other[0] >= part[0] - tolerance_pt
                and other[1] <= part[1] + tolerance_pt
                and (other[1] - other[0]) < (part[1] - part[0]) - tolerance_pt
                for other in parts
                if other != part
            )
        ]
        # A containing figure is a redundant sub-run overall only when
        # the retained parts actually cover it and agree. Otherwise it is a
        # competing branch, not a figure that can be silently discarded.
        for overall in parts:
            if overall in addends:
                continue
            contained = [
                part for part in addends
                if part[0] >= overall[0] - tolerance_pt
                and part[1] <= overall[1] + tolerance_pt
            ]
            subtotal = _walk_hashed_parts(
                contained, overall[0], overall[1], vertical_faces=vertical_faces,
                face_polygon=None, tolerance_pt=tolerance_pt,
            )
            if subtotal is None or abs(subtotal - overall[2]) > RING_CHAIN_MM_AGREE:
                return None
        walked = _walk_hashed_parts(
            addends, inner_lo, inner_hi, vertical_faces=vertical_faces,
            face_polygon=face_polygon, tolerance_pt=tolerance_pt,
        )
        if walked is not None:
            sums.add(round(walked, 3))
    if len(sums) != 1:
        return None
    return next(iter(sums))


def _with_hashed_chain(
    spans: Mapping[tuple[float, float], set[object]],
    dimensions: Sequence[object],
    *,
    orientation: str,
    inner_lo: float,
    inner_hi: float,
    vertical_faces: bool,
    face_polygon: Optional[Sequence[Sequence[float]]],
    tolerance_pt: float,
) -> dict[tuple[float, float], set[object]]:
    chain_mm = _unique_hashed_chain_mm(
        dimensions, orientation=orientation, inner_lo=inner_lo, inner_hi=inner_hi,
        vertical_faces=vertical_faces, face_polygon=face_polygon, tolerance_pt=tolerance_pt,
    )
    if not spans:
        if chain_mm is None:
            return dict(spans)
        return {(float(inner_lo), float(inner_hi)): {("chain_mm", chain_mm)}}
    if chain_mm is None:
        return dict(spans)
    covering_mm = [
        round(float(token[1]), 3)
        for tokens in spans.values()
        for token in tokens
        if isinstance(token, tuple) and token[0] == "mm"
    ]
    if not covering_mm:
        return dict(spans)
    if any(abs(millimetres - chain_mm) > RING_CHAIN_MM_AGREE for millimetres in covering_mm):
        conflict = dict(spans)
        extra = (float(inner_lo) - 1.0, float(inner_hi))
        while extra in conflict:
            extra = (extra[0] - 1.0, extra[1])
        conflict[extra] = {("chain_mm", chain_mm)}
        return conflict
    return dict(spans)


def _same_rail_hash_pairs(
    dimensions: Sequence[object],
    *,
    orientation: str,
    tolerance_pt: float,
) -> tuple[tuple[int, float, float, float], ...]:
    """Unique two-hash figures grouped by actual source collinearity."""
    vertical_faces = orientation == "horizontal"
    entries: list[tuple[float, float, float, float]] = []
    for dimension in dimensions:
        if dimension.orientation != orientation:  # type: ignore[attr-defined]
            continue
        millimetres = _dimension_mm(dimension)
        ends = _dimension_endpoints_pt(dimension)
        if millimetres is None or ends is None:
            continue
        key = _chain_line_key(dimension, vertical_faces=vertical_faces)
        if key is None:
            continue
        (ax, ay), (bx, by) = ends
        lo, hi = sorted((float(ax), float(bx)) if vertical_faces else (float(ay), float(by)))
        if hi - lo <= tolerance_pt:
            continue
        entries.append((key, round(lo, 3), round(hi, 3), round(millimetres, 3)))
    by_span: dict[tuple[int, float, float], set[float]] = {}
    for group_id, group in enumerate(_chain_rail_groups(entries, tolerance_pt=tolerance_pt)):
        rails = [entry[0] for entry in group]
        if max(rails) - min(rails) > RING_CHAIN_LINE_PT:
            continue
        for _rail, lo, hi, millimetres in group:
            by_span.setdefault((group_id, lo, hi), set()).add(millimetres)
    pairs: list[tuple[int, float, float, float]] = []
    for (rail, lo, hi), values in by_span.items():
        if len(values) != 1:
            continue
        pairs.append((rail, lo, hi, next(iter(values))))
    return tuple(pairs)


def _run_carries_hash_pair(
    run_lo: float,
    run_hi: float,
    hash_lo: float,
    hash_hi: float,
    *,
    tolerance_pt: float,
) -> bool:
    """True when both hashes of one rail sit on this traced wall run."""
    if hash_hi - hash_lo <= tolerance_pt:
        return False
    thickness = RING_OWNING_WALL_THICKNESS_MAX_PT
    return (
        hash_lo >= run_lo - thickness
        and hash_hi <= run_hi + thickness
        and (run_hi - run_lo) + 2.0 * thickness >= hash_hi - hash_lo
    )


def _polygon_has_oriented_return_at_extent(
    polygon: Optional[Sequence[Sequence[float]]],
    *,
    orientation: str,
    extent: float,
    tolerance_pt: float,
) -> bool:
    """True when a wall of this orientation in the room turns at ``extent``.

    Opposite walls share one two-hash figure, so the robe return may sit on
    only one of the two parallel walls.
    """
    if polygon is None:
        return False
    points = [(float(point[0]), float(point[1])) for point in polygon]
    for index, start in enumerate(points):
        axis = _axis_aligned_edge(start, points[(index + 1) % len(points)])
        if axis is None or axis[0] != orientation:
            continue
        _orientation, lo, hi, _line_key = axis
        if abs(lo - extent) <= tolerance_pt or abs(hi - extent) <= tolerance_pt:
            return True
    return False


def _shared_inner_hash_millimetres(
    run_lo: float,
    run_hi: float,
    *,
    orientation: str,
    pairs: Sequence[tuple[int, float, float, float]],
    face_polygon: Optional[Sequence[Sequence[float]]],
    full: Optional[float],
    tolerance_pt: float,
) -> tuple[float, ...]:
    """Shorter same-rail walls that share one end hash with this run.

    Opposite walls of the same length share one two-hash figure. A 3600 mm
    inner pair on a longer 4200 mm robe-inclusive run is that bedroom wall,
    not an addend of 4200. Nested parts of this run's own rail stay addends
    of ``full``. The interior hash must land on a return of this wall.
    """
    extras: list[float] = []
    vertical_faces = orientation == "horizontal"
    for rail, hash_lo, hash_hi, millimetres in pairs:
        if not _run_carries_hash_pair(run_lo, run_hi, hash_lo, hash_hi, tolerance_pt=tolerance_pt):
            continue
        interior_lo = run_lo + tolerance_pt < hash_lo < run_hi - tolerance_pt
        interior_hi = run_lo + tolerance_pt < hash_hi < run_hi - tolerance_pt
        end_lo = _hits_matching_hash(
            hash_lo, run_lo, vertical_faces=vertical_faces, toward_min=True,
            face_polygon=face_polygon, tolerance_pt=tolerance_pt,
        )
        end_hi = _hits_matching_hash(
            hash_hi, run_hi, vertical_faces=vertical_faces, toward_min=False,
            face_polygon=face_polygon, tolerance_pt=tolerance_pt,
        )
        if not ((end_lo and interior_hi) or (end_hi and interior_lo)):
            continue
        interior_extent = hash_lo if interior_lo else hash_hi
        if not _polygon_has_oriented_return_at_extent(
            face_polygon, orientation=orientation,
            extent=interior_extent, tolerance_pt=tolerance_pt,
        ):
            continue
        rail_parts = [
            (part_lo, part_hi, part_mm)
            for part_rail, part_lo, part_hi, part_mm in pairs
            if part_rail == rail
        ]
        walked = _walk_hashed_parts(
            rail_parts, run_lo, run_hi, vertical_faces=vertical_faces,
            face_polygon=face_polygon, tolerance_pt=tolerance_pt,
        )
        if (
            full is not None
            and walked is not None
            and abs(walked - full) <= RING_CHAIN_MM_AGREE
        ):
            continue
        extras.append(millimetres)
    return tuple(extras)


def figured_box_pair_count(
    bounding_box: Sequence[float], dimensions: Sequence[object], *,
    tolerance_pt: float = RING_FIGURED_BOX_TOLERANCE_PT,
    face_polygon: Optional[Sequence[Sequence[float]]] = None,
) -> int:
    """How many authenticated (horizontal, vertical) figured pairs have exactly this witness box.

    Uniqueness is the geometric span (and printed millimetres when present), not observation
    id: two parallel prints of the same ticks are one figure. A span that carries two
    disagreeing millimetre values is competing, not unique.

    ``face_polygon`` (optional): a tick may also land through the thickness of the wall
    that owns that inner face, but only on an axis that has no inner-face tick. It is
    never snapped, never nearest, and never inside the room.

    When two hashes on the same rail match that wall and other hashes sit between
    them on that rail, the unique collinear chain of those parts is one length
    (their millimetres add). An overall figure of the same run is not added again;
    a disagreeing overall abstains. Hashes on a different rail are a different chain.
    """
    horizontal, vertical = _figured_axis_spans(
        bounding_box, dimensions, tolerance_pt=tolerance_pt, face_polygon=face_polygon,
    )

    def _unique_spans(store: Mapping[tuple[float, float], set[object]]) -> int | None:
        if any(len(tokens) > 1 for tokens in store.values()):
            return None
        return len(store)

    n_horizontal = _unique_spans(horizontal)
    n_vertical = _unique_spans(vertical)
    if n_horizontal is None or n_vertical is None:
        return 2
    return n_horizontal * n_vertical


def _figured_axis_spans(
    bounding_box: Sequence[float], dimensions: Sequence[object], *,
    tolerance_pt: float,
    face_polygon: Optional[Sequence[Sequence[float]]],
) -> tuple[dict[tuple[float, float], set[object]], dict[tuple[float, float], set[object]]]:
    x0, y0, x1, y1 = bounding_box
    horizontal = _with_hashed_chain(
        _witness_spans_for_axis(
            dimensions, orientation="horizontal", inner_lo=x0, inner_hi=x1,
            vertical_faces=True, face_polygon=face_polygon, tolerance_pt=tolerance_pt,
        ),
        dimensions, orientation="horizontal", inner_lo=x0, inner_hi=x1,
        vertical_faces=True, face_polygon=face_polygon, tolerance_pt=tolerance_pt,
    )
    vertical = _with_hashed_chain(
        _witness_spans_for_axis(
            dimensions, orientation="vertical", inner_lo=y0, inner_hi=y1,
            vertical_faces=False, face_polygon=face_polygon, tolerance_pt=tolerance_pt,
        ),
        dimensions, orientation="vertical", inner_lo=y0, inner_hi=y1,
        vertical_faces=False, face_polygon=face_polygon, tolerance_pt=tolerance_pt,
    )
    return horizontal, vertical


def _cover_mm_and_pt(spans: Mapping[tuple[float, float], set[object]]) -> Optional[tuple[float, float]]:
    if len(spans) != 1:
        return None
    span, tokens = next(iter(spans.items()))
    millimetre_values = {
        round(float(token[1]), 3)
        for token in tokens
        if isinstance(token, tuple) and token[0] in {"mm", "chain_mm"}
    }
    if len(millimetre_values) != 1:
        return None
    millimetres = next(iter(millimetre_values))
    length_pt = float(span[1]) - float(span[0])
    if length_pt <= 0.0:
        return None
    return millimetres, length_pt


def unique_figured_box_axis_covers(
    bounding_box: Sequence[float], dimensions: Sequence[object], *,
    tolerance_pt: float = RING_FIGURED_BOX_TOLERANCE_PT,
    face_polygon: Optional[Sequence[Sequence[float]]] = None,
) -> Optional[tuple[tuple[float, float], tuple[float, float]]]:
    """((width_mm, width_pt), (height_mm, height_pt)) of the unique figured cover, or None."""
    if figured_box_pair_count(
        bounding_box, dimensions, tolerance_pt=tolerance_pt, face_polygon=face_polygon,
    ) != 1:
        return None
    horizontal, vertical = _figured_axis_spans(
        bounding_box, dimensions, tolerance_pt=tolerance_pt, face_polygon=face_polygon,
    )
    width = _cover_mm_and_pt(horizontal)
    height = _cover_mm_and_pt(vertical)
    if width is None or height is None:
        return None
    return width, height


def unique_figured_box_mm_per_pt(
    bounding_box: Sequence[float], dimensions: Sequence[object], *,
    tolerance_pt: float = RING_FIGURED_BOX_TOLERANCE_PT,
    face_polygon: Optional[Sequence[Sequence[float]]] = None,
) -> Optional[float]:
    """Millimetres per page-point of the unique figured pair that witnesses this box, or None."""
    covers = unique_figured_box_axis_covers(
        bounding_box, dimensions, tolerance_pt=tolerance_pt, face_polygon=face_polygon,
    )
    if covers is None:
        return None
    (width_mm, width_pt), (height_mm, height_pt) = covers
    if (
        width_mm is None or height_mm is None or width_pt is None or height_pt is None
        or width_pt <= 0.0 or height_pt <= 0.0
    ):
        return None
    mm_per_pt_x = width_mm / width_pt
    mm_per_pt_y = height_mm / height_pt
    if not math.isfinite(mm_per_pt_x) or not math.isfinite(mm_per_pt_y) or mm_per_pt_x <= 0.0 or mm_per_pt_y <= 0.0:
        return None
    return (mm_per_pt_x + mm_per_pt_y) / 2.0


def bracket_hashed_figure_endpoints(
    orientation: str,
    text_bbox: Sequence[float],
    tick_points: Sequence[Sequence[float]],
    *,
    tolerance_pt: float = RING_FIGURED_BOX_TOLERANCE_PT,
) -> Optional[tuple[tuple[float, float], tuple[float, float]]]:
    """The unique consecutive hash pair that brackets this figure's text, or None.

    Nested hashes on one dimension line are consecutive tick pairs. The printed
    number sits between its own two hashes. That is unique, not nearest or smallest.
    A projection that lands on a hash, or with fewer than two ticks, abstains.
    """
    if orientation not in {"horizontal", "vertical"}:
        return None
    try:
        x0, y0, x1, y1 = (float(text_bbox[0]), float(text_bbox[1]), float(text_bbox[2]), float(text_bbox[3]))
    except (TypeError, ValueError, IndexError):
        return None
    proj = ((x0 + x1) / 2.0) if orientation == "horizontal" else ((y0 + y1) / 2.0)
    keyed: list[tuple[float, tuple[float, float]]] = []
    for tick in tick_points:
        try:
            point = (float(tick[0]), float(tick[1]))
        except (TypeError, ValueError, IndexError):
            continue
        along = point[0] if orientation == "horizontal" else point[1]
        if not math.isfinite(along):
            continue
        keyed.append((along, point))
    keyed.sort(key=lambda item: (item[0], item[1]))
    unique: list[tuple[float, tuple[float, float]]] = []
    for along, point in keyed:
        if not unique or abs(along - unique[-1][0]) > tolerance_pt:
            unique.append((along, point))
    brackets = [
        (unique[index][1], unique[index + 1][1])
        for index in range(len(unique) - 1)
        if unique[index][0] + tolerance_pt < proj < unique[index + 1][0] - tolerance_pt
    ]
    if len(brackets) != 1:
        return None
    return brackets[0]


def hashed_chain_dimensions_from_bundle(
    bundle: object,
    *,
    witness_endpoint_distance_pt: float,
) -> tuple[object, ...]:
    """One figured part per consecutive hash pair on a dimension rail.

    Hash ticks are the endpoints. A printed number whose text sits uniquely
    between two consecutive hashes is that interval's millimetres. Competing
    numbers on the same pair drop that pair. Window callouts on a different
    rail are a different chain.
    """
    from collections import defaultdict
    from types import SimpleNamespace

    from pb_figured_dimension_evidence import _intersection_with_perpendicular

    observations = tuple(getattr(bundle, "observations", ()) or ())
    bindings = {
        str(binding.observation_id): binding
        for binding in (getattr(bundle, "bindings", ()) or ())
    }
    segments = tuple(getattr(bundle, "observed_geometry", ()) or ())
    by_id = {str(segment.segment_id): segment for segment in segments}
    by_line: dict[str, list[object]] = defaultdict(list)
    for observation in observations:
        millimetres = _dimension_mm(observation)
        orientation = getattr(observation, "orientation", None)
        bbox = getattr(observation, "bbox", None)
        if millimetres is None or bbox is None or orientation not in {"horizontal", "vertical"}:
            continue
        binding = bindings.get(str(getattr(observation, "dimension_id", "")))
        line_id = str(getattr(binding, "dimension_line_id", "") or "") if binding is not None else ""
        if not line_id:
            continue
        by_line[line_id].append(observation)
    figures: list[object] = []
    for line_id, grouped in by_line.items():
        line = by_id.get(line_id)
        if line is None:
            continue
        orientation = str(getattr(line, "orientation", "") or grouped[0].orientation)
        if orientation not in {"horizontal", "vertical"}:
            continue
        ticks: list[tuple[float, float]] = []
        for segment in segments:
            if str(segment.segment_id) == line_id:
                continue
            hit = _intersection_with_perpendicular(line, segment, float(witness_endpoint_distance_pt))
            if hit is not None:
                ticks.append(hit)
        keyed: list[tuple[float, tuple[float, float]]] = []
        for tick in ticks:
            along = tick[0] if orientation == "horizontal" else tick[1]
            if math.isfinite(along):
                keyed.append((along, tick))
        keyed.sort(key=lambda item: (item[0], item[1]))
        unique: list[tuple[float, tuple[float, float]]] = []
        for along, point in keyed:
            if not unique or abs(along - unique[-1][0]) > RING_FIGURED_BOX_TOLERANCE_PT:
                unique.append((along, point))
        tick_points = tuple(point for _along, point in unique)
        interval_mm: dict[tuple[int, int], set[float]] = defaultdict(set)
        interval_text: dict[tuple[int, int], str] = {}
        for observation in grouped:
            ends = bracket_hashed_figure_endpoints(
                orientation, observation.bbox, tick_points,
                tolerance_pt=RING_FIGURED_BOX_TOLERANCE_PT,
            )
            if ends is None:
                continue
            millimetres = _dimension_mm(observation)
            if millimetres is None:
                continue
            start = tick_points.index(ends[0]) if ends[0] in tick_points else None
            stop = tick_points.index(ends[1]) if ends[1] in tick_points else None
            if start is None or stop is None or abs(stop - start) != 1:
                continue
            key = (min(start, stop), max(start, stop))
            interval_mm[key].add(round(millimetres, 3))
            interval_text[key] = str(getattr(observation, "raw_text", "") or "")
        for (start, stop), values in interval_mm.items():
            if len(values) != 1:
                continue
            figures.append(SimpleNamespace(
                dimension_id=f"hash_part_{line_id}_{start}_{stop}",
                orientation=orientation,
                endpoints_pt=(tick_points[start], tick_points[stop]),
                value_mm=next(iter(values)),
                raw_text=interval_text.get((start, stop)),
            ))
    return tuple(figures)


def unique_hashed_wall_length_mm(
    span_lo: float,
    span_hi: float,
    dimensions: Sequence[object],
    *,
    orientation: str,
    face_polygon: Optional[Sequence[Sequence[float]]] = None,
    tolerance_pt: float = RING_FIGURED_BOX_TOLERANCE_PT,
) -> Optional[float]:
    """Printed millimetres of the unique hashed chain that matches this wall span, or None.

    Two hashes on the same rail that match the wall ends are one length. Nested
    hashes on that rail between those ends add. An overall of the same run is not
    added again. Two walls of the same span share that chain. A hash on a different
    rail, a gap, or a fork abstains. Not FIRM wall-length quantity authority.
    """
    if orientation not in {"horizontal", "vertical"}:
        return None
    inner_lo = min(float(span_lo), float(span_hi))
    inner_hi = max(float(span_lo), float(span_hi))
    if inner_hi - inner_lo <= tolerance_pt:
        return None
    vertical_faces = orientation == "horizontal"
    spans = _with_hashed_chain(
        _witness_spans_for_axis(
            dimensions, orientation=orientation, inner_lo=inner_lo, inner_hi=inner_hi,
            vertical_faces=vertical_faces, face_polygon=face_polygon, tolerance_pt=tolerance_pt,
        ),
        dimensions, orientation=orientation, inner_lo=inner_lo, inner_hi=inner_hi,
        vertical_faces=vertical_faces, face_polygon=face_polygon, tolerance_pt=tolerance_pt,
    )
    covered = _cover_mm_and_pt(spans)
    if covered is None:
        return None
    millimetres, _length_pt = covered
    if not math.isfinite(millimetres) or millimetres <= 0.0:
        return None
    return millimetres


def _axis_aligned_edge(
    start: Sequence[float], end: Sequence[float],
) -> Optional[tuple[str, float, float, float]]:
    ax, ay = float(start[0]), float(start[1])
    bx, by = float(end[0]), float(end[1])
    if abs(ay - by) <= NOISE_PT * 2 and abs(ax - bx) > NOISE_PT:
        return "horizontal", min(ax, bx), max(ax, bx), (ay + by) / 2.0
    if abs(ax - bx) <= NOISE_PT * 2 and abs(ay - by) > NOISE_PT:
        return "vertical", min(ay, by), max(ay, by), (ax + bx) / 2.0
    return None


def _edge_is_wall(owners: Sequence[str]) -> bool:
    return any(
        owner and not str(owner).startswith(_CLOSURE_OWNER_PREFIX)
        for owner in owners
    )


def _edge_is_length_chord(owners: Sequence[str]) -> bool:
    """True when this edge is only a doorway chord: not a wall, but the wall continues over it."""
    if not owners:
        return False
    return all(str(owner).startswith(_CLOSURE_OWNER_PREFIX) for owner in owners) and not _edge_is_wall(owners)


def unique_hashed_ring_wall_lengths(
    polygon: Sequence[Sequence[float]],
    dimensions: Sequence[object],
    *,
    edge_owner_ids: Sequence[Sequence[str]] = (),
    tolerance_pt: float = RING_FIGURED_BOX_TOLERANCE_PT,
) -> tuple[Optional[float], ...]:
    """Unique hashed millimetre length of each collinear wall run, else None.

    A doorway chord is not a wall owner, but the wall continues over the door, so a
    collinear chord between wall edges belongs to that run. Consecutive collinear
    wall edges are one run. Opposite walls of a rectangle share one hashed chain.
    A lining-cap jog shorter than the figured-box tolerance is representation noise:
    it does not split the finished face, and the two faces of the same strip may
    differ by that much.
    """
    points = [(float(p[0]), float(p[1])) for p in polygon]
    if len(points) < 3:
        return ()
    runs: list[tuple[str, float, float, float, bool]] = []
    current: Optional[tuple[str, float, float, float, bool]] = None
    for index in range(len(points)):
        nxt = points[(index + 1) % len(points)]
        if math.hypot(nxt[0] - points[index][0], nxt[1] - points[index][1]) <= tolerance_pt:
            continue
        owners = edge_owner_ids[index] if index < len(edge_owner_ids) else ("wall",)
        axis = _axis_aligned_edge(points[index], nxt)
        is_wall = _edge_is_wall(owners)
        is_chord = _edge_is_length_chord(owners)
        if axis is None or not (is_wall or is_chord):
            if current is not None:
                runs.append(current)
                current = None
            continue
        orientation, lo, hi, line_key = axis
        if (
            current is not None
            and current[0] == orientation
            and abs(current[3] - line_key) <= tolerance_pt
            and (abs(lo - current[2]) <= tolerance_pt or abs(hi - current[1]) <= tolerance_pt)
        ):
            current = (
                orientation, min(current[1], lo), max(current[2], hi), current[3],
                current[4] or is_wall,
            )
        else:
            if current is not None:
                runs.append(current)
            current = (orientation, lo, hi, line_key, is_wall)
    if current is not None:
        runs.append(current)
    if (
        len(runs) >= 2
        and runs[0][0] == runs[-1][0]
        and abs(runs[0][3] - runs[-1][3]) <= tolerance_pt
        and (
            abs(runs[0][1] - runs[-1][2]) <= tolerance_pt
            or abs(runs[-1][1] - runs[0][2]) <= tolerance_pt
        )
    ):
        first, last = runs[0], runs[-1]
        runs[0] = (
            first[0],
            min(first[1], last[1]),
            max(first[2], last[2]),
            first[3],
            first[4] or last[4],
        )
        runs.pop()
    pairs_h = _same_rail_hash_pairs(dimensions, orientation="horizontal", tolerance_pt=tolerance_pt)
    pairs_v = _same_rail_hash_pairs(dimensions, orientation="vertical", tolerance_pt=tolerance_pt)
    lengths: list[Optional[float]] = []
    for orientation, lo, hi, _line_key, has_wall in runs:
        if not has_wall:
            continue
        full = unique_hashed_wall_length_mm(
            lo, hi, dimensions, orientation=orientation,
            face_polygon=polygon, tolerance_pt=tolerance_pt,
        )
        lengths.append(full)
        lengths.extend(
            _shared_inner_hash_millimetres(
                lo, hi,
                orientation=orientation,
                pairs=pairs_h if orientation == "horizontal" else pairs_v,
                face_polygon=polygon,
                full=full,
                tolerance_pt=tolerance_pt,
            )
        )
    return tuple(lengths)


def _closure_joins_runs(
    left_hi: float,
    right_lo: float,
    band: tuple[float, float],
    *,
    horizontal: bool,
    closures: Sequence[object],
    tolerance_pt: float,
) -> bool:
    for closure in closures:
        if bool(getattr(closure, "horizontal", None)) != horizontal:
            continue
        closure_band = getattr(closure, "band", None)
        gap = getattr(closure, "gap_interval", None)
        if closure_band is None or gap is None:
            continue
        if abs(float(closure_band[0]) - band[0]) > tolerance_pt or abs(float(closure_band[1]) - band[1]) > tolerance_pt:
            continue
        gap_lo, gap_hi = sorted((float(gap[0]), float(gap[1])))
        if abs(gap_lo - left_hi) <= tolerance_pt and abs(gap_hi - right_lo) <= tolerance_pt:
            return True
    return False


def unique_hashed_traced_strip_lengths(
    strips: Sequence[object],
    dimensions: Sequence[object],
    *,
    closures: Sequence[object] = (),
    fill_polygons: Sequence[tuple[int, object]] = (),
    tolerance_pt: float = RING_FIGURED_BOX_TOLERANCE_PT,
) -> tuple[Optional[float], ...]:
    """Hashed millimetres of each traced wall run, hashes matched to the run's ends.

    Collinear touching strips are one wall. A collinear doorway closure continues
    that wall over the opening. Two walls of the same span share one hash chain.
    Nested hashes between the matching end hashes add. Orthogonal notched fills
    contribute their wall-thickness bars; the notch stays empty. Not FIRM wall length.
    """
    traced: list[object] = list(strips)
    for index, polygon in fill_polygons:
        traced.extend(_orthogonal_wall_fill_strips(int(index), polygon))
    lengths: list[Optional[float]] = []
    for horizontal in (True, False):
        orientation = "horizontal" if horizontal else "vertical"
        runs = [
            [band, lo, hi]
            for band, lo, hi, _paths in _runs(traced, horizontal)
        ]
        merged = True
        while merged:
            merged = False
            runs.sort(key=lambda item: (round(item[0][0], 3), round(item[0][1], 3), item[1]))
            nxt: list[list[object]] = []
            skip: set[int] = set()
            for index, run in enumerate(runs):
                if index in skip:
                    continue
                band, lo, hi = run[0], float(run[1]), float(run[2])
                for other_index in range(index + 1, len(runs)):
                    if other_index in skip:
                        continue
                    other = runs[other_index]
                    other_band, other_lo, other_hi = other[0], float(other[1]), float(other[2])
                    if abs(other_band[0] - band[0]) > tolerance_pt or abs(other_band[1] - band[1]) > tolerance_pt:
                        continue
                    if hi <= other_lo and _closure_joins_runs(
                        hi, other_lo, band, horizontal=horizontal,
                        closures=closures, tolerance_pt=tolerance_pt,
                    ):
                        hi = other_hi
                        skip.add(other_index)
                        merged = True
                    elif other_hi <= lo and _closure_joins_runs(
                        other_hi, lo, other_band, horizontal=horizontal,
                        closures=closures, tolerance_pt=tolerance_pt,
                    ):
                        lo = other_lo
                        skip.add(other_index)
                        merged = True
                nxt.append([band, lo, hi])
            runs = nxt
        for band, lo, hi in runs:
            if horizontal:
                face = ((float(lo), band[0]), (float(hi), band[0]), (float(hi), band[1]), (float(lo), band[1]))
            else:
                face = ((band[0], float(lo)), (band[1], float(lo)), (band[1], float(hi)), (band[0], float(hi)))
            lengths.append(
                unique_hashed_wall_length_mm(
                    float(lo), float(hi), dimensions, orientation=orientation,
                    face_polygon=face, tolerance_pt=tolerance_pt,
                )
            )
    return tuple(lengths)


def _fills_its_bounding_rectangle(polygon: Sequence[Sequence[float]]) -> bool:
    """True only when the face IS its bounding rectangle, tested in space and not by an aggregate area.

    Every point of the box must lie within the representation noise (``NOISE_PT``) of the face. A wall return,
    a recess or a jamb offset is spatial content: however small its area against the box, a notch wider than
    twice the noise bound leaves box points farther than that from the face, so it is never absorbed. Extra
    collinear vertices change nothing.
    """
    face = Polygon([(float(p[0]), float(p[1])) for p in polygon])
    if not face.is_valid or face.is_empty:
        return False
    rectangle = shapely_box(*face.bounds)
    return rectangle.difference(face.buffer(NOISE_PT, join_style=2)).area <= 1e-9


def layered_ring_room_face_scope(
    ring_result: LayeredRoomRingResult,
    *,
    document_id: str,
    revision_id: str,
    source_sha256: str,
    snapshot_id: str,
    page_id: str,
    decision_scope_id: str,
    corroborating_dimensions: Optional[Sequence[object]] = None,
    partition_witness: bool = False,
    finished_face_gate: bool = False,
) -> Optional[SourceRoomFaceScopeResult]:
    """The ring scope for one page, or None when no ring closed (nothing is overridden).

    ``corroborating_dimensions`` (authenticated native figured dimensions of the page): when
    given, a CANDIDATE ring becomes a record only if exactly one figured pair has its bounding
    box as witness box; otherwise it is kept as an abstention. When None every CANDIDATE ring
    is a record (direct converter use and tests).

    ``partition_witness`` (default False, its own control): rings joined by real sliding-leaf chords form
    a partition group (see ``pb_layered_wall_doorway_partition_witness_shadow``). Every ring of such a group
    is judged ONLY by the group: the whole group becomes records when its membership is exact and the
    union's outer envelope is the witness box of exactly one authenticated figured pair; otherwise every
    member is an abstention. The shared pair is topology corroboration of the union; it is never a part's
    area. Without ``corroborating_dimensions`` a partition group cannot be corroborated and abstains.
    """
    if type(partition_witness) is not bool:
        raise ValueError("partition_witness must be an explicit boolean")
    if type(finished_face_gate) is not bool:
        raise ValueError("finished_face_gate must be an explicit boolean")
    if not any(r.status is EvidenceResolutionStatus.CANDIDATE for r in ring_result.rings):
        return None
    scope = (document_id, revision_id, source_sha256, snapshot_id, page_id, decision_scope_id)
    records: list[SourceRoomFaceRecord] = []
    abstained: list[SourceRoomFaceAbstention] = []
    not_rectangle_tokens: list[str] = []
    partition_tokens: list[str] = []
    finished_face_tokens: list[str] = []
    # ring record id -> (group ring ids, whole group corroborated)
    partition_of: dict[str, tuple[tuple[str, ...], bool]] = {}
    if partition_witness:
        page_index = int(page_id) - 1 if page_id.isascii() and page_id.isdecimal() else -1
        for group in partition_groups(ring_result, source_sha256=source_sha256, page_index=page_index):
            corroborated_group = (
                group.valid
                and corroborating_dimensions is not None
                and figured_box_pair_count(group.envelope, corroborating_dimensions) == 1
            )
            for ring_record_id in group.ring_record_ids:
                partition_of[ring_record_id] = (group.ring_record_ids, corroborated_group)
    for ring in ring_result.rings:
        polygon = _canonical_polygon(ring.polygon_pdf_pts)
        if not polygon:
            continue
        face_id, payload = _face_ids(ring, polygon, scope=scope)
        owner_ids = tuple(sorted({
            owner for owners in ring.edge_owner_ids for owner in owners
            if not owner.startswith(_CLOSURE_OWNER_PREFIX)
        }))
        boundary = _boundary_edges(ring)
        area = _polygon_area(polygon)
        common = dict(
            face_id=face_id, document_id=document_id, revision_id=revision_id, source_sha256=source_sha256,
            snapshot_id=snapshot_id, page_id=page_id, decision_scope_id=decision_scope_id,
            polygon_pdf_pts=polygon, bounding_wall_ids=owner_ids, area_page_pts2=area,
            boundary_wall_edges=boundary,
        )
        group_of = partition_of.get(ring.record_id)
        if group_of is not None:
            corroborated = group_of[1]  # a group member is judged by its group's union envelope only
        else:
            corroborated = (
                corroborating_dimensions is None
                or figured_box_pair_count(
                    ring.bbox_pdf_pts, corroborating_dimensions, face_polygon=polygon,
                ) == 1
            )
        if ring.status is EvidenceResolutionStatus.CANDIDATE and corroborated:
            record_payload = {
                **payload, "owners": owner_ids, "ring_record_id": ring.record_id,
                "closure_ids": list(ring.bounding_closure_ids),
            }
            if group_of is not None:
                record_payload["partition_group"] = list(group_of[0])
            record_id = stable_contract_id("layered_ring_source_room_face_record", record_payload, digest_chars=32)
            records.append(SourceRoomFaceRecord(record_id=record_id, **common))
            if group_of is not None:
                partition_tokens.append(f"{RING_PARTITION_PART_PREFIX}{record_id}")
            if finished_face_gate:
                finished_face_tokens.append(f"{RING_FINISHED_FACE_REQUIRED_PREFIX}{record_id}")
            if not _fills_its_bounding_rectangle(polygon):
                not_rectangle_tokens.append(f"{RING_NOT_A_RECTANGLE_PREFIX}{record_id}")
        else:
            abstained.append(SourceRoomFaceAbstention(reason=SOURCE_ROOM_FACE_BOUNDARY_UNRESOLVED, **common))
    if not records:
        return None
    records.sort(key=lambda r: r.record_id)
    abstained.sort(key=lambda r: r.face_id)
    return SourceRoomFaceScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=True,
        records=tuple(records),
        reason_codes=(
            SOURCE_ROOM_FACE_SCOPE_RESOLVED, SOURCE_ROOM_FACE_UNIVERSE_PARTIAL, LAYERED_RING_SCOPE_REASON,
            *((LAYERED_RING_PARTITION_REASON,) if partition_tokens else ()),
            *((LAYERED_RING_FINISHED_FACE_GATE_REASON,) if finished_face_tokens else ()),
            *sorted(not_rectangle_tokens),
            *sorted(partition_tokens),
            *sorted(finished_face_tokens),
        ),
        document_id=document_id, revision_id=revision_id, source_sha256=source_sha256,
        snapshot_id=snapshot_id, page_id=page_id, decision_scope_id=decision_scope_id,
        abstained_faces=tuple(abstained),
    )


def layered_ring_scope_overrides(
    source_producer: object,
    *,
    revision_id: str,
    page_ids: Sequence[str],
    require_figured_box: bool = True,
    sliding_leaf_frame_closure: bool = False,
    partition_witness: bool = False,
    finished_face_gate: bool = False,
    dark_painted_wall_source: bool = False,
    wall_end_stroke_closures: bool = False,
) -> Mapping[tuple[str, str, str, str, str, str], SourceRoomFaceScopeOverride]:
    """Issued ring scopes keyed like the room-face authority, read from the SHA-pinned native bytes.

    With ``require_figured_box`` (the live default) only rings corroborated by exactly one
    authenticated figured pair become records; the rest are abstentions.

    ``partition_witness`` (default False; requires ``sliding_leaf_frame_closure`` and ``require_figured_box``)
    additionally judges sliding-leaf partition groups by their union envelope (see the converter).
    """
    if type(partition_witness) is not bool:
        raise ValueError("partition_witness must be an explicit boolean")
    if type(finished_face_gate) is not bool:
        raise ValueError("finished_face_gate must be an explicit boolean")
    if type(dark_painted_wall_source) is not bool:
        raise ValueError("dark_painted_wall_source must be an explicit boolean")
    if dark_painted_wall_source and not finished_face_gate:
        raise ValueError("dark_painted_wall_source requires finished_face_gate")
    if type(wall_end_stroke_closures) is not bool:
        raise ValueError("wall_end_stroke_closures must be an explicit boolean")
    if wall_end_stroke_closures and not dark_painted_wall_source:
        raise ValueError("wall_end_stroke_closures requires dark_painted_wall_source")
    if partition_witness and not (sliding_leaf_frame_closure and require_figured_box):
        raise ValueError("partition_witness requires sliding_leaf_frame_closure and require_figured_box")
    from pb_cross_view_ceiling_finish_authority import _source_bytes
    from pb_cross_view_room_area_authority import _trusted_native_dimensions_for_page
    from pb_drawing_evidence_binding import DrawingViewType

    published = source_producer.published_snapshot_for_revision(revision_id)  # type: ignore[attr-defined]
    payload = _source_bytes(source_producer, revision_id)  # type: ignore[arg-type]
    if published is None or payload is None:
        return {}
    overrides = {}
    for page_id in page_ids:
        page = str(page_id)
        if not page.isascii() or not page.isdecimal() or page.startswith("0"):
            continue
        ring_result = build_from_pdf_bytes(
            payload, source_sha256=published.revision.source_sha256, page_index=int(page) - 1,
            sliding_leaf_frame_closure=sliding_leaf_frame_closure,
            dark_painted_wall_source=dark_painted_wall_source,
            wall_end_stroke_closures=wall_end_stroke_closures,
        )
        decision_scope_id = _PAGE_DECISION_SCOPE.format(page_id=page)
        dimensions = None
        if require_figured_box and any(r.status is EvidenceResolutionStatus.CANDIDATE for r in ring_result.rings):
            dimensions = _trusted_native_dimensions_for_page(
                source_producer, revision_id=published.revision.revision_id, page_id=page,  # type: ignore[arg-type]
                candidate_lines=(), view_type=DrawingViewType.FLOOR_PLAN.value,
            )
        scope = layered_ring_room_face_scope(
            ring_result,
            document_id=published.revision.document_id, revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
            page_id=page, decision_scope_id=decision_scope_id, corroborating_dimensions=dimensions,
            partition_witness=partition_witness, finished_face_gate=finished_face_gate,
        )
        if scope is not None:
            key = (
                published.revision.document_id, published.revision.revision_id,
                published.revision.source_sha256, published.snapshot.snapshot_id, page, decision_scope_id,
            )
            overrides[key] = SourceRoomFaceScopeOverride(
                scope=scope, receipt_digest=scope_override_digest(scope), _seal=SCOPE_OVERRIDE_SEAL,
            )
    return overrides


def ring_face_bounding_box(record: SourceRoomFaceRecord) -> tuple[float, float, float, float]:
    xs = [p[0] for p in record.polygon_pdf_pts]
    ys = [p[1] for p in record.polygon_pdf_pts]
    return min(xs), min(ys), max(xs), max(ys)


__all__ = [
    "LAYERED_RING_FINISHED_FACE_GATE_REASON",
    "LAYERED_RING_PARTITION_REASON",
    "LAYERED_RING_SCOPE_REASON",
    "RING_FIGURED_BOX_TOLERANCE_PT",
    "RING_FINISHED_FACE_REQUIRED_PREFIX",
    "RING_NOT_A_RECTANGLE_PREFIX",
    "RING_PARTITION_PART_PREFIX",
    "figured_box_pair_count",
    "unique_figured_box_axis_covers",
    "unique_figured_box_mm_per_pt",
    "unique_hashed_wall_length_mm",
    "unique_hashed_ring_wall_lengths",
    "unique_hashed_traced_strip_lengths",
    "bracket_hashed_figure_endpoints",
    "hashed_chain_dimensions_from_bundle",
    "layered_ring_room_face_scope",
    "layered_ring_scope_overrides",
    "ring_face_bounding_box",
]
