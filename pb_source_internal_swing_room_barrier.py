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

_INTERNAL_WALL_LAYER = re.compile(
    r"^(?:Enclosure[_ .-]*WallInternal|Wall[_ .-]*Internal|"
    r"Internal[_ .-]*Wall|building[._ -]+wall[._ -]+internal|"
    r"A-WALL-INTR)$", re.I,
)


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


def _authenticated_floor_plan_viewport_id(page_index: int) -> str | None:
    if type(page_index) is not int or page_index < 0:
        return None
    return f"source-authenticated-floor-plan-page-{page_index}"


def _stamp_blank_viewports_for_authenticated_page(
    drawings: Sequence[Mapping[str, Any] | object],
    authenticated_viewport_id: str,
) -> tuple[Mapping[str, Any] | object, ...]:
    """Bind page-authenticated scope onto paths that carry no viewport metadata.

    Existing non-blank viewport identities are preserved so foreign/mixed
    scopes still fail closed in the host/cap checker.
    """
    stamped: list[Mapping[str, Any] | object] = []
    expected = str(authenticated_viewport_id).strip()
    for row in drawings:
        if not isinstance(row, Mapping):
            stamped.append(row)
            continue
        current = str(
            row.get("source_viewport_id") or row.get("viewport_id") or ""
        ).strip()
        if current:
            stamped.append(row)
            continue
        copy = dict(row)
        copy["viewport_id"] = expected
        stamped.append(copy)
    return tuple(stamped)


