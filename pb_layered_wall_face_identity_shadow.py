"""Which face of the wall does a doorway-closed room ring follow? (SHADOW ONLY, default-off, diagnostic).

``pb_layered_wall_doorway_room_ring_shadow`` recovers a room as the free region bounded by drawn wall-layer
ink. That boundary is the face of the DRAWN wall strip. Whether the drawn strip is the structural frame (with
a lining beyond it that the plan does not draw) or the finished wall is a source fact, not a geometric one.
This module classifies every wall edge of a ring by what the source states about the strip that owns it:

* ``lined_internal_frame_face``: the owning strip is on an internal-wall layer and its thickness at the page
  scale equals the frame thickness an authenticated build-up statement gives for internal walls. The drawn
  face is the frame face; the statement gives the lining beyond it. This is the ONLY resolved class.
* every other class is an explicit unresolved reason: a different thickness, a wall kind the set states
  nothing about (for example an external wall), an unclassified fill or layer, a strip the facts do not know.
* a doorway/threshold chord is not a wall and has no lining.

A ring is ``resolved`` only when EVERY wall edge is a lined internal frame face and no other fact (a statement
variant for wet areas, conflicting statements) leaves the lining open. Anything else is ``unresolved`` with the
reason codes and the edge length in each class, so the missing source fact is precise.

It never infers a lining thickness: the lining comes only from an authenticated statement. It issues no scale
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
    _collect_strips,
)

FACE_IDENTITY_SCHEMA_VERSION = "1.0.0"

VERDICT_RESOLVED = "resolved_internal_frame_face_with_stated_lining"
VERDICT_UNRESOLVED = "unresolved"

CLASS_LINED_INTERNAL_FRAME_FACE = "lined_internal_frame_face"
CLASS_INTERNAL_THICKNESS_MISMATCH = "internal_strip_thickness_not_the_stated_frame"
CLASS_INTERNAL_STATEMENT_UNUSABLE = "internal_strip_without_a_usable_statement_or_scale"
CLASS_EXTERNAL_LINING_NOT_STATED = "external_wall_internal_lining_not_stated"
CLASS_LAYER_NOT_CLASSIFIED = "wall_layer_not_classified"
CLASS_FILL_NOT_CLASSIFIED = "wall_fill_not_classified"
CLASS_OWNER_UNKNOWN = "wall_owner_not_in_strip_facts"
CLASS_OWNERS_MIXED = "edge_owned_by_mixed_classes"
CLASS_THRESHOLD_CHORD = "threshold_chord"

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
    return facts


def _layer_kind(layer: str) -> str:
    lowered = layer.lower()
    if "wallinternal" in lowered:
        return "internal"
    if "wallexternal" in lowered:
        return "external"
    return "other"


def _edge_class(
    owners: Sequence[str], facts: Mapping[int, WallStripFact], *, frame_mm: Optional[float], mm_per_pt: Optional[float],
) -> str:
    classes: set[str] = set()
    for owner in owners:
        if owner.startswith(_FILL_OWNER_PREFIX):
            classes.add(CLASS_FILL_NOT_CLASSIFIED)
            continue
        if not owner.startswith(_STRIP_OWNER_PREFIX):
            classes.add(CLASS_OWNER_UNKNOWN)
            continue
        try:
            fact = facts.get(int(owner[len(_STRIP_OWNER_PREFIX):]))
        except ValueError:
            fact = None
        if fact is None:
            classes.add(CLASS_OWNER_UNKNOWN)
            continue
        if not fact.is_strip:
            classes.add(CLASS_FILL_NOT_CLASSIFIED)
            continue
        kind = _layer_kind(fact.layer)
        if kind == "external":
            classes.add(CLASS_EXTERNAL_LINING_NOT_STATED)
        elif kind == "other":
            classes.add(CLASS_LAYER_NOT_CLASSIFIED)
        elif frame_mm is None or mm_per_pt is None or fact.thickness_pt is None:
            classes.add(CLASS_INTERNAL_STATEMENT_UNUSABLE)
        elif abs(fact.thickness_pt * mm_per_pt - frame_mm) <= NOISE_PT * mm_per_pt:
            classes.add(CLASS_LINED_INTERNAL_FRAME_FACE)
        else:
            classes.add(CLASS_INTERNAL_THICKNESS_MISMATCH)
    if len(classes) == 1:
        return next(iter(classes))
    return CLASS_OWNERS_MIXED


def classify_ring_face_identity(
    ring: LayeredRoomRingRecord,
    *,
    strip_facts: Mapping[int, WallStripFact],
    statements: Sequence[Any],
    mm_per_pt: Optional[float],
    room_is_wet_area: Optional[bool] = None,
) -> RingFaceIdentity:
    """Classify every wall edge of ``ring`` (see ``_classify_edges``)."""
    points = ring.polygon_pdf_pts
    owners = ring.edge_owner_ids if len(ring.edge_owner_ids) == len(points) else tuple(() for _ in points)
    return _classify_edges(
        ring.record_id, points, owners, strip_facts=strip_facts, statements=statements,
        mm_per_pt=mm_per_pt, room_is_wet_area=room_is_wet_area,
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
) -> RingFaceIdentity:
    """The same classification for a sealed ``SourceRoomFaceRecord`` produced from a ring."""
    return _classify_edges(
        str(record.record_id), tuple(record.polygon_pdf_pts), record_edge_owners(record),
        strip_facts=strip_facts, statements=statements, mm_per_pt=mm_per_pt, room_is_wet_area=room_is_wet_area,
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
            owners, strip_facts, frame_mm=frame_mm, mm_per_pt=float(mm_per_pt) if scale_ok else None,  # type: ignore[arg-type]
        )
        lengths[edge_class] = lengths.get(edge_class, 0.0) + length
        if edge_class == CLASS_LINED_INTERNAL_FRAME_FACE and lining_mm is not None:
            offsets.append((index, lining_mm))
    if wall_edges == 0:
        reasons.add(REASON_NO_WALL_EDGES)
    unresolved_classes = {name for name in lengths if name not in (CLASS_LINED_INTERNAL_FRAME_FACE, CLASS_THRESHOLD_CHORD)}
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


__all__ = [
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
    "classify_record_face_identity",
    "classify_ring_face_identity",
    "record_edge_owners",
    "wall_strip_facts",
]
