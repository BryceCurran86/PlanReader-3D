"""Bind a unique source-drawn door swing/leaf to an already-hosted opening (shadow).

PhysicalOpeningAuthority records many wall-band interruptions as
``jamb_bounded_two_face_interruption``. That pattern is not a door kind: windows
interrupt walls too. A unique cubic quarter-swing with its radial leaf, or a
unique 45-degree wall-layer leaf, is source door geometry. This module never
mints a second physical opening. It only fills ``opening_kind`` when exactly one
already-hosted, unkinded opening sits at that swing. Default-off; not FIRM.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import replace
from typing import Any, Mapping, Sequence

from pb_layered_wall_doorway_room_ring_shadow import (
    NOISE_PT,
    _swing_arcs,
    _visible_source_stroke_paint,
    _wall_rows,
    _xy,
)
from pb_live_physical_opening_void_composition import (
    LiveCanonicalOpeningObject,
    LivePhysicalOpeningVoidComposition,
)
from pb_migration_contracts import stable_contract_id
from pb_opening_kind_authority import (
    SOURCE_DIAGONAL_DOOR_LEAF,
    SOURCE_QUARTER_SWING_AND_RADIAL_LEAF,
    resolve_opening_kind,
)


# Production 2.5 pt snap: CAD hinge/jamb endpoints sit this far from the
# interruption segment. Not a new geometric authority.
_SWING_OPENING_BIND_PT = 2.5
_MIN_DIAGONAL_LEAF_PT = 10.0
_MAX_DIAGONAL_LEAF_PT = 140.0


def _point_to_segment(
    point: tuple[float, float],
    geom: Sequence[float],
) -> float:
    if len(geom) < 4:
        return float("inf")
    x0, y0, x1, y1 = (float(value) for value in geom[:4])
    vx, vy = x1 - x0, y1 - y0
    length2 = vx * vx + vy * vy
    if length2 <= 1e-12:
        return math.hypot(point[0] - x0, point[1] - y0)
    t = max(0.0, min(1.0, ((point[0] - x0) * vx + (point[1] - y0) * vy) / length2))
    return math.hypot(point[0] - (x0 + t * vx), point[1] - (y0 + t * vy))


def _opening_distance(
    opening: LiveCanonicalOpeningObject,
    point: tuple[float, float],
) -> float:
    geoms = opening.source_geometries or ()
    if not geoms:
        return float("inf")
    return min(_point_to_segment(point, geom) for geom in geoms)


def _hosted_unkinded(opening: LiveCanonicalOpeningObject) -> bool:
    if type(opening) is not LiveCanonicalOpeningObject:
        return False
    if str(opening.opening_kind or "").strip():
        return False
    if not str(opening.host_wall_id or "").strip():
        return False
    if not (
        str(opening.host_binding_record_id or "").strip()
        or str(opening.host_frame_record_id or "").strip()
    ):
        return False
    return True


def _collect_diagonal_leaves(
    drawings: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    leaves: list[dict[str, Any]] = []
    for index, row in _wall_rows(drawings):
        if row.get("fill") is not None or not _visible_source_stroke_paint(row):
            continue
        items = list(row.get("items", ()))
        if len(items) != 1 or items[0][0] != "l":
            continue
        start, end = _xy(items[0][1]), _xy(items[0][2])
        dx, dy = abs(start[0] - end[0]), abs(start[1] - end[1])
        length = math.hypot(dx, dy)
        if not (_MIN_DIAGONAL_LEAF_PT <= length <= _MAX_DIAGONAL_LEAF_PT):
            continue
        if abs(dx - dy) > max(NOISE_PT, 0.02 * length):
            continue
        leaves.append(
            {
                "leaf": index,
                "centre": start,
                "closed_tip": end,
                "pattern": SOURCE_DIAGONAL_DOOR_LEAF,
            }
        )
    return tuple(leaves)


def _witnesses(
    drawings: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    arcs, _rejected = _swing_arcs(drawings)
    cubic = tuple(
        {
            "arc": item["arc"],
            "leaf": item["leaf"],
            "centre": tuple(item["centre"]),
            "closed_tip": tuple(item["closed_tip"]),
            "pattern": SOURCE_QUARTER_SWING_AND_RADIAL_LEAF,
        }
        for item in arcs
    )
    return cubic + _collect_diagonal_leaves(drawings)


def _unique_bindings(
    openings: Sequence[LiveCanonicalOpeningObject],
    witnesses: Sequence[Mapping[str, Any]],
) -> Mapping[str, Mapping[str, Any]]:
    """Unique painted swing owns one opening; typed neighbours still consume it.

    Uniqueness looks at every opening on the page that sits on the hinge or
    closed tip. Only an already-hosted unkinded record may be updated. An
    already-typed door or window at that swing keeps the witness; it is not
    freed for another opening.
    """
    by_id = {
        item.canonical_opening_id: item
        for item in openings
        if type(item) is LiveCanonicalOpeningObject
    }
    witness_hits: list[tuple[Mapping[str, Any], tuple[str, ...]]] = []
    for witness in witnesses:
        hinge = tuple(float(v) for v in witness["centre"])
        tip = tuple(float(v) for v in witness["closed_tip"])
        hits = []
        for opening in by_id.values():
            near_hinge = _opening_distance(opening, hinge) <= _SWING_OPENING_BIND_PT
            near_tip = _opening_distance(opening, tip) <= _SWING_OPENING_BIND_PT
            far_hinge = _opening_distance(opening, hinge)
            far_tip = _opening_distance(opening, tip)
            # A leaf must touch the interruption at exactly one end. A cubic
            # swing may have the hinge on the jamb and the closed tip on the
            # other jamb of the same interruption, so either end is enough
            # when the other end is not a second opening.
            if near_hinge or near_tip:
                if witness.get("pattern") == SOURCE_DIAGONAL_DOOR_LEAF:
                    if not (
                        min(far_hinge, far_tip) <= _SWING_OPENING_BIND_PT
                        < max(far_hinge, far_tip)
                    ):
                        continue
                hits.append(opening.canonical_opening_id)
        witness_hits.append((witness, tuple(hits)))

    by_opening: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for witness, hits in witness_hits:
        if len(hits) != 1:
            continue
        target = by_id.get(hits[0])
        if target is None or not _hosted_unkinded(target):
            continue
        by_opening[hits[0]].append(witness)
    return {
        opening_id: bound[0]
        for opening_id, bound in by_opening.items()
        if len(bound) == 1
    }


def _leaf_evidence_id(page_id: str, witness: Mapping[str, Any]) -> str:
    return stable_contract_id(
        "source_drawn_door_leaf",
        {
            "page_id": page_id,
            "pattern": witness["pattern"],
            "arc": witness.get("arc"),
            "leaf": witness.get("leaf"),
            "centre": tuple(round(float(v), 5) for v in witness["centre"]),
            "closed_tip": tuple(round(float(v), 5) for v in witness["closed_tip"]),
        },
        digest_chars=32,
    )


def apply_source_quarter_swing_opening_kinds(
    composition: LivePhysicalOpeningVoidComposition,
    *,
    drawings_by_page_id: Mapping[str, Sequence[Mapping[str, Any]]],
) -> LivePhysicalOpeningVoidComposition:
    """Fill door kind on uniquely hosted openings that own a source swing/leaf."""
    if type(composition) is not LivePhysicalOpeningVoidComposition:
        raise TypeError("composition must be LivePhysicalOpeningVoidComposition")

    by_page: dict[str, list[LiveCanonicalOpeningObject]] = defaultdict(list)
    for opening in composition.canonical_openings:
        by_page[str(opening.page_id)].append(opening)

    updated: dict[str, LiveCanonicalOpeningObject] = {}
    for page_id, openings in by_page.items():
        drawings = drawings_by_page_id.get(page_id)
        if not drawings:
            continue
        bindings = _unique_bindings(openings, _witnesses(drawings))
        for opening in openings:
            witness = bindings.get(opening.canonical_opening_id)
            if witness is None:
                continue
            resolution = resolve_opening_kind(structural_pattern=witness["pattern"])
            if resolution.opening_kind != "door":
                continue
            evidence_id = _leaf_evidence_id(page_id, witness)
            evidence_ids = tuple(
                dict.fromkeys((*opening.evidence_ids, evidence_id))
            )
            updated[opening.canonical_opening_id] = replace(
                opening,
                opening_kind="door",
                evidence_ids=evidence_ids,
            )

    if not updated:
        return composition
    return replace(
        composition,
        canonical_openings=tuple(
            updated.get(item.canonical_opening_id, item)
            for item in composition.canonical_openings
        ),
    )


__all__ = [
    "SOURCE_DIAGONAL_DOOR_LEAF",
    "SOURCE_QUARTER_SWING_AND_RADIAL_LEAF",
    "apply_source_quarter_swing_opening_kinds",
]
