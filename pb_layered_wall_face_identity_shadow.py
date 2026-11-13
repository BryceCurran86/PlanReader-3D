"""Which face of the wall does a doorway-closed room ring follow? (SHADOW ONLY, default-off, diagnostic).

``pb_layered_wall_doorway_room_ring_shadow`` recovers a room as the free region bounded by drawn wall-layer
ink. That boundary is the face of the DRAWN wall strip. Whether the drawn strip is the structural frame (with
a lining beyond it that the plan does not draw) or the finished wall is a source fact, not a geometric one.
This module classifies every wall edge of a ring by what the source states about the strip that owns it:

* ``lined_internal_frame_face``: the owning strip is on an internal-wall layer and its thickness at the page
  scale equals the frame thickness an authenticated build-up statement gives for internal walls. The drawn
  face is the frame face; the statement gives the lining beyond it.
* ``internal_strip_is_stated_frame_plus_both_linings``: the owning internal fill or strip thickness equals
  the stated frame plus lining on both faces. The room face of that body is already the finished face.
* ``internal_drawn_lining_face``: the ring follows an internal lining-thin stroke, or a strip whose thickness
  is the stated lining. That drawn face is already the finished face; it is not inset again.
* ``external_drawn_inner_face``: the owning strip is on an external-wall layer. The set does not state an
  internal lining for that kind, so the inner face of the DRAWN strip is the room face. No lining is inferred.
* every other class is an explicit unresolved reason: a different thickness, an unclassified fill or layer, a
  strip the facts do not know.
* a doorway/threshold chord is not a wall and has no lining.

A ring is ``resolved`` only when EVERY wall edge is a lined internal frame face or an external drawn inner
face, and no other fact (a statement variant for wet areas, conflicting statements) leaves the lining open.
Anything else is ``unresolved`` with the reason codes and the edge length in each class, so the missing
source fact is precise.

It never infers a lining thickness: the lining comes only from an authenticated statement. External walls
carry a zero offset. It issues no scale
(the page scale is an input from the existing authority), area, length, host, deduction or finish, and it never
promotes a ring to a measurement.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from pb_layered_wall_doorway_room_ring_shadow import (
    NOISE_PT,
    LayeredRoomRingRecord,
    _STROKE_PAIR_FACE_PT,
    _collect_stroke_pair_strips,
    _collect_strips,
    _orthogonal_wall_fill_strips,
    _source_wall_ink_candidate_drawings,
)

FACE_IDENTITY_SCHEMA_VERSION = "1.0.0"

VERDICT_RESOLVED = "resolved_internal_frame_face_with_stated_lining"
VERDICT_UNRESOLVED = "unresolved"

CLASS_LINED_INTERNAL_FRAME_FACE = "lined_internal_frame_face"
CLASS_DRAWN_FINISHED_BUILD_UP = "internal_strip_is_stated_frame_plus_both_linings"
CLASS_DRAWN_LINING_FACE = "internal_drawn_lining_face"
CLASS_EXTERNAL_DRAWN_INNER_FACE = "external_drawn_inner_face"
CLASS_INTERNAL_THICKNESS_MISMATCH = "internal_strip_thickness_not_the_stated_frame"
CLASS_INTERNAL_STATEMENT_UNUSABLE = "internal_strip_without_a_usable_statement_or_scale"
CLASS_EXTERNAL_LINING_NOT_STATED = "external_wall_internal_lining_not_stated"
CLASS_LAYER_NOT_CLASSIFIED = "wall_layer_not_classified"
CLASS_FILL_NOT_CLASSIFIED = "wall_fill_not_classified"
CLASS_OWNER_UNKNOWN = "wall_owner_not_in_strip_facts"
CLASS_OWNERS_MIXED = "edge_owned_by_mixed_classes"
CLASS_THRESHOLD_CHORD = "threshold_chord"
_RESOLVED_EDGE_CLASSES = (
    CLASS_LINED_INTERNAL_FRAME_FACE,
    CLASS_DRAWN_FINISHED_BUILD_UP,
    CLASS_DRAWN_LINING_FACE,
    CLASS_EXTERNAL_DRAWN_INNER_FACE,
    CLASS_THRESHOLD_CHORD,
)

REASON_STATEMENT_UNAVAILABLE = "internal_wall_build_up_statement_unavailable"
REASON_STATEMENTS_CONFLICT = "internal_wall_build_up_statements_conflict"
REASON_SCALE_UNAVAILABLE = "page_scale_unavailable_for_strip_thickness"
REASON_WET_AREA_STATUS = "room_wet_area_status_not_established"
REASON_NO_WALL_EDGES = "ring_has_no_wall_edges"

_CLOSURE_OWNER_PREFIX = "layered_doorway_closure:"
_STRIP_OWNER_PREFIX = "layered_wall_strip:"
_FILL_OWNER_PREFIX = "layered_wall_fill:"


@dataclass(frozen=True)
class WallStripFact:
    """What the page's drawing says about one wall-layer shape: its layer and (for a strip) its thickness."""

    path_index: int
    layer: str
    is_strip: bool
    thickness_pt: Optional[float]


