"""Bind a unique figured width written inside a painted door swing (shadow).

Owner source rule: the door width is the figure drawn in that door's swing.
This module never invents a width, never uses nearest/first/smallest, and
never overwrites an already-bound figured axis. Default-off; not FIRM.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Any, Mapping, Sequence

from pb_live_physical_opening_void_composition import (
    LiveCanonicalOpeningObject,
    LivePhysicalOpeningVoidComposition,
)
from pb_opening_kind_authority import SOURCE_QUARTER_SWING_AND_RADIAL_LEAF
from pb_source_quarter_swing_opening_kind_shadow import (
    _SWING_OPENING_BIND_PT,
    _unique_hosted_door_bindings,
    _witnesses,
)


@dataclass(frozen=True)
class SwingFiguredWidthCallout:
    """One native figured callout that may sit inside a painted swing."""

    callout_id: str
    value_mm: float
    text_bbox: tuple[float, float, float, float]


def _clean(value: object) -> str:
    return str(value).strip() if type(value) is str else ""


def _positive_mm(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value > 0.0


def _text_centre(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    return ((float(bbox[0]) + float(bbox[2])) / 2.0, (float(bbox[1]) + float(bbox[3])) / 2.0)


def point_in_painted_swing_sector(
    *,
    centre: tuple[float, float],
    open_tip: tuple[float, float],
    closed_tip: tuple[float, float],
    radius: float,
    point: tuple[float, float],
) -> bool:
    """True when a point sits in the quarter-swing disk, including 2.5 pt snap."""
    cx, cy = (float(centre[0]), float(centre[1]))
    px, py = (float(point[0]), float(point[1]))
    span = float(radius) + _SWING_OPENING_BIND_PT
    if span <= 0.0 or math.hypot(px - cx, py - cy) > span:
        return False
    xs = (cx, float(open_tip[0]), float(closed_tip[0]))
    ys = (cy, float(open_tip[1]), float(closed_tip[1]))
    return (
        min(xs) - _SWING_OPENING_BIND_PT <= px <= max(xs) + _SWING_OPENING_BIND_PT
        and min(ys) - _SWING_OPENING_BIND_PT <= py <= max(ys) + _SWING_OPENING_BIND_PT
    )


def callouts_from_trusted_native_dimensions(
    dimensions: Sequence[Any],
) -> tuple[SwingFiguredWidthCallout, ...]:
    """Keep dims that carry a source text box and a positive mm value.

    "Trusted" is the caller's claim: this shadow does not authenticate a dimension, so a wiring caller must hand it
    producer-owned, text-integrity-corroborated dimensions only. One id seen twice with the same value and box is one
    callout; the same id with a different value or box is ambiguous and is dropped, never resolved by order.
    """
    rows: dict[str, SwingFiguredWidthCallout] = {}
    conflicting: set[str] = set()
    order: list[str] = []
    for item in dimensions:
        if type(item) is SwingFiguredWidthCallout:
            callout_id, bbox, value = item.callout_id, item.text_bbox, item.value_mm
            if type(callout_id) is not str or not callout_id:
                continue
        else:
            callout_id = _clean(getattr(item, "dimension_id", None))
            bbox = getattr(item, "text_bbox", None)
            value = getattr(item, "value_mm", None)
        if (
            not callout_id
            or not isinstance(bbox, (tuple, list))
            or len(bbox) < 4
            or not _positive_mm(value)
        ):
            continue
        try:
            box = (
                float(bbox[0]),
                float(bbox[1]),
                float(bbox[2]),
                float(bbox[3]),
            )
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(part) for part in box):
            continue
        callout = SwingFiguredWidthCallout(
            callout_id=callout_id, value_mm=float(value), text_bbox=box,
        )
        if callout_id in rows:
            if rows[callout_id] != callout:
                conflicting.add(callout_id)
            continue
        rows[callout_id] = callout
        order.append(callout_id)
    return tuple(rows[callout_id] for callout_id in order if callout_id not in conflicting)


def _callouts_in_witness(
    witness: Mapping[str, Any],
    callouts: Sequence[SwingFiguredWidthCallout],
) -> tuple[SwingFiguredWidthCallout, ...]:
    if str(witness.get("pattern") or "") != SOURCE_QUARTER_SWING_AND_RADIAL_LEAF:
        return ()
    try:
        centre = tuple(float(value) for value in witness["centre"])
        open_tip = tuple(float(value) for value in witness["open_tip"])
        closed_tip = tuple(float(value) for value in witness["closed_tip"])
        radius = float(witness["radius"])
    except (KeyError, TypeError, ValueError):
        return ()
    hits: list[SwingFiguredWidthCallout] = []
    for callout in callouts:
        if point_in_painted_swing_sector(
            centre=centre,
            open_tip=open_tip,
            closed_tip=closed_tip,
            radius=radius,
            point=_text_centre(callout.text_bbox),
        ):
            hits.append(callout)
    return tuple(hits)


def apply_source_swing_figured_widths(
    composition: LivePhysicalOpeningVoidComposition,
    *,
    drawings_by_page_id: Mapping[str, Sequence[Mapping[str, Any]]],
    dimensions_by_page_id: Mapping[str, Sequence[Any]],
) -> LivePhysicalOpeningVoidComposition:
    """Stamp a unique in-swing figured width onto the hosted door that owns it."""
    if type(composition) is not LivePhysicalOpeningVoidComposition:
        raise TypeError("composition must be LivePhysicalOpeningVoidComposition")

    by_page: dict[str, list[LiveCanonicalOpeningObject]] = {}
    for opening in composition.canonical_openings:
        by_page.setdefault(str(opening.page_id), []).append(opening)

    updated: dict[str, LiveCanonicalOpeningObject] = {}
    for page_id, openings in by_page.items():
        drawings = drawings_by_page_id.get(page_id)
        if not drawings:
            continue
        callouts = callouts_from_trusted_native_dimensions(
            dimensions_by_page_id.get(page_id, ())
        )
        if not callouts:
            continue
        witnesses = _witnesses(drawings)
        bindings = _unique_hosted_door_bindings(openings, witnesses)
        by_opening_id = {item.canonical_opening_id: item for item in openings}
        sole_callout: dict[str, SwingFiguredWidthCallout] = {}
        owners: dict[str, list[str]] = {}
        for opening_id, witness in bindings.items():
            if by_opening_id[opening_id].figured_single_axis_mm is not None:
                continue
            hits = _callouts_in_witness(witness, callouts)
            if len(hits) != 1:
                continue
            sole_callout[opening_id] = hits[0]
            owners.setdefault(hits[0].callout_id, []).append(opening_id)
        for opening_id, callout in sole_callout.items():
            # A figure that sits in two doors' swings is ambiguous: it belongs to neither, whatever the order.
            if len(owners[callout.callout_id]) != 1:
                continue
            opening = by_opening_id[opening_id]
            evidence_ids = tuple(
                dict.fromkeys((*opening.evidence_ids, callout.callout_id))
            )
            updated[opening_id] = replace(
                opening,
                figured_single_axis_mm=float(callout.value_mm),
                figured_area_record_id=callout.callout_id,
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
    "SwingFiguredWidthCallout",
    "apply_source_swing_figured_widths",
    "callouts_from_trusted_native_dimensions",
    "point_in_painted_swing_sector",
]
