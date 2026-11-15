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
from pb_source_opening_identity_partition_shadow import (
    AMBIGUOUS,
    DISTINCT,
    SAME,
    compare_live_canonical_opening_identity,
    share_issued_aperture_ownership,
    share_source_jamb_vertex,
    share_source_jamb_vertex_at,
    source_segment_endpoint_at,
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
            "open_tip": tuple(item["open_tip"]),
            "closed_tip": tuple(item["closed_tip"]),
            "radius": float(item["radius"]),
            "pattern": SOURCE_QUARTER_SWING_AND_RADIAL_LEAF,
        }
        for item in arcs
    )
    return cubic + _collect_diagonal_leaves(drawings)


def _touches_witness_end(
    opening: LiveCanonicalOpeningObject,
    point: tuple[float, float],
) -> bool:
    return _opening_distance(opening, point) <= _SWING_OPENING_BIND_PT


def _witness_hits(
    openings: Sequence[LiveCanonicalOpeningObject],
    witness: Mapping[str, Any],
) -> tuple[LiveCanonicalOpeningObject, ...]:
    hinge = tuple(float(value) for value in witness["centre"])
    tip = tuple(float(value) for value in witness["closed_tip"])
    hits: list[LiveCanonicalOpeningObject] = []
    for opening in openings:
        near_hinge = _touches_witness_end(opening, hinge)
        near_tip = _touches_witness_end(opening, tip)
        far_hinge = _opening_distance(opening, hinge)
        far_tip = _opening_distance(opening, tip)
        # A leaf must touch the interruption at exactly one end. A cubic
        # swing may have the hinge on the jamb and the closed tip on the
        # other jamb of the same interruption, so either end is enough
        # when the other end is not a second opening.
        if not (near_hinge or near_tip):
            continue
        if witness.get("pattern") == SOURCE_DIAGONAL_DOOR_LEAF:
            if not (
                min(far_hinge, far_tip) <= _SWING_OPENING_BIND_PT
                < max(far_hinge, far_tip)
            ):
                continue
        hits.append(opening)
    return tuple(hits)


def _authenticated_same_viewport(
    left: LiveCanonicalOpeningObject,
    right: LiveCanonicalOpeningObject,
) -> bool:
    left_viewport = str(left.viewport_id or "").strip()
    right_viewport = str(right.viewport_id or "").strip()
    return bool(left_viewport and right_viewport and left_viewport == right_viewport)


def _local_swing_face_join(
    left: LiveCanonicalOpeningObject,
    right: LiveCanonicalOpeningObject,
    hinge: tuple[float, float],
    tip: tuple[float, float],
    relation: str,
) -> bool:
    """Join records of one doorway at this painted swing.

    DISTINCT never joins. SAME joins. AMBIGUOUS joins only with an
    authenticated shared viewport plus issued aperture ownership, a CAD
    vertex that is this witness's hinge or closed tip, or an unhosted
    jamb tick that reaches that hinge/tip from the hosted wall cut.
    """
    if relation == DISTINCT:
        return False
    if relation == SAME:
        return True
    if relation != AMBIGUOUS:
        return False
    if not _authenticated_same_viewport(left, right):
        return False
    if share_issued_aperture_ownership(left, right):
        return True
    if not share_source_jamb_vertex(left, right):
        return False
    if share_source_jamb_vertex_at(left, right, hinge) or share_source_jamb_vertex_at(
        left, right, tip
    ):
        return True
    left_hosted = bool(str(left.host_wall_id or "").strip())
    right_hosted = bool(str(right.host_wall_id or "").strip())
    if left_hosted == right_hosted:
        return False
    tick = right if left_hosted else left
    return source_segment_endpoint_at(tick, hinge) or source_segment_endpoint_at(tick, tip)


