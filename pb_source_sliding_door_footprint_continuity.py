"""Hosted residential exterior sliding-door footprint continuity (source-only).

A printed native ASD/SGD label PLUS two wall ends, two independent jamb caps
and paired source-painted track runs authenticate a boundary aperture.
It cannot authenticate a physical wall, commercial area, door-frame quantity,
opening dimension, or room-finish ownership.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pb_source_window_footprint_continuity import (
    _EXTERIOR_WALL_LAYER,
    _WINDOW_CODE,
    _line,
    _rect,
    _words,
)

_SLIDING_LABEL = re.compile(r"^(?:asd[- ]?\d*|sgd[- ]?\d*|sd[- ]?\d*|stacker)$", re.IGNORECASE)
_NON_WALL_LAYER = re.compile(r"(?:dim|anno|text|grid|title|border|note)", re.IGNORECASE)


@dataclass(frozen=True)
class ExteriorSlidingDoorFootprintBridge:
    first_host_path_id: int
    second_host_path_id: int
    jamb_cap_path_ids: tuple[int, int]
    sliding_track_path_ids: tuple[int, ...]
    label_text: str
    bounds_pdf_pts: tuple[float, float, float, float]
    axis: str
    page_index: int = -1
    physical_wall_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": "source_hosted_sliding_door_footprint_continuity_only",
            "first_host_path_id": self.first_host_path_id,
            "second_host_path_id": self.second_host_path_id,
            "jamb_cap_path_ids": list(self.jamb_cap_path_ids),
            "sliding_track_path_ids": list(self.sliding_track_path_ids),
            "label_text": self.label_text,
            "bounds_pdf_pts": list(self.bounds_pdf_pts),
            "axis": self.axis,
            "page_index": self.page_index,
            "physical_wall_authenticated": False,
            "measurement_authorized": False,
        }


def _viewport_compatible(
    rows: Sequence[Mapping[str, Any] | object], ids: tuple[int, ...]
) -> bool:
    viewports = {
        str(
            rows[i].get("viewport_id") or rows[i].get("source_viewport_id") or ""
        ).strip()
        for i in ids
        if isinstance(rows[i], Mapping)
    }
    viewports.discard("")
    return len(viewports) <= 1


def detect_exterior_sliding_door_footprint_bridges(
    drawings: Sequence[Mapping[str, Any] | object],
    source_words: Sequence[Mapping[str, Any] | Sequence[Any]],
    *,
    page_index: int = -1,
    wall_bars: Sequence[Any] | None = None,
) -> tuple[ExteriorSlidingDoorFootprintBridge, ...]:
    labels = _words(source_words, pattern=_SLIDING_LABEL)
    if not labels:
        return ()
    has_any_layers = any(
        bool(str(r.get("layer") or "").strip())
        for r in drawings
        if isinstance(r, Mapping)
    )
    has_wall_layers = any(
        _EXTERIOR_WALL_LAYER.search(str(r.get("layer") or ""))
        for r in drawings
        if isinstance(r, Mapping)
    )
    if has_any_layers and not has_wall_layers:
        return ()
    competing_windows = _words(source_words, pattern=_WINDOW_CODE)
    walls = []
    caps = []
    rails = []

    if wall_bars:
        for bar in wall_bars:
            poly = getattr(bar, "polygon", None)
            if poly is None or poly.is_empty or not poly.is_valid:
                continue
            bb = tuple(float(v) for v in poly.bounds)
            dx, dy = bb[2] - bb[0], bb[3] - bb[1]
            if min(dx, dy) <= 8 and max(dx, dy) >= 0.7:
                pid = int(getattr(bar, "path_index", -1))
                layer = str(getattr(bar, "layer", "") or "")
                walls.append((pid, layer, bb))

    for idx, row in enumerate(drawings):
        if not isinstance(row, Mapping):
            continue
        layer = str(row.get("layer") or "")
        if has_wall_layers:
            if not _EXTERIOR_WALL_LAYER.search(layer):
                continue
        elif _NON_WALL_LAYER.search(layer):
            continue
        bounds = _rect(row)
        fill = row.get("fill")
        if bounds and isinstance(fill, (tuple, list)) and len(fill) >= 3:
            tone = tuple(float(v) for v in fill[:3])
            if all(math.isfinite(t) for t in tone):
                dx, dy = bounds[2] - bounds[0], bounds[3] - bounds[1]
                if min(dx, dy) >= 0.15:
                    if max(tone) < 0.3:
                        if min(dx, dy) <= 8 and max(dx, dy) >= 0.7:
                            walls.append((idx, layer, bounds))
                    elif min(tone) > 0.9:
                        if max(dx, dy) <= 12 and min(dx, dy) > 0.2:
                            caps.append((idx, layer, bounds))
                        elif max(dx, dy) >= 5 and min(dx, dy) <= 2.0:
                            rails.append((idx, layer, bounds))
        ln = _line(row)
        if ln:
            d = math.dist(*ln)
            p0, p1 = ln
            dx, dy = abs(p0[0] - p1[0]), abs(p0[1] - p1[1])
            ln_bb = (min(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[0], p1[0]), max(p0[1], p1[1]))
            if 5.0 <= d <= 160.0 and (dx < 0.1 or dy < 0.1):
                rails.append((idx, layer, (ln_bb[0], ln_bb[1] - 0.2, ln_bb[2], ln_bb[3] + 0.2)))
            elif 0.2 <= d <= 12.0:
                caps.append((idx, layer, (ln_bb[0], ln_bb[1] - 0.2, ln_bb[2], ln_bb[3] + 0.2)))
    result = []
    for label, label_rect in labels:
        lx = (label_rect[0] + label_rect[2]) / 2
        ly = (label_rect[1] + label_rect[3]) / 2
        matches = []
        for i, layer, a in walls:
            for j, otherlayer, b in walls:
                if i == j or (has_wall_layers and otherlayer != layer):
                    continue
                for axis in ("h", "v"):
                    if axis == "h":
                        if a[2] >= b[0]:
                            continue
                        thick1, thick2 = a[3] - a[1], b[3] - b[1]
                        gap = b[0] - a[2]
                        alignment = abs((a[1] + a[3]) - (b[1] + b[3])) / 2
                        bounds = (a[2], max(a[1], b[1]), b[0], min(a[3], b[3]))
                        label_ok = (
                            bounds[0] + 0.05 * gap < lx < bounds[2] - 0.05 * gap
                            and min(
                                abs(label_rect[1] - b[3]), abs(label_rect[3] - b[1])
                            )
                            < 35
                        )
                    else:
                        if a[3] >= b[1]:
                            continue
                        thick1, thick2 = a[2] - a[0], b[2] - b[0]
                        gap = b[1] - a[3]
                        alignment = abs((a[0] + a[2]) - (b[0] + b[2])) / 2
                        bounds = (max(a[0], b[0]), a[3], min(a[2], b[2]), b[1])
                        label_ok = (
                            bounds[1] + 0.05 * gap < ly < bounds[3] - 0.05 * gap
                            and min(
                                abs(label_rect[0] - b[2]), abs(label_rect[2] - b[0])
                            )
                            < 35
                        )
                    thick = min(thick1, thick2)
                    if not (
                        8 <= gap <= 160
                        and 0.7 <= thick <= 8
                        and abs(thick1 - thick2) < 0.4
                        and alignment < 0.4
                        and label_ok
                        and bounds[0] < bounds[2]
                        and bounds[1] < bounds[3]
                    ):
                        continue
                    # A native ASW/SGW label inside this SAME aperture
                    # contradicts ASD/SGD identity; never first-match.
                    if any(
                        (
                            bounds[0] <= (w[0] + w[2]) / 2 <= bounds[2]
                            and min(abs(w[1] - b[1]), abs(w[3] - b[3])) < 30
                        )
                        if axis == "h"
                        else (
                            bounds[1] <= (w[1] + w[3]) / 2 <= bounds[3]
                            and min(abs(w[0] - b[0]), abs(w[2] - b[2])) < 30
                        )
                        for _, w in competing_windows
                    ):
                        continue
                    ends = []
                    for end in (0, 1):
                        edge = (
                            (a[2] if end == 0 else b[0])
                            if axis == "h"
                            else (a[3] if end == 0 else b[1])
                        )
                        owners = []
                        for k, caplayer, c in caps:
                            if has_wall_layers and caplayer != layer:
                                continue
                            if axis == "h":
                                bound_ok = (
                                    abs(c[0] - edge) < 0.15
                                    if end == 0
                                    else abs(c[2] - edge) < 0.15
                                )
                                cross = c[3] - c[1]
                                along = c[2] - c[0]
                                offset = abs((c[1] + c[3]) - (a[1] + a[3])) / 2
                            else:
                                bound_ok = (
                                    abs(c[1] - edge) < 0.15
                                    if end == 0
                                    else abs(c[3] - edge) < 0.15
                                )
                                cross = c[2] - c[0]
                                along = c[3] - c[1]
                                offset = abs((c[0] + c[2]) - (a[0] + a[2])) / 2
                            if (
                                bound_ok
                                and abs(cross - thick) < 0.65
                                and offset < 0.6
                                and 0.2 <= along <= 2.5
                            ):
                                owners.append(k)
                        ends.append(tuple(sorted(set(owners))))
                    if len(ends[0]) != 1 or len(ends[1]) != 1:
                        continue
                    capids = (ends[0][0], ends[1][0])
                    if capids[0] == capids[1]:
                        continue
                    tracks = []
                    for k, tracklayer, c in rails:
                        if has_wall_layers and tracklayer != layer:
                            continue
                        if axis == "h":
                            length = c[2] - c[0]
                            thin = c[3] - c[1]
                            center = (c[0] + c[2]) / 2
                            contained = c[0] >= bounds[0] and c[2] <= bounds[2]
                            lane = c[1] >= bounds[1] - 0.5 and c[3] <= bounds[3] + 0.5
                        else:
                            length = c[3] - c[1]
                            thin = c[2] - c[0]
                            center = (c[1] + c[3]) / 2
                            contained = c[1] >= bounds[1] and c[3] <= bounds[3]
                            lane = c[0] >= bounds[0] - 0.5 and c[2] <= bounds[2] + 0.5
                        if (
                            contained
                            and lane
                            and 0.15 <= thin <= 0.8 * thick
                            and length >= 0.2 * gap
                        ):
                            tracks.append((k, center))
                    if len(tracks) < 2:
                        continue
                    midpoint = (
                        (bounds[0] + bounds[2]) / 2
                        if axis == "h"
                        else (bounds[1] + bounds[3]) / 2
                    )
                    if not (
                        any(center < midpoint for _, center in tracks)
                        and any(center > midpoint for _, center in tracks)
                    ):
                        continue
                    trackids = tuple(sorted({k for k, _ in tracks}))
                    ids = (i, j, *capids, *trackids)
                    if not _viewport_compatible(drawings, ids):
                        continue
                    # Exclude a third same-lane full-thickness wall between
                    # the two native door hosts.
                    occluded = False
                    for k, otherlayer, c in walls:
                        if k in (i, j) or otherlayer != layer:
                            continue
                        if axis == "h":
                            overlap = min(bounds[2], c[2]) - max(bounds[0], c[0])
                            aligned = abs((c[1] + c[3]) - (a[1] + a[3])) / 2 < 0.4
                            full = c[3] - c[1] >= 0.8 * thick
                        else:
                            overlap = min(bounds[3], c[3]) - max(bounds[1], c[1])
                            aligned = abs((c[0] + c[2]) - (a[0] + a[2])) / 2 < 0.4
                            full = c[2] - c[0] >= 0.8 * thick
                        if overlap > 0.4 and aligned and full:
                            occluded = True
                            break
                    if occluded:
                        continue
                    matches.append(
                        ExteriorSlidingDoorFootprintBridge(
                            first_host_path_id=i,
                            second_host_path_id=j,
                            jamb_cap_path_ids=capids,
                            sliding_track_path_ids=trackids,
                            label_text=label,
                            bounds_pdf_pts=bounds,
                            axis=axis,
                            page_index=page_index,
                        )
                    )
        unique = {
            (m.first_host_path_id, m.second_host_path_id, m.bounds_pdf_pts): m
            for m in matches
        }
        # If multiple wall hosts explain the same printed sliding door,
        # ownership is not unique. Never pick a plan-specific nearest pair.
        if len(unique) == 1:
            result.extend(unique.values())
    owner_pairs = {}
    for b in result:
        key = (b.first_host_path_id, b.second_host_path_id)
        owner_pairs[key] = owner_pairs.get(key, 0) + 1
    return tuple(
        sorted(
            (
                b
                for b in result
                if owner_pairs[(b.first_host_path_id, b.second_host_path_id)] == 1
            ),
            key=lambda b: (b.first_host_path_id, b.second_host_path_id),
        )
    )