@dataclass(frozen=True)
class RingFaceIdentity:
    ring_record_id: str
    verdict: str
    reason_codes: tuple[str, ...]
    class_lengths_pt: tuple[tuple[str, float], ...]
    wall_edge_count: int
    chord_edge_count: int
    lined_edge_offsets_mm: tuple[tuple[int, float], ...]
    statement_text_sha256: tuple[str, ...]
    schema_version: str = FACE_IDENTITY_SCHEMA_VERSION
    takeoff_eligible: bool = False
    commercial_projection_allowed: bool = False
    metric_area_issued: bool = False
    floor_finish_issued: bool = False
    diagnostic_only: bool = True


def wall_strip_facts(drawings: Sequence[Mapping[str, Any]]) -> dict[int, WallStripFact]:
    """Layer and thickness of every wall-layer strip or fill the ring module can own an edge with."""
    strips, other_fills = _collect_strips(drawings)
    facts: dict[int, WallStripFact] = {}
    for strip in strips:
        thickness = min(strip.x1 - strip.x0, strip.y1 - strip.y0)
        facts[strip.path_index] = WallStripFact(
            path_index=strip.path_index, layer=str(drawings[strip.path_index].get("layer") or ""),
            is_strip=True, thickness_pt=float(thickness),
        )
    for index, _polygon in other_fills:
        facts[int(index)] = WallStripFact(
            path_index=int(index), layer=str(drawings[int(index)].get("layer") or ""),
            is_strip=False, thickness_pt=None,
        )
    by_path: dict[int, list[float]] = {}
    for strip in _collect_stroke_pair_strips(drawings):
        thickness = min(strip.x1 - strip.x0, strip.y1 - strip.y0)
        for path_index in strip.native_path_indices():
            by_path.setdefault(path_index, []).append(float(thickness))
    for path_index, thicknesses in by_path.items():
        if path_index in facts:
            continue
        first = thicknesses[0]
        if any(abs(value - first) > NOISE_PT for value in thicknesses):
            continue
        row = drawings[path_index] if 0 <= path_index < len(drawings) else {}
        layer = str(row.get("layer") or "") if isinstance(row, Mapping) else ""
        facts[path_index] = WallStripFact(
            path_index=path_index, layer=layer, is_strip=True, thickness_pt=float(first),
        )
    return facts


