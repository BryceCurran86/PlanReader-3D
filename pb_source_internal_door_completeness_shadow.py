"""Original-source internal door symbol inventory, not a physical-opening issuer.

A unique black radial leaf and true cubic quarter-arc on WallInternal
identify a source swing SYMBOL; two genuine hosted wall ends and jambs remain
necessary for a topology barrier. A native "CS" callout records a cavity
slider text witness, not a constructed jamb/threshold/billable door.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
import re
from typing import Any

from pb_layered_wall_doorway_room_ring_shadow import _swing_arcs
from pb_source_internal_swing_room_barrier import detect_source_internal_swing_room_barriers

_INTERNAL_WALL = re.compile(r"(?:WallInternal|Wall_Internal|InternalWall)", re.I)
_WIDTH = re.compile(r"^(?:6\d\d|7\d\d|8\d\d|9\d\d|1[,]?[0-4]\d\d)$")


@dataclass(frozen=True)
class SourceInternalDoorMark:
    kind: str
    status: str
    bounds_pdf_pts: tuple[float, float, float, float]
    native_path_ids: tuple[int, ...] = ()
    source_word_index: int | None = None
    label_width_word_index: int | None = None
    label_width_mm: int | None = None
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
            "cavity_slider_geometry_authenticated_count": 0,
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
        if not isinstance(row, Mapping) or not _INTERNAL_WALL.search(str(row.get("layer") or "")):
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
        marks.append(SourceInternalDoorMark(
            "native_swing_arc_leaf",
            "HOSTED_TOPOLOGY_ONLY" if matches else "NEEDS_HOST",
            bounds,
            native_path_ids=tuple(native),
        ))

    parsed = [_word(w) for w in source_words]
    widths: list[tuple[int, int, tuple[float, float, float, float]]] = []
    for i, value in enumerate(parsed):
        if value is None:
            continue
        bounds, token = value
        if _WIDTH.fullmatch(token):
            mm = int(token.replace(",", ""))
            if 600 <= mm <= 1400:
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
        marks.append(SourceInternalDoorMark(
            "native_cavity_slider_callout", "NEEDS_JAMB_WITNESS", bounds,
            source_word_index=index,
            label_width_word_index=width_witness[1] if width_witness else None,
            label_width_mm=width_witness[2] if width_witness else None,
        ))

    marks.sort(key=lambda m: (m.bounds_pdf_pts[1], m.bounds_pdf_pts[0], m.kind, m.native_path_ids))
    swings = [m for m in marks if m.kind == "native_swing_arc_leaf"]
    sliders = [m for m in marks if m.kind == "native_cavity_slider_callout"]
    return SourceInternalDoorCompleteness(
        swing_symbol_count=len(swings),
        hosted_swing_count=sum(m.status == "HOSTED_TOPOLOGY_ONLY" for m in swings),
        unhosted_swing_symbol_count=sum(m.status == "NEEDS_HOST" for m in swings),
        cavity_slider_callout_count=len(sliders),
        cavity_slider_geometry_authenticated_count=0,
        marks=tuple(marks),
    )