def _swing_identity_groups(
    hits: Sequence[LiveCanonicalOpeningObject],
    witness: Mapping[str, Any],
) -> tuple[frozenset[str], ...]:
    """Count physical doorways, not record IDs, at one painted swing.

    Vertex-joined jamb ticks collapse to one doorway only when the shared
    vertex is this witness's hinge or closed tip, both records share an
    authenticated viewport, and identity is not DISTINCT. A hinge-only
    cluster and a tip-only cluster collapse only when they share this
    swing's aperture: SAME, or AMBIGUOUS with the same viewport plus
    issued host/frame ownership or one hosted face and one unhosted tick.
    DISTINCT never joins. Opposite ends of a painted swing are not SAME
    by themselves. Adjacent openings that only share a far jamb stay
    competitors. Typed neighbours still consume the witness.
    """
    if not hits:
        return ()
    hinge = tuple(float(value) for value in witness["centre"])
    tip = tuple(float(value) for value in witness["closed_tip"])
    by_id = {item.canonical_opening_id: item for item in hits}
    parent = {item.canonical_opening_id: item.canonical_opening_id for item in hits}

    def find(identity: str) -> str:
        while parent[identity] != identity:
            parent[identity] = parent[parent[identity]]
            identity = parent[identity]
        return identity

    def union(left_id: str, right_id: str) -> None:
        root_left, root_right = find(left_id), find(right_id)
        if root_left != root_right:
            parent[root_right] = root_left

    for index, left in enumerate(hits):
        for right in hits[index + 1:]:
            relation = compare_live_canonical_opening_identity(left, right)
            if _local_swing_face_join(left, right, hinge, tip, relation):
                union(left.canonical_opening_id, right.canonical_opening_id)
    grouped: dict[str, list[str]] = {}
    for item in hits:
        grouped.setdefault(find(item.canonical_opening_id), []).append(
            item.canonical_opening_id
        )
    seen: list[str] = []
    for item in hits:
        root = find(item.canonical_opening_id)
        if root not in seen:
            seen.append(root)
    clusters = [frozenset(grouped[root]) for root in seen]
    classified: list[tuple[frozenset[str], bool, bool]] = []
    for members in clusters:
        at_hinge = any(_touches_witness_end(by_id[member], hinge) for member in members)
        at_tip = any(_touches_witness_end(by_id[member], tip) for member in members)
        classified.append((members, at_hinge, at_tip))
    hinge_only = [item for item in classified if item[1] and not item[2]]
    tip_only = [item for item in classified if item[2] and not item[1]]
    if (
        len(classified) == 2
        and len(hinge_only) == 1
        and len(tip_only) == 1
        and _hinge_tip_clusters_share_aperture(
            hinge_only[0][0], tip_only[0][0], by_id, hinge, tip,
        )
    ):
        return (hinge_only[0][0] | tip_only[0][0],)
    return tuple(item[0] for item in classified)


def _hinge_tip_clusters_share_aperture(
    hinge_members: frozenset[str],
    tip_members: frozenset[str],
    by_id: Mapping[str, LiveCanonicalOpeningObject],
    hinge: tuple[float, float],
    tip: tuple[float, float],
) -> bool:
    """True when opposite-end clusters are one doorway of this swing."""
    saw_doorway = False
    for left_id in hinge_members:
        for right_id in tip_members:
            left = by_id[left_id]
            right = by_id[right_id]
            relation = compare_live_canonical_opening_identity(left, right)
            if relation == DISTINCT:
                return False
            if _local_swing_face_join(left, right, hinge, tip, relation):
                saw_doorway = True
                continue
            if relation == SAME:
                saw_doorway = True
                continue
            if relation != AMBIGUOUS or not _authenticated_same_viewport(left, right):
                continue
            if share_issued_aperture_ownership(left, right):
                saw_doorway = True
                continue
            left_hosted = bool(str(left.host_wall_id or "").strip())
            right_hosted = bool(str(right.host_wall_id or "").strip())
            if left_hosted != right_hosted:
                saw_doorway = True
    return saw_doorway