def wall_face_source_support(
    drawings: Sequence[Mapping[str, Any]],
) -> tuple[
    dict[int, WallStripFact],
    dict[int, Any],
    dict[int, tuple[tuple[float, float, float, float], ...]],
    dict[int, str],
    frozenset[int],
]:
    """Strip facts, fill polygons, stroke-pair bounds, layers and unfilled paths, index-stable."""
    kept, _supported, _green = _source_wall_ink_candidate_drawings(drawings)
    facts = wall_strip_facts(kept)
    _strips, other_fills = _collect_strips(kept)
    fill_polygons = {int(index): polygon for index, polygon in other_fills}
    pairs_by_path: dict[int, list[tuple[float, float, float, float]]] = {}
    for strip in _collect_stroke_pair_strips(kept):
        bounds = (float(strip.x0), float(strip.y0), float(strip.x1), float(strip.y1))
        for path_index in strip.native_path_indices():
            pairs_by_path.setdefault(path_index, []).append(bounds)
    path_layers: dict[int, str] = {}
    unfilled: set[int] = set()
    for index, row in enumerate(kept):
        if not isinstance(row, Mapping):
            continue
        path_layers[index] = str(row.get("layer") or "")
        if row.get("fill") is None and row.get("items"):
            unfilled.add(index)
    return (
        facts,
        fill_polygons,
        {index: tuple(bounds) for index, bounds in pairs_by_path.items()},
        path_layers,
        frozenset(unfilled),
    )


def _layer_kind(layer: str) -> str:
    lowered = layer.lower()
    if "wallinternal" in lowered:
        return "internal"
    if "wallexternal" in lowered:
        return "external"
    return "other"


def _matches_stated_mm(thickness_pt: float, target_mm: float, mm_per_pt: float) -> bool:
    return abs(float(thickness_pt) * float(mm_per_pt) - float(target_mm)) <= NOISE_PT * float(mm_per_pt)


def _internal_thickness_class(
    thickness_pt: Optional[float],
    *,
    frame_mm: Optional[float],
    lining_mm: Optional[float],
    mm_per_pt: Optional[float],
) -> str:
    if frame_mm is None or mm_per_pt is None or thickness_pt is None:
        return CLASS_INTERNAL_STATEMENT_UNUSABLE
    if _matches_stated_mm(thickness_pt, frame_mm, mm_per_pt):
        return CLASS_LINED_INTERNAL_FRAME_FACE
    if lining_mm is not None and _matches_stated_mm(thickness_pt, frame_mm + 2.0 * lining_mm, mm_per_pt):
        return CLASS_DRAWN_FINISHED_BUILD_UP
    if lining_mm is not None and _matches_stated_mm(thickness_pt, frame_mm + lining_mm, mm_per_pt):
        return CLASS_DRAWN_FINISHED_BUILD_UP
    if lining_mm is not None and _matches_stated_mm(thickness_pt, lining_mm, mm_per_pt):
        return CLASS_DRAWN_LINING_FACE
    return CLASS_INTERNAL_THICKNESS_MISMATCH


def _layer_and_thickness_class(
    layer: str,
    thickness_pt: Optional[float],
    *,
    frame_mm: Optional[float],
    lining_mm: Optional[float],
    mm_per_pt: Optional[float],
) -> str:
    kind = _layer_kind(layer)
    if kind == "external":
        return CLASS_EXTERNAL_DRAWN_INNER_FACE
    if kind == "other":
        return CLASS_LAYER_NOT_CLASSIFIED
    return _internal_thickness_class(
        thickness_pt, frame_mm=frame_mm, lining_mm=lining_mm, mm_per_pt=mm_per_pt,
    )


def _edge_lies_on_rect_face(
    first: Sequence[float],
    second: Sequence[float],
    bounds: Sequence[float],
    *,
    tol: float,
) -> bool:
    x0, y0, x1, y1 = (float(value) for value in bounds)
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    ax, ay = float(first[0]), float(first[1])
    bx, by = float(second[0]), float(second[1])
    if abs(ay - by) <= NOISE_PT:
        y = (ay + by) / 2.0
        lo, hi = (ax, bx) if ax <= bx else (bx, ax)
        return (
            (abs(y - y0) <= tol or abs(y - y1) <= tol)
            and min(hi, x1) - max(lo, x0) >= -NOISE_PT
        )
    if abs(ax - bx) <= NOISE_PT:
        x = (ax + bx) / 2.0
        lo, hi = (ay, by) if ay <= by else (by, ay)
        return (
            (abs(x - x0) <= tol or abs(x - x1) <= tol)
            and min(hi, y1) - max(lo, y0) >= -NOISE_PT
        )
    return False


