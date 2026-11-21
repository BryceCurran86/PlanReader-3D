"""Original-source internal door symbol inventory, not a physical-opening issuer.

A unique black radial leaf and true cubic quarter-arc on WallInternal
identify a source swing SYMBOL; two genuine hosted wall ends and jambs remain
necessary for a topology barrier. A native "CS" callout records a cavity
slider text witness, not a constructed jamb/threshold/billable door.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pb_layered_wall_doorway_room_ring_shadow import _swing_arcs
from pb_source_internal_swing_room_barrier import (
    _INTERNAL_WALL_LAYER,
    detect_source_internal_swing_room_barriers,
)
from pb_source_native_cavity_slider_jamb_shadow import (
    match_source_native_cavity_sliders,
)

# One internal-wall layer predicate for the whole door evidence path: the barrier's (five CAD conventions,
# anchored). The inventory used to keep a looser three-name copy that could list a swing the hosting
# detector could never host, and miss every convention it did not spell.
_WIDTH = re.compile(r"^(?:6\d\d|7\d\d|8\d\d|9\d\d|1[,]?[0-4]\d\d)$")
# The pattern bounds the lower end at 600; this trims the 1401-1499 the pattern would still pass.
_MAX_DOOR_WIDTH_MM = 1400
# A hinge owns a printed width only when exactly one plausible door-width token lies this close.
_HINGE_WIDTH_RADIUS_PT = 15.0


@dataclass(frozen=True)
class SourceInternalDoorMark:
    kind: str
    status: str
    bounds_pdf_pts: tuple[float, float, float, float]
    native_path_ids: tuple[int, ...] = ()
    source_word_index: int | None = None
    label_width_word_index: int | None = None
    label_width_mm: int | None = None
    host_wall_native_path_ids: tuple[int, ...] = ()
    jamb_native_path_ids: tuple[int, ...] = ()
    leaf_native_path_id: int | None = None
    clear_interval_pdf_pts: tuple[float, float] | None = None
    physical_opening_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "status": self.status,
            "bounds_pdf_pts": list(self.bounds_pdf_pts),
            "native_path_ids": list(self.native_path_ids),
            "source_word_index": self.source_word_index,
            "label_width_word_index": self.label_width_word_index,
            "label_width_mm": self.label_width_mm,
            "host_wall_native_path_ids": list(self.host_wall_native_path_ids),
            "jamb_native_path_ids": list(self.jamb_native_path_ids),
            "leaf_native_path_id": self.leaf_native_path_id,
            "clear_interval_pdf_pts": (
                list(self.clear_interval_pdf_pts)
                if self.clear_interval_pdf_pts is not None else None
            ),
            "physical_opening_authenticated": False,
            "measurement_authorized": False,
        }


@dataclass(frozen=True)
class SourceInternalDoorCompleteness:
    swing_symbol_count: int
    hosted_swing_count: int
    unhosted_swing_symbol_count: int
    cavity_slider_callout_count: int
    cavity_slider_geometry_authenticated_count: int
    marks: tuple[SourceInternalDoorMark, ...]
    physical_openings_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "swing_symbol_count": self.swing_symbol_count,
            "hosted_swing_count": self.hosted_swing_count,
            "unhosted_swing_symbol_count": self.unhosted_swing_symbol_count,
            "cavity_slider_callout_count": self.cavity_slider_callout_count,
            "cavity_slider_geometry_authenticated_count": self.cavity_slider_geometry_authenticated_count,
            "marks": [m.to_dict() for m in self.marks],
            "physical_openings_authenticated": False,
            "measurement_authorized": False,
            "physical_door_count_is_not_established": True,
        }


def _word(row: Sequence[Any] | Mapping[str, Any]) -> tuple[tuple[float, float, float, float], str] | None:
    try:
        if isinstance(row, Mapping):
            label = str(row.get("text") or "").strip()
            box = row.get("bbox_pdf_pts") or row.get("bbox")
        else:
            label = str(row[4]).strip()
            box = row[:4]
        coords = tuple(float(x) for x in box)
        if len(coords) != 4 or not all(math.isfinite(v) for v in coords):
            return None
        if coords[0] > coords[2] or coords[1] > coords[3]:
            return None
        return coords, label.upper()
    except (IndexError, TypeError, ValueError, OverflowError):
        return None


def _owned_hinge_width(
    box: tuple[float, float, float, float],
    source_words: Sequence[Sequence[Any] | Mapping[str, Any]],
) -> tuple[int | None, int | None]:
    """A hinge gets a printed width only when exactly ONE plausible door-width token lies near it.

    Every plausible token (600-1400 mm, the range the cavity-slider detector uses) inside the radius is a
    candidate. Two or more are ambiguous: none is chosen, and no nearest tie-break is applied. No width value is
    privileged. The result is a witness, never a measurement.
    """
    cx, cy = (box[0] + box[2]) / 2., (box[1] + box[3]) / 2.
    options = []
    for index, row in enumerate(source_words):
        parsed = _word(row)
        if parsed is None:
            continue
        bounds, token = parsed
        if _WIDTH.fullmatch(token) is None:
            continue
        width_mm = int(token.replace(",", ""))
        if width_mm > _MAX_DOOR_WIDTH_MM:
            continue
        x, y = (bounds[0] + bounds[2]) / 2., (bounds[1] + bounds[3]) / 2.
        if math.hypot(x - cx, y - cy) < _HINGE_WIDTH_RADIUS_PT:
            options.append((index, width_mm))
    if len(options) != 1:
        return None, None
    return options[0]


def inspect_source_internal_door_completeness(
    drawings: Sequence[Mapping[str, Any] | object],
    source_words: Sequence[Sequence[Any] | Mapping[str, Any]] = (),
    *,
    page_index: int = -1,
) -> SourceInternalDoorCompleteness:
    """Report source-only symbols missed by the strict existing host matcher.

    A width annotation/CS text cannot authorize a physical opening, room
    closure, area or a customer door. Only exact original arc+radial leaf
    count as a native swing symbol; printed CS words remain unhosted.
    """
    arcs, _rejected = _swing_arcs(drawings, unlabelled_source_ink=True)
    hosted = detect_source_internal_swing_room_barriers(
        drawings, source_words, page_index=page_index,
    )
    marks: list[SourceInternalDoorMark] = []
    for arc in arcs:
        arc_id, leaf_id = arc["arc"], arc["leaf"]
        row = drawings[arc_id]
        if not isinstance(row, Mapping) or not _INTERNAL_WALL_LAYER.search(str(row.get("layer") or "")):
            continue
        rect = row.get("rect")
        if rect is None:
            continue
        try:
            bounds = tuple(float(v) for v in rect)
            if len(bounds) != 4 or not all(math.isfinite(x) for x in bounds):
                continue
        except (TypeError, ValueError, OverflowError):
            continue
        matches = [r for r in hosted if r.swing_arc_path_id == arc_id]
        matches = matches if len(matches) == 1 else []
        native = ((arc_id, leaf_id, matches[0].first_host_path_id,
                   matches[0].second_host_path_id, *matches[0].jamb_cap_path_ids)
                  if matches else (arc_id, leaf_id))
        width_index, width_mm = _owned_hinge_width(bounds, source_words)
        marks.append(SourceInternalDoorMark(
            "native_swing_arc_leaf",
            "HOSTED_TOPOLOGY_ONLY" if matches else "NEEDS_HOST",
            bounds,
            native_path_ids=tuple(native),
            label_width_word_index=width_index,
            label_width_mm=width_mm,
            host_wall_native_path_ids=(
                (matches[0].first_host_path_id, matches[0].second_host_path_id)
                if matches else ()
            ),
            jamb_native_path_ids=matches[0].jamb_cap_path_ids if matches else (),
        ))

    # A partial 25-65 degree original swing plus diagonal leaf may not
    # appear in the quarter-circle parser. It nevertheless has independent
    # source-positive wall-end and jamb ownership in the strict detector.
    standard_arcs = {
        m.native_path_ids[0] for m in marks
        if m.kind == "native_swing_arc_leaf" and m.native_path_ids
    }
    for r in hosted:
        if r.swing_arc_path_id in standard_arcs:
            continue
        row = drawings[r.swing_arc_path_id]
        rect = row.get("rect") if isinstance(row, Mapping) else None
        if rect is None:
            continue
        bounds = tuple(float(v) for v in rect)
        width_index, width_mm = _owned_hinge_width(bounds, source_words)
        marks.append(SourceInternalDoorMark(
            "native_swing_arc_leaf", "HOSTED_TOPOLOGY_ONLY",
            bounds,
            native_path_ids=(r.swing_arc_path_id, r.first_host_path_id,
                             r.second_host_path_id, *r.jamb_cap_path_ids),
            label_width_word_index=width_index,
            label_width_mm=width_mm,
            host_wall_native_path_ids=(r.first_host_path_id, r.second_host_path_id),
            jamb_native_path_ids=r.jamb_cap_path_ids,
        ))
    sliders_from_native = {
        rec.cs_word_index: rec for rec in match_source_native_cavity_sliders(
            drawings, source_words, page_index=page_index,
        )
    } if page_index >= 0 else {}
    parsed = [_word(w) for w in source_words]
    widths: list[tuple[int, int, tuple[float, float, float, float]]] = []
    for i, value in enumerate(parsed):
        if value is None:
            continue
        bounds, token = value
        if _WIDTH.fullmatch(token):
            mm = int(token.replace(",", ""))
            if mm <= _MAX_DOOR_WIDTH_MM:
                widths.append((i, mm, bounds))
    for index, value in enumerate(parsed):
        if value is None or value[1] != "CS":
            continue
        bounds, _ = value
        cx, cy = (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2
        near = []
        for w_index, width_mm, wbox in widths:
            wx, wy = (wbox[0] + wbox[2]) / 2, (wbox[1] + wbox[3]) / 2
            dist = math.hypot(cx - wx, cy - wy)
            if dist <= 17.0:
                near.append((dist, w_index, width_mm))
        near.sort()
        width_witness = (
            near[0] if near and (len(near) == 1 or near[1][0] - near[0][0] > 1.0)
            else None
        )
        native = sliders_from_native.get(index)
        marks.append(SourceInternalDoorMark(
            "native_cavity_slider_callout",
            "HOSTED_TOPOLOGY_ONLY" if native else "NEEDS_JAMB_WITNESS",
            bounds,
            native_path_ids=tuple(sorted({
                *native.host_path_ids, *native.jamb_path_ids, native.leaf_path_id,
            })) if native else (),
            source_word_index=index,
            label_width_word_index=width_witness[1] if width_witness else None,
            label_width_mm=width_witness[2] if width_witness else None,
            host_wall_native_path_ids=native.host_path_ids if native else (),
            jamb_native_path_ids=native.jamb_path_ids if native else (),
            leaf_native_path_id=native.leaf_path_id if native else None,
            clear_interval_pdf_pts=native.clear_interval_pdf_pts if native else None,
        ))

    marks.sort(key=lambda m: (m.bounds_pdf_pts[1], m.bounds_pdf_pts[0], m.kind, m.native_path_ids))
    swings = [m for m in marks if m.kind == "native_swing_arc_leaf"]
    sliders = [m for m in marks if m.kind == "native_cavity_slider_callout"]
    return SourceInternalDoorCompleteness(
        swing_symbol_count=len(swings),
        hosted_swing_count=sum(m.status == "HOSTED_TOPOLOGY_ONLY" for m in swings),
        unhosted_swing_symbol_count=sum(m.status == "NEEDS_HOST" for m in swings),
        cavity_slider_callout_count=len(sliders),
        cavity_slider_geometry_authenticated_count=sum(
            m.status == "HOSTED_TOPOLOGY_ONLY" for m in sliders
        ),
        marks=tuple(marks),
    )
