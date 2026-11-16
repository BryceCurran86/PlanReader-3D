"""Trace the source-owned UNBOUNDED outside face, not a closed dwelling loop.

This is a review-only *wall-network* walk. A building with two dwellings can
have two internal free-space faces sharing a PARTY wall, but only ONE outside
face. Never use a clockwise/left-turn closed UNIT ring as the building's
outside perimeter. No inferred wall, snapping, quantities or FIRM authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
from typing import Any

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from pb_source_shared_dwelling_envelope_shadow import (
    CandidateSharedBuildingDivider,
)


@dataclass(frozen=True)
class OutsideFacingBuildingWalk:
    status: str
    reason: str
    clockwise_pdf_pts: tuple[tuple[float, float], ...] = ()
    outer_wall_native_path_ids: tuple[int, ...] = ()
    internal_party_wall_native_path_ids: tuple[int, ...] = ()
    enclosed_region_count: int = 0
    enclosed_dwelling_zone_count: int = 0
    unclosed_dwelling_sides: tuple[str, ...] = ()
    other_source_wall_band_count: int = 0
    building_footprint_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "clockwise_pdf_pts": [list(p) for p in self.clockwise_pdf_pts],
            "outer_wall_native_path_ids": list(self.outer_wall_native_path_ids),
            "internal_party_wall_native_path_ids": list(
                self.internal_party_wall_native_path_ids
            ),
            "enclosed_region_count": self.enclosed_region_count,
            "enclosed_dwelling_zone_count": self.enclosed_dwelling_zone_count,
            "unclosed_dwelling_sides": list(self.unclosed_dwelling_sides),
            "other_source_wall_band_count": self.other_source_wall_band_count,
            "building_footprint_authenticated": False,
            "measurement_authorized": False,
        }


def _word_centers(source_words: Sequence[Mapping[str, Any] | Sequence[Any]]):
    result = []
    for row in source_words:
        try:
            if isinstance(row, Mapping):
                word = str(row.get("text") or "").strip().upper()
                bounds = row.get("bbox_pdf_pts") or row.get("bbox")
            else:
                word, bounds = str(row[4]).strip().upper(), row[:4]
            x0, y0, x1, y1 = (float(v) for v in bounds)
            if (
                not all(math.isfinite(v) for v in (x0, y0, x1, y1))
                or x0 >= x1
                or y0 >= y1
            ):
                continue
        except (IndexError, ValueError, TypeError, OverflowError):
            continue
        result.append((word, Point((x0 + x1) / 2, (y0 + y1) / 2)))
    return result


def _owner(bar):
    geom = getattr(bar, "polygon", None)
    get_ids = getattr(bar, "native_path_indices", None)
    if (
        not isinstance(geom, Polygon)
        or not geom.is_valid
        or geom.is_empty
        or not callable(get_ids)
    ):
        return None
    try:
        ids = tuple(int(v) for v in get_ids())
    except (TypeError, ValueError, OverflowError):
        return None
    return (geom, ids) if ids and min(ids) >= 0 else None


def _clockwise_page_ring(source_exterior):
    coords = [(float(x), float(y)) for x, y in list(source_exterior.coords)[:-1]]
    if len(coords) < 4 or not all(math.isfinite(v) for pt in coords for v in pt):
        return ()
    signed = sum(
        a[0] * b[1] - b[0] * a[1] for a, b in zip(coords, coords[1:] + coords[:1])
    )
    # PDF y-axis goes DOWN. Signed-positive means clockwise on the page.
    if signed < 0:
        coords.reverse()
    first = min(
        range(len(coords)),
        key=lambda i: (round(coords[i][1], 8), round(coords[i][0], 8)),
    )
    coords = coords[first:] + coords[:first]
    return tuple(coords + [coords[0]])


def _occupied_party_regions(
    holes: Sequence[Polygon],
    words: Sequence[tuple[str, Point]],
    divider: CandidateSharedBuildingDivider,
):
    x0, y0, x1, y1 = divider.wall_bounds_pdf_pts
    vertical = divider.orientation == "vertical"
    mid = (x0 + x1) / 2 if vertical else (y0 + y1) / 2
    low, high = (y0, y1) if vertical else (x0, x1)
    sides = {"left": set(), "right": set()}
    # Source words used to discover this divider, not a caller-supplied
    # guess that the house is a particular rectangle or a fixed twin-unit.
    for label in (divider.side_one_label, divider.side_two_label):
        for text, point in words:
            if text != label.upper():
                continue
            normal = point.x if vertical else point.y
            along = point.y if vertical else point.x
            if abs(normal - mid) > 180 or not low - 4 <= along <= high + 4:
                continue
            for idx, hole in enumerate(holes):
                if hole.contains(point):
                    sides["left" if normal < mid else "right"].add(idx)
    return sides


def walk_source_unbounded_building_face(
    wall_bars: Sequence[Any],
    source_words: Sequence[Mapping[str, Any] | Sequence[Any]],
    *,
    shared_dividers: Sequence[CandidateSharedBuildingDivider] = (),
    source_wall_union: Any | None = None,
) -> OutsideFacingBuildingWalk:
    """Walk OUTSIDE-facing source wall network; fail closed on unjoined zones.

    Reuse the original already-computed wall/hosted-opening union from the
    source preflight when supplied; do not make duplicate OCR/geometry passes.
    A missing party wall or a source-named room still open to the outside
    is not repaired by a sketch, a bounding hull or a direct endpoint snap.
    """
    owners = tuple(v for b in wall_bars if (v := _owner(b)) is not None)
    if len(owners) < 4:
        return OutsideFacingBuildingWalk("ABSTAINED", "source_walls_insufficient")
    if source_wall_union is None:
        source_wall_union = unary_union([geom for geom, _ in owners])
    components = (
        list(source_wall_union.geoms)
        if hasattr(source_wall_union, "geoms")
        else [source_wall_union]
    )
    closed = [
        p for p in components if isinstance(p, Polygon) and p.is_valid and p.interiors
    ]
    party_ids = tuple(
        sorted({i for d in shared_dividers for i in d.wall_native_path_ids})
    )
    if len(closed) != 1:
        return OutsideFacingBuildingWalk(
            "ABSTAINED",
            "outside_face_source_wall_domain_not_unique_and_closed",
            internal_party_wall_native_path_ids=party_ids,
        )
    primary = closed[0]
    holes = tuple(Polygon(r) for r in primary.interiors)
    dwelling_count = 0
    if shared_dividers:
        if len(shared_dividers) != 1:
            return OutsideFacingBuildingWalk(
                "ABSTAINED",
                "several_party_dividers_require_dwelling_zone_graph",
                enclosed_region_count=len(holes),
                internal_party_wall_native_path_ids=party_ids,
            )
        divider = shared_dividers[0]
        sides = _occupied_party_regions(holes, _word_centers(source_words), divider)
        dwelling_count = len(sides["left"] | sides["right"])
        missing = tuple(side for side, zones in sides.items() if not zones)
        if missing:
            return OutsideFacingBuildingWalk(
                "ABSTAINED",
                "source_dwelling_region_still_open_to_outside",
                enclosed_region_count=len(holes),
                enclosed_dwelling_zone_count=dwelling_count,
                unclosed_dwelling_sides=missing,
                internal_party_wall_native_path_ids=party_ids,
            )
        if sides["left"] & sides["right"]:
            return OutsideFacingBuildingWalk(
                "ABSTAINED",
                "party_wall_two_sides_are_same_free_space",
                enclosed_region_count=len(holes),
                enclosed_dwelling_zone_count=dwelling_count,
                internal_party_wall_native_path_ids=party_ids,
            )
        # Longitudinally walking the dividing wall would close one UNIT,
        # not the externally facing outside. Endpoints/T-junctions are fine.
        x0, y0, x1, y1 = divider.wall_bounds_pdf_pts
        from shapely.geometry import box

        wall = box(x0, y0, x1, y1)
        wall_long = (y1 - y0) if divider.orientation == "vertical" else (x1 - x0)
        if primary.exterior.intersection(wall.buffer(0.3)).length > 0.55 * wall_long:
            return OutsideFacingBuildingWalk(
                "ABSTAINED",
                "party_wall_used_as_external_walking_edge",
                enclosed_region_count=len(holes),
                enclosed_dwelling_zone_count=dwelling_count,
                internal_party_wall_native_path_ids=party_ids,
            )
    extra = sum(1 for geom, _ in owners if not primary.buffer(0.05).covers(geom))
    if extra:
        return OutsideFacingBuildingWalk(
            "ABSTAINED",
            "source_other_structural_walls_outside_candidate",
            enclosed_region_count=len(holes),
            enclosed_dwelling_zone_count=dwelling_count,
            other_source_wall_band_count=extra,
            internal_party_wall_native_path_ids=party_ids,
        )
    for label, point in _word_centers(source_words):
        if label in {
            "ALFRESCO",
            "PORCH",
            "PATIO",
            "VERANDA",
            "VERANDAH",
            "DECK",
        } and any(hole.contains(point) for hole in holes):
            return OutsideFacingBuildingWalk(
                "ABSTAINED",
                "outdoor_space_inside_proposed_building",
                enclosed_region_count=len(holes),
                enclosed_dwelling_zone_count=dwelling_count,
                internal_party_wall_native_path_ids=party_ids,
            )
    ring = _clockwise_page_ring(primary.exterior)
    if not ring:
        return OutsideFacingBuildingWalk(
            "ABSTAINED",
            "source_unbounded_face_not_closed",
            internal_party_wall_native_path_ids=party_ids,
        )
    # Source bar endpoints may meet outside boundary at a PARTY junction.
    # Only bars spanning a substantial outer segment are outside owners.
    exterior_paths = tuple(
        sorted(
            {
                pid
                for geom, ids in owners
                if primary.exterior.intersection(geom.buffer(0.02)).length
                >= 0.25
                * max(geom.bounds[2] - geom.bounds[0], geom.bounds[3] - geom.bounds[1])
                for pid in ids
            }
        )
    )
    exterior_paths = tuple(pid for pid in exterior_paths if pid not in party_ids)
    if len(exterior_paths) < 4:
        return OutsideFacingBuildingWalk(
            "ABSTAINED",
            "source_outside_face_wall_owners_incomplete",
            internal_party_wall_native_path_ids=party_ids,
        )
    return OutsideFacingBuildingWalk(
        "CANDIDATE",
        "unbounded_outside_wall_walk_requires_independent_source_seal",
        clockwise_pdf_pts=ring,
        outer_wall_native_path_ids=exterior_paths,
        internal_party_wall_native_path_ids=party_ids,
        enclosed_region_count=len(holes),
        enclosed_dwelling_zone_count=dwelling_count,
    )