def _unique_stroke_pair_thickness(
    path_index: int,
    first: Sequence[float],
    second: Sequence[float],
    stroke_pairs_by_path: Mapping[int, Sequence[Sequence[float]]],
) -> Optional[float]:
    pairs = tuple(stroke_pairs_by_path.get(path_index, ()))
    if not pairs:
        return None
    on_face = [
        min(abs(float(b[2]) - float(b[0])), abs(float(b[3]) - float(b[1])))
        for b in pairs
        if _edge_lies_on_rect_face(first, second, b, tol=_STROKE_PAIR_FACE_PT)
    ]
    pool = on_face or [
        min(abs(float(b[2]) - float(b[0])), abs(float(b[3]) - float(b[1])))
        for b in pairs
    ]
    if not pool:
        return None
    first_thick = pool[0]
    if any(abs(value - first_thick) > NOISE_PT for value in pool):
        return None
    return float(first_thick)


def _fill_thickness_at_edge(polygon: Any, first: Sequence[float], second: Sequence[float]) -> Optional[float]:
    """Perpendicular depth of a wall-layer fill at the room-face edge, in page points."""
    from shapely.geometry import LineString, Point

    ax, ay = float(first[0]), float(first[1])
    bx, by = float(second[0]), float(second[1])
    length = math.hypot(bx - ax, by - ay)
    if length <= NOISE_PT:
        return None
    nx, ny = (by - ay) / length, - (bx - ax) / length
    mid = ((ax + bx) / 2.0, (ay + by) / 2.0)
    probe = Point(mid[0] + nx * (NOISE_PT * 2.0), mid[1] + ny * (NOISE_PT * 2.0))
    if not polygon.covers(probe) and not polygon.intersects(probe):
        nx, ny = -nx, -ny
    ray = LineString((
        (mid[0] + nx * NOISE_PT, mid[1] + ny * NOISE_PT),
        (mid[0] + nx * 40.0, mid[1] + ny * 40.0),
    ))
    hit = ray.intersection(polygon.boundary)
    if hit.is_empty:
        return None
    points = []
    geom_type = hit.geom_type
    if geom_type == "Point":
        points = [hit]
    elif geom_type == "MultiPoint":
        points = list(hit.geoms)
    elif geom_type == "GeometryCollection":
        points = [geom for geom in hit.geoms if geom.geom_type == "Point"]
    if not points:
        return None
    origin = Point(mid)
    farthest = max(points, key=lambda point: point.distance(origin))
    return float(farthest.distance(origin))


def _fill_candidate_thicknesses(polygon: Any) -> tuple[float, ...]:
    """Axis-aligned side lengths and orthogonal wall bars of a notched fill."""
    thicknesses: list[float] = []
    try:
        coords = list(polygon.exterior.coords)
    except AttributeError:
        return ()
    for start, end in zip(coords, coords[1:]):
        dx, dy = float(end[0]) - float(start[0]), float(end[1]) - float(start[1])
        if abs(dx) <= NOISE_PT and abs(dy) > NOISE_PT:
            thicknesses.append(abs(dy))
        elif abs(dy) <= NOISE_PT and abs(dx) > NOISE_PT:
            thicknesses.append(abs(dx))
    for bar in _orthogonal_wall_fill_strips(0, polygon):
        thicknesses.append(min(bar.x1 - bar.x0, bar.y1 - bar.y0))
    return tuple(thicknesses)


def _unique_fill_statement_class(
    polygon: Any,
    *,
    layer: str,
    frame_mm: Optional[float],
    lining_mm: Optional[float],
    mm_per_pt: Optional[float],
) -> Optional[str]:
    matches = {
        _layer_and_thickness_class(
            layer, thickness, frame_mm=frame_mm, lining_mm=lining_mm, mm_per_pt=mm_per_pt,
        )
        for thickness in _fill_candidate_thicknesses(polygon)
        if _layer_and_thickness_class(
            layer, thickness, frame_mm=frame_mm, lining_mm=lining_mm, mm_per_pt=mm_per_pt,
        ) in _RESOLVED_EDGE_CLASSES
    }
    if len(matches) == 1:
        return next(iter(matches))
    return None


