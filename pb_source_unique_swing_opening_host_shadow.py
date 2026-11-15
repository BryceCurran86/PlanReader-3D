"""Bind a unique source door swing hinge to one unhosted opening (shadow).

``apply_source_quarter_swing_opening_kinds`` only classifies an already-hosted
opening. Many 3Laurel jamb-bounded interruptions stay unhosted because W4
two-face lineage cannot map the four face primitives. A unique cubic
quarter-swing or 45-degree leaf already identifies the doorway. This module
fills ``host_wall_id`` / ``host_binding_record_id`` when:

* exactly one unhosted, non-window opening sits at the hinge (2.5 pt snap)
* no already-hosted opening sits at that same hinge

The closed-leaf tip is ignored: both jambs of one door often mint their own
interruption, and choosing the tip would duplicate the doorway. Two unhosted
openings at one hinge abstain. An existing host is never overwritten. No
second physical opening is minted. Default-off; not FIRM.

``apply_source_one_room_envelope_external_roles`` then records a CORROBORATED
EXTERNAL whole-wall role for that host when the hinge sits on the outer
contour of the morphologically closed wall-ink footprint. Closing uses half
the existing 140 pt doorway/leaf maximum so rooms fill and doorways close;
the hinge must then lie within two stroke-pair wall thicknesses of that
outer contour. That is envelope topology, not a CAD layer name, thickness
rank, or bounding-box perimeter. Internal hinges stay inside the footprint.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from shapely.geometry import Point
from shapely.ops import unary_union

from pb_layered_wall_doorway_room_ring_shadow import (
    _STROKE_PAIR_THICK_MAX,
    _collect_strips,
)
from pb_live_physical_opening_void_composition import (
    LiveCanonicalOpeningObject,
    LivePhysicalOpeningVoidComposition,
)
from pb_live_whole_wall_role_composition import (
    LIVE_WHOLE_WALL_ROLE_PARTIAL,
    LIVE_WHOLE_WALL_ROLE_RESOLVED,
    LiveWholeWallRoleComposition,
    LiveWholeWallRoleTrace,
)
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_source_quarter_swing_opening_kind_shadow import (
    _SWING_OPENING_BIND_PT,
    _opening_distance,
    _witnesses,
)
from pb_wall_role_authority import WallRoleClassification


SOURCE_UNIQUE_SWING_OPENING_HOST = "source_unique_swing_opening_host"
SOURCE_ONE_ROOM_ENVELOPE_EXTERNAL_ROLE = "source_envelope_external_wall_role"
# Half of the existing 10–140 pt doorway/leaf span filter. Morphological
# closing at this radius fills rooms and doorways; it is not a measurement.
_ENVELOPE_CLOSE_PT = 70.0
_ENVELOPE_WALL_BAND_PT = _STROKE_PAIR_THICK_MAX * 2.0


def _unhosted_non_window(opening: LiveCanonicalOpeningObject) -> bool:
    if type(opening) is not LiveCanonicalOpeningObject:
        return False
    if str(opening.host_wall_id or "").strip():
        return False
    if str(opening.opening_kind or "").strip().lower() == "window":
        return False
    return True


def _hosted(opening: LiveCanonicalOpeningObject) -> bool:
    return bool(str(opening.host_wall_id or "").strip())


def _unique_hinge_hosts(
    openings: Sequence[LiveCanonicalOpeningObject],
    witnesses: Sequence[Mapping[str, Any]],
) -> Mapping[str, Mapping[str, Any]]:
    pool = tuple(item for item in openings if _unhosted_non_window(item))
    already = tuple(item for item in openings if _hosted(item))
    witness_hits: list[tuple[Mapping[str, Any], tuple[str, ...]]] = []
    for witness in witnesses:
        hinge = tuple(float(value) for value in witness["centre"])
        if any(
            _opening_distance(item, hinge) <= _SWING_OPENING_BIND_PT
            for item in already
        ):
            continue
        hits = tuple(
            item.canonical_opening_id
            for item in pool
            if _opening_distance(item, hinge) <= _SWING_OPENING_BIND_PT
        )
        witness_hits.append((witness, hits))

    by_opening: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for witness, hits in witness_hits:
        if len(hits) != 1:
            continue
        by_opening[hits[0]].append(witness)
    return {
        opening_id: bound[0]
        for opening_id, bound in by_opening.items()
        if len(bound) == 1
    }


def _host_ids(page_id: str, opening_id: str, witness: Mapping[str, Any]) -> tuple[str, str]:
    payload = {
        "page_id": page_id,
        "pattern": witness["pattern"],
        "arc": witness.get("arc"),
        "leaf": witness.get("leaf"),
        "centre": tuple(round(float(value), 5) for value in witness["centre"]),
    }
    host_wall_id = stable_contract_id(
        "opening_host_binding_group",
        payload,
        digest_chars=32,
    )
    host_binding_record_id = stable_contract_id(
        "opening_host_binding_v3",
        {
            **payload,
            "canonical_opening_id": opening_id,
            "host_wall_id": host_wall_id,
        },
        digest_chars=32,
    )
    return host_wall_id, host_binding_record_id


def apply_source_unique_swing_opening_hosts(
    composition: LivePhysicalOpeningVoidComposition,
    *,
    drawings_by_page_id: Mapping[str, Sequence[Mapping[str, Any]]],
) -> LivePhysicalOpeningVoidComposition:
    """Fill host identity on the unique unhosted opening at a source swing hinge."""
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
        bindings = _unique_hinge_hosts(openings, _witnesses(drawings))
        for opening in openings:
            witness = bindings.get(opening.canonical_opening_id)
            if witness is None:
                continue
            host_wall_id, host_binding_record_id = _host_ids(
                page_id, opening.canonical_opening_id, witness,
            )
            evidence_id = stable_contract_id(
                SOURCE_UNIQUE_SWING_OPENING_HOST,
                {
                    "page_id": page_id,
                    "canonical_opening_id": opening.canonical_opening_id,
                    "host_wall_id": host_wall_id,
                },
                digest_chars=32,
            )
            updated[opening.canonical_opening_id] = replace(
                opening,
                host_wall_id=host_wall_id,
                host_binding_record_id=host_binding_record_id,
                evidence_ids=tuple(
                    dict.fromkeys((*opening.evidence_ids, evidence_id))
                ),
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


def _closed_wall_footprint(drawings: Sequence[Mapping[str, Any]]):
    strips, other = _collect_strips(drawings)
    geoms = [strip.polygon for strip in strips] + [polygon for _index, polygon in other]
    geoms = [geom for geom in geoms if geom is not None and not geom.is_empty]
    if not geoms:
        return None
    filled = unary_union(
        [geom.buffer(_ENVELOPE_CLOSE_PT, join_style=2) for geom in geoms]
    ).buffer(-_ENVELOPE_CLOSE_PT, join_style=2)
    if filled.is_empty:
        return None
    return filled


def _envelope_exteriors(footprint) -> tuple:
    if footprint is None:
        return ()
    if footprint.geom_type == "Polygon":
        return (footprint.exterior,)
    if footprint.geom_type == "MultiPolygon":
        return tuple(polygon.exterior for polygon in footprint.geoms)
    return ()


def _hinge_on_envelope(
    hinge: tuple[float, float],
    footprint,
) -> bool:
    exteriors = _envelope_exteriors(footprint)
    if not exteriors:
        return False
    point = Point(hinge)
    distance = min(point.distance(ring) for ring in exteriors)
    return distance <= _ENVELOPE_WALL_BAND_PT


def apply_source_one_room_envelope_external_roles(
    roles: LiveWholeWallRoleComposition,
    composition: LivePhysicalOpeningVoidComposition,
    *,
    drawings_by_page_id: Mapping[str, Sequence[Mapping[str, Any]]],
    sliding_leaf_frame_closure: bool = False,
    dark_painted_wall_source: bool = False,
    wall_end_stroke_closures: bool = False,
) -> LiveWholeWallRoleComposition:
    """Stamp EXTERNAL on unique swing hosts that sit on the wall-ink envelope."""
    if type(roles) is not LiveWholeWallRoleComposition:
        raise TypeError("roles must be LiveWholeWallRoleComposition")
    if type(composition) is not LivePhysicalOpeningVoidComposition:
        raise TypeError("composition must be LivePhysicalOpeningVoidComposition")
    if type(sliding_leaf_frame_closure) is not bool:
        raise TypeError("sliding_leaf_frame_closure must be an explicit boolean")
    if type(dark_painted_wall_source) is not bool:
        raise TypeError("dark_painted_wall_source must be an explicit boolean")
    if type(wall_end_stroke_closures) is not bool:
        raise TypeError("wall_end_stroke_closures must be an explicit boolean")
    # Ring flags stay explicit-bool so the live collector can keep forwarding
    # them; envelope proof no longer rebuilds rings from those flags.
    _ = (
        sliding_leaf_frame_closure,
        dark_painted_wall_source,
        wall_end_stroke_closures,
    )

    existing = {
        str(trace.physical_wall_id)
        for trace in roles.traces
        if (
            str(trace.physical_wall_id or "").strip()
            and trace.role is WallRoleClassification.EXTERNAL
            and trace.status is EvidenceResolutionStatus.CORROBORATED
        )
    }
    by_page: dict[str, list[LiveCanonicalOpeningObject]] = defaultdict(list)
    for opening in composition.canonical_openings:
        by_page[str(opening.page_id)].append(opening)

    extra: list[LiveWholeWallRoleTrace] = []
    for page_id, openings in by_page.items():
        drawings = drawings_by_page_id.get(page_id)
        if not drawings:
            continue
        hosted = tuple(
            item for item in openings
            if str(item.host_wall_id or "").strip()
            and str(item.opening_kind or "").strip().lower() == "door"
        )
        if not hosted:
            continue
        footprint = _closed_wall_footprint(drawings)
        if footprint is None:
            continue
        witnesses = _witnesses(drawings)
        for opening in hosted:
            host_wall_id = str(opening.host_wall_id)
            if host_wall_id in existing:
                continue
            hinge_hits = []
            for witness in witnesses:
                hinge = tuple(float(value) for value in witness["centre"])
                if _opening_distance(opening, hinge) <= _SWING_OPENING_BIND_PT:
                    hinge_hits.append(hinge)
            if len(hinge_hits) != 1:
                continue
            if not _hinge_on_envelope(hinge_hits[0], footprint):
                continue
            record_id = stable_contract_id(
                SOURCE_ONE_ROOM_ENVELOPE_EXTERNAL_ROLE,
                {
                    "page_id": page_id,
                    "host_wall_id": host_wall_id,
                    "canonical_opening_id": opening.canonical_opening_id,
                },
                digest_chars=32,
            )
            extra.append(
                LiveWholeWallRoleTrace(
                    physical_wall_id=host_wall_id,
                    page_id=page_id,
                    decision_scope_id=f"live-page-{page_id}",
                    status=EvidenceResolutionStatus.CORROBORATED,
                    reason_codes=(SOURCE_ONE_ROOM_ENVELOPE_EXTERNAL_ROLE,),
                    record_id=record_id,
                    role=WallRoleClassification.EXTERNAL,
                )
            )
            existing.add(host_wall_id)

    if not extra:
        return roles
    traces = tuple((*roles.traces, *extra))
    reason_status = (
        LIVE_WHOLE_WALL_ROLE_PARTIAL
        if roles.traces
        else LIVE_WHOLE_WALL_ROLE_RESOLVED
    )
    return replace(
        roles,
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=tuple(
            dict.fromkeys(
                (reason_status, *roles.reason_codes, SOURCE_ONE_ROOM_ENVELOPE_EXTERNAL_ROLE)
            )
        ),
        traces=traces,
        role_selectors=MappingProxyType(dict(roles.role_selectors)),
    )


__all__ = [
    "SOURCE_ONE_ROOM_ENVELOPE_EXTERNAL_ROLE",
    "SOURCE_UNIQUE_SWING_OPENING_HOST",
    "apply_source_one_room_envelope_external_roles",
    "apply_source_unique_swing_opening_hosts",
]
