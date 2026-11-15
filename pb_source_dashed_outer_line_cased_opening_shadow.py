"""Tag unique dashed-inner + outer-wall openings so they stay openings, not doors.

Owner source rule: dashed inner lines with solid outside wall lines are a cased
opening. This module never mints a physical opening, never sets door kind, never
binds 2100 mm or a stacked width/height pair, and never uses room labels.
Default-off at the live collector; the wall-trace ring builder fills the same
span as a doorway closure. Not FIRM.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping, Sequence

from shapely.geometry import Point

from pb_layered_wall_doorway_room_ring_shadow import (
    collect_dashed_outer_line_cased_openings,
)
from pb_live_physical_opening_void_composition import (
    LiveCanonicalOpeningObject,
    LivePhysicalOpeningVoidComposition,
)
from pb_migration_contracts import stable_contract_id
from pb_source_quarter_swing_opening_kind_shadow import (
    _SWING_OPENING_BIND_PT,
    drawing_viewport_id_for_page,
    opening_matches_drawing_viewport,
)


SOURCE_DASHED_OUTER_LINE_CASED_OPENING = "source_dashed_outer_line_cased_opening"


def opening_has_cased_opening_evidence(opening: LiveCanonicalOpeningObject) -> bool:
    return any(
        str(item).startswith(SOURCE_DASHED_OUTER_LINE_CASED_OPENING)
        for item in opening.evidence_ids
    )


def _opening_midpoints(
    opening: LiveCanonicalOpeningObject,
) -> tuple[tuple[float, float], ...]:
    points: list[tuple[float, float]] = []
    for geom in opening.source_geometries or ():
        if len(geom) < 4:
            continue
        points.append(
            (
                (float(geom[0]) + float(geom[2])) / 2.0,
                (float(geom[1]) + float(geom[3])) / 2.0,
            )
        )
    return tuple(points)


def _opening_in_cased(
    opening: LiveCanonicalOpeningObject,
    cased: Any,
    drawing_viewport_id: object,
) -> bool:
    if not opening_matches_drawing_viewport(opening, drawing_viewport_id):
        return False
    rect = cased.wall_rect()
    return any(
        rect.distance(Point(mid)) <= _SWING_OPENING_BIND_PT
        for mid in _opening_midpoints(opening)
    )


def _span_positions(
    opening: LiveCanonicalOpeningObject,
    cased: Any,
) -> tuple[float, ...]:
    if cased.horizontal:
        return tuple(mid[0] for mid in _opening_midpoints(opening))
    return tuple(mid[1] for mid in _opening_midpoints(opening))


def _near_span_end(opening: LiveCanonicalOpeningObject, cased: Any, end: float) -> bool:
    return any(
        abs(position - float(end)) <= _SWING_OPENING_BIND_PT
        for position in _span_positions(opening, cased)
    )


def _unique_cased_hits(
    openings: Sequence[LiveCanonicalOpeningObject],
    cased: Any,
    drawing_viewport_id: object,
) -> tuple[LiveCanonicalOpeningObject, ...]:
    """One interruption, or the two jamb ticks of this one cased span."""
    hits = tuple(
        item
        for item in openings
        if type(item) is LiveCanonicalOpeningObject
        and str(item.opening_kind or "").strip().lower() != "door"
        and not opening_has_cased_opening_evidence(item)
        and _opening_in_cased(item, cased, drawing_viewport_id)
    )
    if len(hits) == 1:
        return hits
    if len(hits) != 2:
        return ()
    left, right = hits
    left_lo = _near_span_end(left, cased, cased.lo)
    left_hi = _near_span_end(left, cased, cased.hi)
    right_lo = _near_span_end(right, cased, cased.lo)
    right_hi = _near_span_end(right, cased, cased.hi)
    if (left_lo and right_hi and not left_hi and not right_lo) or (
        left_hi and right_lo and not left_lo and not right_hi
    ):
        return hits
    return ()


def apply_source_dashed_outer_line_cased_openings(
    composition: LivePhysicalOpeningVoidComposition,
    *,
    drawings_by_page_id: Mapping[str, Sequence[Mapping[str, Any]]],
    drawing_viewport_id_by_page_id: Mapping[str, str] | None = None,
) -> LivePhysicalOpeningVoidComposition:
    """Stamp cased-opening evidence; never classify the record as a door.

    Page ink is not a viewport. Callers must supply the authenticated
    drawing viewport for that page. Openings with a missing, blank or
    foreign viewport stay untagged.
    """
    if type(composition) is not LivePhysicalOpeningVoidComposition:
        raise TypeError("composition must be LivePhysicalOpeningVoidComposition")

    by_page: dict[str, list[LiveCanonicalOpeningObject]] = {}
    for opening in composition.canonical_openings:
        by_page.setdefault(str(opening.page_id), []).append(opening)

    updated: dict[str, LiveCanonicalOpeningObject] = {}
    for page_id, openings in by_page.items():
        drawings = drawings_by_page_id.get(page_id)
        drawing_viewport_id = drawing_viewport_id_for_page(
            page_id, drawing_viewport_id_by_page_id,
        )
        if not drawings or not drawing_viewport_id:
            continue
        scoped = tuple(
            item
            for item in openings
            if opening_matches_drawing_viewport(item, drawing_viewport_id)
        )
        if not scoped:
            continue
        cased_openings = collect_dashed_outer_line_cased_openings(drawings)
        if not cased_openings:
            continue
        claimed: dict[str, int] = {}
        unique: list[tuple[Any, LiveCanonicalOpeningObject]] = []
        for cased in cased_openings:
            hits = _unique_cased_hits(scoped, cased, drawing_viewport_id)
            if not hits:
                continue
            for opening in hits:
                unique.append((cased, opening))
                claimed[opening.canonical_opening_id] = (
                    claimed.get(opening.canonical_opening_id, 0) + 1
                )
        for cased, opening in unique:
            if claimed[opening.canonical_opening_id] != 1:
                continue
            if opening.canonical_opening_id in updated:
                continue
            evidence_id = stable_contract_id(
                SOURCE_DASHED_OUTER_LINE_CASED_OPENING,
                {
                    "page_id": page_id,
                    "viewport_id": drawing_viewport_id,
                    "canonical_opening_id": opening.canonical_opening_id,
                    "band": [round(v, 5) for v in cased.band],
                    "span": [round(cased.lo, 5), round(cased.hi, 5)],
                    "native": list(cased.native_path_indices),
                },
                digest_chars=32,
            )
            updated[opening.canonical_opening_id] = replace(
                opening,
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


__all__ = [
    "SOURCE_DASHED_OUTER_LINE_CASED_OPENING",
    "apply_source_dashed_outer_line_cased_openings",
    "opening_has_cased_opening_evidence",
]