def _edge_class(
    owners: Sequence[str],
    facts: Mapping[int, WallStripFact],
    *,
    first: Sequence[float],
    second: Sequence[float],
    frame_mm: Optional[float],
    lining_mm: Optional[float],
    mm_per_pt: Optional[float],
    fill_polygons: Optional[Mapping[int, Any]] = None,
    stroke_pairs_by_path: Optional[Mapping[int, Sequence[Sequence[float]]]] = None,
    path_layers: Optional[Mapping[int, str]] = None,
    unfilled_paths: Optional[frozenset[int]] = None,
) -> str:
    classes: set[str] = set()
    fill_polygons = fill_polygons or {}
    stroke_pairs_by_path = stroke_pairs_by_path or {}
    path_layers = path_layers or {}
    unfilled_paths = unfilled_paths or frozenset()
    for owner in owners:
        if owner.startswith(_FILL_OWNER_PREFIX):
            try:
                fill_index = int(owner[len(_FILL_OWNER_PREFIX):])
            except ValueError:
                classes.add(CLASS_OWNER_UNKNOWN)
                continue
            polygon = fill_polygons.get(fill_index)
            if polygon is None:
                classes.add(CLASS_FILL_NOT_CLASSIFIED)
                continue
            thickness_pt = _fill_thickness_at_edge(polygon, first, second)
            fact = facts.get(fill_index)
            layer = (fact.layer if fact is not None else path_layers.get(fill_index, ""))
            fill_class = _layer_and_thickness_class(
                layer, thickness_pt, frame_mm=frame_mm, lining_mm=lining_mm, mm_per_pt=mm_per_pt,
            )
            if fill_class not in _RESOLVED_EDGE_CLASSES:
                fallback = _unique_fill_statement_class(
                    polygon, layer=layer, frame_mm=frame_mm, lining_mm=lining_mm, mm_per_pt=mm_per_pt,
                )
                if fallback is not None:
                    fill_class = fallback
            classes.add(fill_class)
            continue
        if not owner.startswith(_STRIP_OWNER_PREFIX):
            classes.add(CLASS_OWNER_UNKNOWN)
            continue
        try:
            path_index = int(owner[len(_STRIP_OWNER_PREFIX):])
        except ValueError:
            classes.add(CLASS_OWNER_UNKNOWN)
            continue
        fact = facts.get(path_index)
        pair_thickness = _unique_stroke_pair_thickness(
            path_index, first, second, stroke_pairs_by_path,
        )
        if fact is not None and fact.is_strip:
            thickness_pt = pair_thickness if pair_thickness is not None else fact.thickness_pt
            classes.add(_layer_and_thickness_class(
                fact.layer, thickness_pt, frame_mm=frame_mm, lining_mm=lining_mm, mm_per_pt=mm_per_pt,
            ))
            continue
        if pair_thickness is not None:
            layer = path_layers.get(path_index, "")
            if fact is not None:
                layer = fact.layer or layer
            classes.add(_layer_and_thickness_class(
                layer, pair_thickness, frame_mm=frame_mm, lining_mm=lining_mm, mm_per_pt=mm_per_pt,
            ))
            continue
        if fact is not None and not fact.is_strip:
            classes.add(CLASS_FILL_NOT_CLASSIFIED)
            continue
        if path_index in unfilled_paths and lining_mm is not None:
            layer = path_layers.get(path_index, "")
            kind = _layer_kind(layer)
            if kind == "internal":
                classes.add(CLASS_DRAWN_LINING_FACE)
                continue
            if kind == "external":
                classes.add(CLASS_EXTERNAL_DRAWN_INNER_FACE)
                continue
        classes.add(CLASS_OWNER_UNKNOWN)
    if len(classes) == 1:
        only = next(iter(classes))
        if (
            only == CLASS_INTERNAL_THICKNESS_MISMATCH
            and frame_mm is not None
            and mm_per_pt is not None
            and math.hypot(float(second[0]) - float(first[0]), float(second[1]) - float(first[1]))
            <= (float(frame_mm) / float(mm_per_pt)) + NOISE_PT
        ):
            return CLASS_DRAWN_LINING_FACE
        return only
    return CLASS_OWNERS_MIXED