def detect_source_internal_swing_room_barriers(
    drawings: Sequence[Mapping[str, Any] | object],
    source_words: Sequence[Any] = (),
    *,
    page_index: int = -1,
    authenticated_viewport_id: str | None = None,
) -> tuple[SourceInternalSwingRoomBarrier, ...]:
    """Source native unique-host+arc+caps; internal cap widths vary slightly.

    The external door classifier is unchanged at its original 0.5pt tolerance.
    Internal 0.75pt tolerance is used only when a full original jamb cap,
    quarter-arc and both black internal faces prove the *same* opening.
    """
    viewport_id = (
        str(authenticated_viewport_id).strip()
        if authenticated_viewport_id is not None
        else _authenticated_floor_plan_viewport_id(page_index)
    )
    scoped_drawings = (
        _stamp_blank_viewports_for_authenticated_page(drawings, viewport_id)
        if viewport_id
        else tuple(drawings)
    )
    receipts = detect_exterior_swing_door_footprint_bridges(
        scoped_drawings,
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

    arcs, _ = _swing_arcs(scoped_drawings, unlabelled_source_ink=True)
    already = {r.swing_arc_path_id for r in resolved}
    proposals = []
    for arc in arcs:
        arc_id = arc["arc"]
        if arc_id in already:
            continue
        row = scoped_drawings[arc_id]
        if not isinstance(row, Mapping) or not _INTERNAL_WALL_LAYER.search(
            str(row.get("layer") or "")
        ):
            continue
        candidate = _source_native_internal_cap_host_pair(
            scoped_drawings, arc, page_index=page_index,
            authenticated_viewport_id=viewport_id,
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
    if source_words:
        partial = _source_partial_internal_swing_candidates(
            scoped_drawings, source_words, page_index=page_index,
            authenticated_viewport_id=viewport_id,
        )
        existing_arcs = {r.swing_arc_path_id for r in resolved}
        existing_gaps = {
            (r.axis, tuple(round(x, 1) for x in r.bounds_pdf_pts))
            for r in resolved
        }
        from collections import Counter
        duplicates = Counter(
            (r.axis, tuple(round(x, 1) for x in r.bounds_pdf_pts))
            for r in partial
        )
        for r in partial:
            key = (r.axis, tuple(round(x, 1) for x in r.bounds_pdf_pts))
            # Distinct doors may share a physical wall stub. Competing
            # claims for the SAME source aperture may not.
            if (
                r.swing_arc_path_id not in existing_arcs
                and key not in existing_gaps
                and duplicates[key] == 1
            ):
                resolved.append(r)
                existing_arcs.add(r.swing_arc_path_id)
                existing_gaps.add(key)
    return tuple(sorted(resolved, key=lambda r: r.swing_arc_path_id))

def _source_native_internal_cap_host_pair(
    drawings: Sequence[Mapping[str, Any] | object], arc: Mapping[str, Any],
    *, page_index: int,
    authenticated_viewport_id: str | None = None,
) -> SourceInternalSwingRoomBarrier | None:
    """Verify the source's short end-stub/white-cap internal swing opening.

    No artificial segment, nearest-room label or wall extension is admitted:
    each original cap must touch an actual black wall-end stub on the
    outside of the exact original native swing-and-radial-leaf opening.

    All six arc/leaf/cap/host path viewport identities must be non-blank and
    equal the independently authenticated floor-plan structural viewport.
    Blank, mixed or foreign viewports fail closed.
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
    expected = str(authenticated_viewport_id or "").strip()
    if not expected:
        return None
    scopes = []
    for idx in (arc_id, leaf_id, cap_a, cap_b, host_a, host_b):
        row = drawings[idx]
        if not isinstance(row, Mapping):
            return None
        scope = str(
            row.get("source_viewport_id") or row.get("viewport_id") or ""
        ).strip()
        if scope != expected:
            return None
        scopes.append(scope)
    if len(set(scopes)) != 1:
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


def _source_partial_internal_swing_candidates(
    drawings, source_words, *, page_index,
    authenticated_viewport_id: str | None = None,
):
    """Original 25-65 degree source curve + radial leaf, not a guessed swing.

    One 3Laurel hinged door is drawn in this partial arc form. Only a unique
    real wall-layer cubic, diagonal radial leaf, source width word, two white
    jamb caps and two black end-hosts can supply a topology-only barrier.
    """
    import math

    def point(p):
        try:
            return (float(p.x), float(p.y)) if hasattr(p, "x") else (
                float(p[0]), float(p[1]),
            )
        except (AttributeError, IndexError, TypeError, ValueError):
            return None

    lines = []
    for idx, row in enumerate(drawings):
        if not isinstance(row, Mapping) or not _INTERNAL_WALL_LAYER.search(
            str(row.get("layer") or "")
        ):
            continue
        if row.get("fill") is not None or row.get("type") != "s":
            continue
        ink = row.get("color")
        if not (isinstance(ink, (tuple, list)) and len(ink) >= 3
                and all(isinstance(v, (float, int)) and math.isfinite(v)
                        and 0 <= v < .02 for v in ink[:3])):
            continue
        items = row.get("items") or ()
        if len(items) == 1 and items[0][0] == "l":
            a, b = map(point, items[0][1:3])
            if a and b and all(map(math.isfinite, (*a, *b))):
                lines.append((idx, a, b))

    proposals = []
    for arc_id, row in enumerate(drawings):
        if not isinstance(row, Mapping) or not _INTERNAL_WALL_LAYER.search(
            str(row.get("layer") or "")
        ):
            continue
        if row.get("type") != "s" or row.get("fill") is not None:
            continue
        items = row.get("items") or ()
        if len(items) != 1 or items[0][0] != "c":
            continue
        source_points = tuple(point(p) for p in items[0][1:5])
        if None in source_points:
            continue
        start, cp1, cp2, end = source_points
        if not all(map(math.isfinite, (*start, *cp1, *cp2, *end))):
            continue
        matches = []
        for leaf_id, a, b in lines:
            if leaf_id == arc_id:
                continue
            if math.dist(a, end) <= .16:
                hinge = b
            elif math.dist(b, end) <= .16:
                hinge = a
            else:
                continue
            v1 = (start[0] - hinge[0], start[1] - hinge[1])
            v2 = (end[0] - hinge[0], end[1] - hinge[1])
            r1, r2 = math.hypot(*v1), math.hypot(*v2)
            if not (15 < r1 < 50 and abs(r1 - r2) < .035 * r1):
                continue
            if not ((abs(v1[0]) < .15) != (abs(v1[1]) < .15)):
                continue
            if abs(v2[0]) <= 3 or abs(v2[1]) <= 3:
                continue
            dot = (v1[0] * v2[0] + v1[1] * v2[1]) / (r1 * r2)
            angle = math.degrees(math.acos(max(-1, min(1, dot))))
            if not 25 <= angle <= 65:
                continue
            lowx, miny = min(start[0], end[0]), min(start[1], end[1])
            highx, maxy = max(start[0], end[0]), max(start[1], end[1])
            if any(
                not lowx - .2 <= x <= highx + .2
                or not miny - .2 <= y <= maxy + .2
                for x, y in (cp1, cp2)
            ):
                continue
            mid = ((start[0] + hinge[0]) / 2, (start[1] + hinge[1]) / 2)
            widths = []
            for word in source_words:
                try:
                    txt = str(
                        word.get("text") if isinstance(word, Mapping) else word[4]
                    ).strip().replace(",", "")
                    if not txt.isdigit() or not 600 <= int(txt) <= 1400:
                        continue
                    bbox = (
                        word.get("bbox_pdf_pts")
                        if isinstance(word, Mapping) else word[:4]
                    )
                    q = tuple(float(t) for t in bbox)
                    cx, cy = (q[0] + q[2]) / 2, (q[1] + q[3]) / 2
                    if (
                        math.hypot(cx - mid[0], cy - mid[1]) <= 20
                        and .021 * int(txt) <= r1 <= .043 * int(txt)
                    ):
                        widths.append(int(txt))
                except (ValueError, TypeError, IndexError, AttributeError):
                    continue
            if len(widths) != 1:
                continue
            claimed = {
                "arc": arc_id, "leaf": leaf_id,
                "centre": hinge, "closed_tip": start,
            }
            candidate = _source_native_internal_cap_host_pair(
                drawings, claimed, page_index=page_index,
                authenticated_viewport_id=authenticated_viewport_id,
            )
            if candidate is not None:
                matches.append(candidate)
        if len(matches) == 1:
            proposals.append(matches[0])
    return tuple(proposals)