def _unique_bindings(
    openings: Sequence[LiveCanonicalOpeningObject],
    witnesses: Sequence[Mapping[str, Any]],
) -> Mapping[str, Mapping[str, Any]]:
    """Unique painted swing owns one opening; typed neighbours still consume it.

    Uniqueness looks at every opening on the page that sits on the hinge or
    closed tip, then collapses proven-SAME jamb/tip records of one doorway.
    Only an already-hosted unkinded record may be updated. An already-typed
    door or window at that swing keeps the witness; it is not freed for
    another opening. Unique IDs alone never prove DISTINCT.
    """
    by_id = {
        item.canonical_opening_id: item
        for item in openings
        if type(item) is LiveCanonicalOpeningObject
    }
    page_openings = tuple(by_id.values())
    by_opening: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for witness in witnesses:
        hits = _witness_hits(page_openings, witness)
        groups = _swing_identity_groups(hits, witness)
        if len(groups) != 1:
            continue
        members = groups[0]
        typed = [
            by_id[member]
            for member in members
            if str(by_id[member].opening_kind or "").strip()
        ]
        if typed:
            continue
        hosted_unkinded = [
            by_id[member] for member in members if _hosted_unkinded(by_id[member])
        ]
        if len(hosted_unkinded) != 1:
            continue
        by_opening[hosted_unkinded[0].canonical_opening_id].append(witness)
    return {
        opening_id: bound[0]
        for opening_id, bound in by_opening.items()
        if len(bound) == 1
    }


_HINGED_WIDTH_BLOCK_PREFIXES = (
    "source_dashed_outer_line_cased_opening",
    "source_sliding_leaf_opening_host",
    "source_stacker_leaf_opening_host",
)


def _blocked_hinged_width_evidence(opening: LiveCanonicalOpeningObject) -> bool:
    return any(
        str(item).startswith(prefix)
        for prefix in _HINGED_WIDTH_BLOCK_PREFIXES
        for item in opening.evidence_ids
    )


def _hosted_hinged_door(opening: LiveCanonicalOpeningObject) -> bool:
    """Hosted personnel door, including one already kinded during composition."""
    kind = str(opening.opening_kind or "").strip().lower()
    if kind not in {"", "door"}:
        return False
    if _blocked_hinged_width_evidence(opening):
        return False
    if not str(opening.host_wall_id or "").strip():
        return False
    if not (
        str(opening.host_binding_record_id or "").strip()
        or str(opening.host_frame_record_id or "").strip()
    ):
        return False
    return True


def _unique_hosted_door_bindings(
    openings: Sequence[LiveCanonicalOpeningObject],
    witnesses: Sequence[Mapping[str, Any]],
) -> Mapping[str, Mapping[str, Any]]:
    """Unique painted swing owns one hosted hinged door, even if already kinded.

    Composition may already have stamped ``opening_kind='door'`` from a plan
    tag. Kinding then consumes that witness and refuses a second kind. Width
    still needs the unique in-swing figure on that same hosted door.
    A window, cased opening, or sliding/stacker host still consumes the
    witness. Unique IDs alone never prove DISTINCT.
    """
    by_id = {
        item.canonical_opening_id: item
        for item in openings
        if type(item) is LiveCanonicalOpeningObject
    }
    page_openings = tuple(by_id.values())
    by_opening: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for witness in witnesses:
        if str(witness.get("pattern") or "") != SOURCE_QUARTER_SWING_AND_RADIAL_LEAF:
            continue
        hits = _witness_hits(page_openings, witness)
        groups = _swing_identity_groups(hits, witness)
        if len(groups) != 1:
            continue
        members = groups[0]
        if any(
            str(by_id[member].opening_kind or "").strip().lower() == "window"
            for member in members
        ):
            continue
        hosted_doors = [
            by_id[member] for member in members if _hosted_hinged_door(by_id[member])
        ]
        if len(hosted_doors) != 1:
            continue
        by_opening[hosted_doors[0].canonical_opening_id].append(witness)
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
            if any(
                str(item).startswith("source_dashed_outer_line_cased_opening")
                for item in opening.evidence_ids
            ):
                continue
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