def classify_ring_face_identity(
    ring: LayeredRoomRingRecord,
    *,
    strip_facts: Mapping[int, WallStripFact],
    statements: Sequence[Any],
    mm_per_pt: Optional[float],
    room_is_wet_area: Optional[bool] = None,
    fill_polygons: Optional[Mapping[int, Any]] = None,
    stroke_pairs_by_path: Optional[Mapping[int, Sequence[Sequence[float]]]] = None,
    path_layers: Optional[Mapping[int, str]] = None,
    unfilled_paths: Optional[frozenset[int]] = None,
) -> RingFaceIdentity:
    """Classify every wall edge of ``ring`` (see ``_classify_edges``)."""
    points = ring.polygon_pdf_pts
    owners = ring.edge_owner_ids if len(ring.edge_owner_ids) == len(points) else tuple(() for _ in points)
    return _classify_edges(
        ring.record_id, points, owners, strip_facts=strip_facts, statements=statements,
        mm_per_pt=mm_per_pt, room_is_wet_area=room_is_wet_area,
        fill_polygons=fill_polygons, stroke_pairs_by_path=stroke_pairs_by_path,
        path_layers=path_layers, unfilled_paths=unfilled_paths,
    )


def record_edge_owners(record: Any) -> tuple[tuple[str, ...], ...]:
    """Per polygon edge, the wall owners of a ``SourceRoomFaceRecord`` ring face; an edge no wall owns is a chord.

    The converter never lists a doorway chord as a wall owner, so the edges without an owner are exactly the
    planarization chords.
    """
    from pb_source_room_face_authority import _edge

    points = record.polygon_pdf_pts
    by_edge: dict[Any, list[str]] = {}
    for owner, edge in record.boundary_wall_edges:
        by_edge.setdefault(edge, []).append(str(owner))
    out: list[tuple[str, ...]] = []
    for index in range(len(points)):
        owners = tuple(sorted(by_edge.get(_edge(points[index], points[(index + 1) % len(points)]), ())))
        out.append(owners if owners else (_CLOSURE_OWNER_PREFIX + "unowned",))
    return tuple(out)


def classify_record_face_identity(
    record: Any,
    *,
    strip_facts: Mapping[int, WallStripFact],
    statements: Sequence[Any],
    mm_per_pt: Optional[float],
    room_is_wet_area: Optional[bool] = None,
    fill_polygons: Optional[Mapping[int, Any]] = None,
    stroke_pairs_by_path: Optional[Mapping[int, Sequence[Sequence[float]]]] = None,
    path_layers: Optional[Mapping[int, str]] = None,
    unfilled_paths: Optional[frozenset[int]] = None,
) -> RingFaceIdentity:
    """The same classification for a sealed ``SourceRoomFaceRecord`` produced from a ring."""
    return _classify_edges(
        str(record.record_id), tuple(record.polygon_pdf_pts), record_edge_owners(record),
        strip_facts=strip_facts, statements=statements, mm_per_pt=mm_per_pt, room_is_wet_area=room_is_wet_area,
        fill_polygons=fill_polygons, stroke_pairs_by_path=stroke_pairs_by_path,
        path_layers=path_layers, unfilled_paths=unfilled_paths,
    )


