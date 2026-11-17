"""Original-source internal swing threshold closure for candidate room topology.

Only an original PDF swing arc, TWO distinct native black internal-wall ends
and TWO uniquely hosted original jamb caps may supply a temporary barrier.
The geometry closes a room for *review*, never for physical wall material or
billable customer floor, wall, ceiling or opening quantities.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping, Sequence
import re
from typing import Any

from pb_source_swing_door_footprint_continuity import (
    detect_exterior_swing_door_footprint_bridges,
)

_INTERNAL_WALL_LAYER = re.compile(r"WallInternal|Wall_Internal|InternalWall", re.I)


@dataclass(frozen=True)
class SourceInternalSwingRoomBarrier:
    first_host_path_id: int
    second_host_path_id: int
    swing_arc_path_id: int
    jamb_cap_path_ids: tuple[int, int]
    bounds_pdf_pts: tuple[float, float, float, float]
    axis: str
    page_index: int
    physical_wall_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": "source_owned_internal_swing_room_closure_only",
            "first_host_path_id": self.first_host_path_id,
            "second_host_path_id": self.second_host_path_id,
            "swing_arc_path_id": self.swing_arc_path_id,
            "jamb_cap_path_ids": list(self.jamb_cap_path_ids),
            "bounds_pdf_pts": list(self.bounds_pdf_pts),
            "axis": self.axis,
            "page_index": self.page_index,
            "physical_wall_authenticated": False,
            "measurement_authorized": False,
        }


def detect_source_internal_swing_room_barriers(
    drawings: Sequence[Mapping[str, Any] | object],
    source_words: Sequence[Any] = (),
    *,
    page_index: int = -1,
) -> tuple[SourceInternalSwingRoomBarrier, ...]:
    """Source native unique-host+arc+caps; internal cap widths vary slightly.

    The external door classifier is unchanged at its original 0.5pt tolerance.
    Internal 0.75pt tolerance is used only when a full original jamb cap,
    quarter-arc and both black internal faces prove the *same* opening.
    """
    receipts = detect_exterior_swing_door_footprint_bridges(
        drawings,
        source_words,
        page_index=page_index,
        wall_layer_pattern=_INTERNAL_WALL_LAYER,
        cap_across_tolerance_pt=0.75,
    )
    resolved = [
        SourceInternalSwingRoomBarrier(
            first_host_path_id=r.first_host_path_id,
            second_host_path_id=r.second_host_path_id,
            swing_arc_path_id=r.swing_arc_path_id,
            jamb_cap_path_ids=r.jamb_cap_path_ids,
            bounds_pdf_pts=r.bounds_pdf_pts,
            axis=r.axis,
            page_index=page_index,
        )
        for r in receipts
    ]
    # The external matcher misses true INTERNAL short native wall-end stubs.
    # Recover only with a unique original arc+radial leaf, two WHITE jamb
    # returns and two directly terminated BLACK internal wall hosts.
    from pb_layered_wall_doorway_room_ring_shadow import _swing_arcs
    from collections import Counter

    arcs, _ = _swing_arcs(drawings, unlabelled_source_ink=True)
    already = {r.swing_arc_path_id for r in resolved}
    proposals = []
    for arc in arcs:
        arc_id = arc["arc"]
        if arc_id in already:
            continue
        row = drawings[arc_id]
        if not isinstance(row, Mapping) or not _INTERNAL_WALL_LAYER.search(
            str(row.get("layer") or "")
        ):
            continue
        candidate = _source_native_internal_cap_host_pair(
            drawings, arc, page_index=page_index,
        )
        if candidate is not None:
            proposals.append(candidate)
    # Do not arbitrarily select a shared jamb or host when two arcs compete.
    used = Counter(
        pid for candidate in proposals
        for pid in (*candidate.jamb_cap_path_ids, candidate.first_host_path_id,
                    candidate.second_host_path_id)
    )
    resolved.extend(
        candidate for candidate in proposals
        if all(used[pid] == 1 for pid in (
            *candidate.jamb_cap_path_ids, candidate.first_host_path_id,
            candidate.second_host_path_id,
        ))
    )
    return tuple(sorted(resolved, key=lambda r: r.swing_arc_path_id))


def _source_native_internal_cap_host_pair(
    drawings: Sequence[Mapping[str, Any] | object], arc: Mapping[str, Any],
    *, page_index: int,
) -> SourceInternalSwingRoomBarrier | None:
    """Verify the source's short end-stub/white-cap internal swing opening.

    No artificial segment, nearest-room label or wall extension is admitted:
    each original cap must touch an actual black wall-end stub on the
    outside of the exact original native swing-and-radial-leaf opening.
    """
    import math

    arc_id, leaf_id = int(arc["arc"]), int(arc["leaf"])
    centre, tip = arc["centre"], arc["closed_tip"]
    dx, dy = abs(centre[0] - tip[0]), abs(centre[1] - tip[1])
    if dx <= .06 and 15.0 <= dy <= 45.0:
        axis, coordinate, lo, hi = "v", float(centre[0]), min(centre[1], tip[1]), max(centre[1], tip[1])
    elif dy <= .06 and 15.0 <= dx <= 45.0:
        axis, coordinate, lo, hi = "h", float(centre[1]), min(centre[0], tip[0]), max(centre[0], tip[0])
    else:
        return None

    def _bounds(r):
        try:
            b = tuple(float(v) for v in r.get("rect", ()))
            return b if len(b) == 4 and all(math.isfinite(v) for v in b) else None
        except (ValueError, TypeError, OverflowError):
            return None

    def _ink(r, white):
        fill = r.get("fill")
        return (isinstance(fill, (tuple, list)) and len(fill) >= 3
                and all(isinstance(v, (float, int)) and math.isfinite(v) for v in fill[:3])
                and (min(fill[:3]) > .98 if white else max(fill[:3]) < .02))

    candidates = []
    for i, row in enumerate(drawings):
        if (not isinstance(row, Mapping)
                or not _INTERNAL_WALL_LAYER.search(str(row.get("layer") or ""))
                or row.get("type") != "f"):
            continue
        b = _bounds(row)
        if b is None or not (_ink(row, True) or _ink(row, False)):
            continue
        along = (b[1], b[3]) if axis == "v" else (b[0], b[2])
        across = (b[0], b[2]) if axis == "v" else (b[1], b[3])
        if not .7 < across[1] - across[0] <= 5:
            continue
        if across[0] > coordinate + .65 or across[1] < coordinate - .65:
            continue
        candidates.append((i, b, along, across, _ink(row, True)))

    results = []
    for endpoint, location in ((0, lo), (1, hi)):
        options = []
        for cap_id, cap_bounds, cap_along, cap_across, is_white in candidates:
            if not is_white or not .5 <= cap_along[1] - cap_along[0] <= 3.5:
                continue
            if abs((cap_along[1] if endpoint == 0 else cap_along[0]) - location) > .3:
                continue
            hosts = []
            for host_id, host_bounds, host_along, host_across, host_white in candidates:
                if host_white or host_id == cap_id or not .7 <= host_along[1] - host_along[0]:
                    continue
                overlap = min(host_across[1], cap_across[1]) - max(host_across[0], cap_across[0])
                if overlap < .7 or overlap / min(
                    host_across[1] - host_across[0], cap_across[1] - cap_across[0]
                ) < .55:
                    continue
                black_end = host_along[1] if endpoint == 0 else host_along[0]
                cap_outside = cap_along[0] if endpoint == 0 else cap_along[1]
                if abs(black_end - cap_outside) > .3:
                    continue
                if endpoint == 0 and host_along[1] > lo + .3:
                    continue
                if endpoint == 1 and host_along[0] < hi - .3:
                    continue
                hosts.append((host_id, host_bounds, host_across))
            if len(hosts) == 1:
                options.append((cap_id, cap_bounds, cap_across, *hosts[0]))
        if len(options) != 1:
            return None
        results.append(options[0])

    first, second = results
    cap_a, cap_b = first[0], second[0]
    host_a, host_b = first[3], second[3]
    if len({cap_a, cap_b, host_a, host_b, arc_id, leaf_id}) != 6:
        return None
    overlap_lo = max(first[5][0], second[5][0])
    overlap_hi = min(first[5][1], second[5][1])
    if not .65 <= overlap_hi - overlap_lo <= 5:
        return None
    if axis == "v":
        bounds = (overlap_lo, first[1][1], overlap_hi, second[1][3])
    else:
        bounds = (first[1][0], overlap_lo, second[1][2], overlap_hi)
    if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
        return None
    scopes = {
        str(drawings[idx].get("source_viewport_id") or drawings[idx].get("viewport_id") or "").strip()
        for idx in (arc_id, leaf_id, cap_a, cap_b, host_a, host_b)
    }
    if len(scopes) > 1:
        return None
    return SourceInternalSwingRoomBarrier(
        first_host_path_id=host_a,
        second_host_path_id=host_b,
        swing_arc_path_id=arc_id,
        jamb_cap_path_ids=(cap_a, cap_b),
        bounds_pdf_pts=bounds,
        axis=axis,
        page_index=page_index,
    )