def _classify_edges(
    record_id: str,
    points: Sequence[Sequence[float]],
    owners_by_edge: Sequence[Sequence[str]],
    *,
    strip_facts: Mapping[int, WallStripFact],
    statements: Sequence[Any],
    mm_per_pt: Optional[float],
    room_is_wet_area: Optional[bool] = None,
    fill_polygons: Optional[Mapping[int, Any]] = None,
    stroke_pairs_by_path: Optional[Mapping[int, Sequence[Sequence[float]]]] = None,
    path_layers: Optional[Mapping[int, str]] = None,
    unfilled_paths: Optional[frozenset[int]] = None,
) -> RingFaceIdentity:
    """Classify every wall edge. ``statements`` are authenticated WallBuildUpStatement records.

    ``mm_per_pt`` comes from the existing page-scale authority (never derived here); None leaves every strip
    unclassified. ``room_is_wet_area`` must be supplied by an authority when a statement carries a wet-area
    variant; None then leaves the lining open.
    """
    reasons: set[str] = set()
    variants = {
        (float(s.frame_mm), float(s.lining_mm), s.wet_area_lining_mm) for s in statements
        if getattr(s, "scope", "") == "internal_walls"
    }
    frame_mm: Optional[float] = None
    lining_mm: Optional[float] = None
    if not variants:
        reasons.add(REASON_STATEMENT_UNAVAILABLE)
    elif len(variants) > 1:
        reasons.add(REASON_STATEMENTS_CONFLICT)  # two readings of the build-up: neither is chosen
    else:
        frame_mm, lining_mm, wet_area_lining_mm = next(iter(variants))
        if wet_area_lining_mm is not None and room_is_wet_area is not False:
            reasons.add(REASON_WET_AREA_STATUS)
    scale_ok = (
        mm_per_pt is not None and isinstance(mm_per_pt, (int, float)) and math.isfinite(mm_per_pt) and mm_per_pt > 0.0
    )
    if not scale_ok:
        reasons.add(REASON_SCALE_UNAVAILABLE)

    lengths: dict[str, float] = {}
    wall_edges = chord_edges = 0
    offsets: list[tuple[int, float]] = []
    for index, owners in enumerate(owners_by_edge):
        first, second = points[index], points[(index + 1) % len(points)]
        length = math.hypot(first[0] - second[0], first[1] - second[1])
        if owners and all(owner.startswith(_CLOSURE_OWNER_PREFIX) for owner in owners):
            chord_edges += 1
            lengths[CLASS_THRESHOLD_CHORD] = lengths.get(CLASS_THRESHOLD_CHORD, 0.0) + length
            continue
        wall_edges += 1
        edge_class = _edge_class(
            owners, strip_facts, first=first, second=second,
            frame_mm=frame_mm, lining_mm=lining_mm,
            mm_per_pt=float(mm_per_pt) if scale_ok else None,  # type: ignore[arg-type]
            fill_polygons=fill_polygons, stroke_pairs_by_path=stroke_pairs_by_path,
            path_layers=path_layers, unfilled_paths=unfilled_paths,
        )
        lengths[edge_class] = lengths.get(edge_class, 0.0) + length
        if edge_class == CLASS_LINED_INTERNAL_FRAME_FACE and lining_mm is not None:
            offsets.append((index, lining_mm))
    if wall_edges == 0:
        reasons.add(REASON_NO_WALL_EDGES)
    unresolved_classes = {
        name for name in lengths
        if name not in _RESOLVED_EDGE_CLASSES
    }
    reasons |= unresolved_classes
    resolved = not reasons
    return RingFaceIdentity(
        ring_record_id=record_id,
        verdict=VERDICT_RESOLVED if resolved else VERDICT_UNRESOLVED,
        reason_codes=tuple(sorted(reasons)),
        class_lengths_pt=tuple((name, round(lengths[name], 4)) for name in sorted(lengths)),
        wall_edge_count=wall_edges, chord_edge_count=chord_edges,
        lined_edge_offsets_mm=tuple(offsets) if resolved else (),
        statement_text_sha256=tuple(sorted({getattr(s, "text_sha256", "") for s in statements})),
    )


def apply_lined_finished_face_polygon(
    polygon_pdf_pts: Sequence[Sequence[float]],
    lined_edge_offsets_mm: Sequence[tuple[int, float]],
    mm_per_pt: float,
) -> Optional[tuple[tuple[float, float], ...]]:
    """Inset only the wall edges that carry an authenticated lining, in page points.

    External drawn inner faces and doorway chords are omitted from ``lined_edge_offsets_mm``
    and stay put. A missing or non-finite scale, or a lining that eats the face, abstains.
    """
    from shapely.geometry import Point, Polygon

    points = [(float(x), float(y)) for x, y in polygon_pdf_pts]
    if len(points) < 3:
        return None
    if not isinstance(mm_per_pt, (int, float)) or not math.isfinite(mm_per_pt) or mm_per_pt <= 0.0:
        return None
    face = Polygon(points)
    if not face.is_valid:
        face = face.buffer(0)
    if face.is_empty:
        return None
    offsets = {int(index): float(offset_mm) for index, offset_mm in lined_edge_offsets_mm}
    if not offsets:
        return tuple((float(x), float(y)) for x, y in points)
    n = len(points)
    for index in range(n):
        offset_mm = offsets.get(index)
        if offset_mm is None or not math.isfinite(offset_mm) or offset_mm <= 0.0:
            continue
        offset_pt = offset_mm / float(mm_per_pt)
        if offset_pt <= 0.0:
            continue
        first, second = points[index], points[(index + 1) % n]
        dx, dy = second[0] - first[0], second[1] - first[1]
        length = math.hypot(dx, dy)
        if length <= NOISE_PT:
            continue
        nx, ny = dy / length, -dx / length
        mid = ((first[0] + second[0]) / 2.0, (first[1] + second[1]) / 2.0)
        probe = Point(mid[0] + nx * (NOISE_PT * 2.0), mid[1] + ny * (NOISE_PT * 2.0))
        if not face.covers(probe):
            nx, ny = -nx, -ny
        strip = Polygon((
            first, second,
            (second[0] + nx * offset_pt, second[1] + ny * offset_pt),
            (first[0] + nx * offset_pt, first[1] + ny * offset_pt),
        ))
        if not strip.is_valid or strip.is_empty:
            continue
        face = face.difference(strip)
        if face.geom_type == "MultiPolygon":
            face = max(face.geoms, key=lambda geom: geom.area)
        if face.is_empty:
            return None
    coords = tuple((float(x), float(y)) for x, y in face.exterior.coords[:-1])
    if len(coords) < 3:
        return None
    return coords


__all__ = [
    "CLASS_DRAWN_FINISHED_BUILD_UP",
    "CLASS_DRAWN_LINING_FACE",
    "CLASS_EXTERNAL_DRAWN_INNER_FACE",
    "CLASS_EXTERNAL_LINING_NOT_STATED",
    "CLASS_FILL_NOT_CLASSIFIED",
    "CLASS_INTERNAL_STATEMENT_UNUSABLE",
    "CLASS_INTERNAL_THICKNESS_MISMATCH",
    "CLASS_LAYER_NOT_CLASSIFIED",
    "CLASS_LINED_INTERNAL_FRAME_FACE",
    "CLASS_OWNERS_MIXED",
    "CLASS_OWNER_UNKNOWN",
    "CLASS_THRESHOLD_CHORD",
    "REASON_NO_WALL_EDGES",
    "REASON_SCALE_UNAVAILABLE",
    "REASON_STATEMENTS_CONFLICT",
    "REASON_STATEMENT_UNAVAILABLE",
    "REASON_WET_AREA_STATUS",
    "RingFaceIdentity",
    "VERDICT_RESOLVED",
    "VERDICT_UNRESOLVED",
    "WallStripFact",
    "apply_lined_finished_face_polygon",
    "classify_record_face_identity",
    "classify_ring_face_identity",
    "record_edge_owners",
    "wall_face_source_support",
    "wall_strip_facts",
]
