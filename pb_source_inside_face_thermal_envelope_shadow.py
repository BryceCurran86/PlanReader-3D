"""Shadow: inside-face clockwise thermal envelope for dual-dwelling footprints.

Cursor-02 (#4537). Reuses the unbounded outside-face walker and garage panel
topology bridges. The inside-face ring is the clockwise page boundary of the
dissolved dwelling occupancy voids (exterior-wall inner faces), never a hull
of porch/alfresco outdoor labels. Party / separating walls stay internal.

Garage panel doors may close the envelope FOR TOPOLOGY ONLY. This module does
not mint walls, FIRM areas, or customer rows.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from pb_source_garage_door_footprint_continuity import (
    detect_exterior_garage_door_footprint_bridges,
)
from pb_source_shared_dwelling_envelope_shadow import (
    CandidateSharedBuildingDivider,
)
from pb_source_unbounded_building_face_walk_shadow import (
    OutsideFacingBuildingWalk,
    _clockwise_page_ring,
    _owner,
    _word_centers,
    walk_source_unbounded_building_face,
)

_OUTDOOR_LABELS = frozenset(
    {
        "ALFRESCO",
        "PORCH",
        "PATIO",
        "VERANDA",
        "VERANDAH",
        "DECK",
        "CARPORT",
    }
)
_GARAGE_LABELS = frozenset({"GARAGE", "GARAGEDOOR", "PANELDOOR", "PANEL LIFT"})


@dataclass(frozen=True)
class InsideFaceThermalEnvelopeShadow:
    status: str
    reason: str
    inside_face_clockwise_pdf_pts: tuple[tuple[float, float], ...] = ()
    outside_face_clockwise_pdf_pts: tuple[tuple[float, float], ...] = ()
    outer_wall_native_path_ids: tuple[int, ...] = ()
    internal_party_wall_native_path_ids: tuple[int, ...] = ()
    garage_topology_bridge_count: int = 0
    garage_included: bool = False
    outdoor_excluded: bool = False
    enclosed_dwelling_zone_count: int = 0
    topology_only: bool = True
    physical_wall_authenticated: bool = False
    measurement_authorized: bool = False
    commercial_publishable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "inside_face_clockwise_pdf_pts": [
                list(p) for p in self.inside_face_clockwise_pdf_pts
            ],
            "outside_face_clockwise_pdf_pts": [
                list(p) for p in self.outside_face_clockwise_pdf_pts
            ],
            "outer_wall_native_path_ids": list(self.outer_wall_native_path_ids),
            "internal_party_wall_native_path_ids": list(
                self.internal_party_wall_native_path_ids
            ),
            "garage_topology_bridge_count": self.garage_topology_bridge_count,
            "garage_included": self.garage_included,
            "outdoor_excluded": self.outdoor_excluded,
            "enclosed_dwelling_zone_count": self.enclosed_dwelling_zone_count,
            "topology_only": True,
            "doorway_closure_is_not_physical_wall": True,
            "physical_wall_authenticated": False,
            "measurement_authorized": False,
            "commercial_publishable": False,
            "can_issue_area": False,
            "official_frozen120_score_change": 0,
        }


def _abstain(
    reason: str,
    *,
    walk: OutsideFacingBuildingWalk | None = None,
    garage_bridges: int = 0,
    outdoor_excluded: bool = False,
) -> InsideFaceThermalEnvelopeShadow:
    return InsideFaceThermalEnvelopeShadow(
        status="ABSTAINED",
        reason=reason,
        outside_face_clockwise_pdf_pts=(
            () if walk is None else walk.clockwise_pdf_pts
        ),
        outer_wall_native_path_ids=(
            () if walk is None else walk.outer_wall_native_path_ids
        ),
        internal_party_wall_native_path_ids=(
            () if walk is None else walk.internal_party_wall_native_path_ids
        ),
        garage_topology_bridge_count=garage_bridges,
        outdoor_excluded=outdoor_excluded,
        enclosed_dwelling_zone_count=(
            0 if walk is None else walk.enclosed_dwelling_zone_count
        ),
    )


def _label_tokens(source_words: Sequence[Any]) -> tuple[tuple[str, Point], ...]:
    out: list[tuple[str, Point]] = []
    for label, point in _word_centers(source_words):
        token = "".join(ch for ch in str(label).upper() if ch.isalnum())
        if token:
            out.append((token, point))
    return tuple(out)


def _occupancy_polygons_from_union(union: Any) -> tuple[Polygon, ...]:
    if union is None or getattr(union, "is_empty", True):
        return ()
    polygons = list(union.geoms) if hasattr(union, "geoms") else [union]
    holes: list[Polygon] = []
    for part in polygons:
        if not isinstance(part, Polygon) or not part.is_valid:
            continue
        for ring in part.interiors:
            poly = Polygon(ring)
            if poly.is_valid and not poly.is_empty and poly.area > 0:
                holes.append(poly)
    return tuple(holes)


def build_inside_face_thermal_envelope_shadow(
    wall_bars: Sequence[Any],
    source_words: Sequence[Any],
    *,
    shared_dividers: Sequence[CandidateSharedBuildingDivider] = (),
    source_wall_union: Any | None = None,
    source_drawings: Sequence[Mapping[str, Any] | object] = (),
    page_index: int = -1,
) -> InsideFaceThermalEnvelopeShadow:
    """Emit inside-face clockwise envelope or ABSTAIN with first failing gate."""
    drawings = tuple(source_drawings or ())
    garage_bridges = (
        detect_exterior_garage_door_footprint_bridges(
            drawings, source_words, page_index=page_index,
        )
        if drawings
        else ()
    )
    labels = _label_tokens(source_words)
    garage_labeled = any(
        token.startswith("GARAGE") or token in _GARAGE_LABELS
        for token, _pt in labels
    )

    walk = walk_source_unbounded_building_face(
        wall_bars,
        source_words,
        shared_dividers=shared_dividers,
        source_wall_union=source_wall_union,
        source_drawings=drawings or None,
    )
    if walk.status != "CANDIDATE" or not walk.clockwise_pdf_pts:
        return _abstain(
            walk.reason if walk.reason else "outside_face_not_candidate",
            walk=walk,
            garage_bridges=len(garage_bridges),
        )

    if garage_labeled and drawings and not garage_bridges:
        return _abstain(
            "garage_panel_topology_bridge_missing",
            walk=walk,
            garage_bridges=0,
        )

    # Drop internal party / separating walls before recovering the building
    # inside-face void. Dual dwellings share one exterior envelope; the
    # separating wall must not appear as an exterior edge.
    party_ids = set(walk.internal_party_wall_native_path_ids)
    envelope_geoms = []
    for bar in wall_bars:
        owned = _owner(bar)
        if owned is None:
            continue
        geom, ids = owned
        if party_ids and set(ids) and set(ids) <= party_ids:
            continue
        envelope_geoms.append(geom)
    envelope_union = unary_union(envelope_geoms) if envelope_geoms else source_wall_union
    holes = _occupancy_polygons_from_union(envelope_union)
    if not holes:
        return _abstain(
            "inside_face_occupancy_void_missing",
            walk=walk,
            garage_bridges=len(garage_bridges),
        )

    outdoor_points = [
        point for token, point in labels if token in _OUTDOOR_LABELS
    ]
    dwelling_holes: list[Polygon] = []
    outdoor_holes = 0
    for hole in holes:
        if any(hole.contains(pt) or hole.touches(pt) for pt in outdoor_points):
            outdoor_holes += 1
            continue
        dwelling_holes.append(hole)

    if outdoor_points and outdoor_holes == 0:
        # Outdoor labels sit on the proposed inside-face domain — fail closed.
        dissolved_probe = unary_union(holes)
        if any(
            dissolved_probe.contains(pt) or dissolved_probe.covers(pt)
            for pt in outdoor_points
        ):
            return _abstain(
                "outdoor_porch_or_alfresco_inside_proposed_inside_face",
                walk=walk,
                garage_bridges=len(garage_bridges),
                outdoor_excluded=False,
            )

    if not dwelling_holes:
        return _abstain(
            "no_dwelling_occupancy_after_outdoor_exclusion",
            walk=walk,
            garage_bridges=len(garage_bridges),
            outdoor_excluded=outdoor_holes > 0,
        )

    dissolved = unary_union(dwelling_holes)
    if not isinstance(dissolved, Polygon):
        return _abstain(
            "inside_face_not_single_building_footprint",
            walk=walk,
            garage_bridges=len(garage_bridges),
            outdoor_excluded=outdoor_holes > 0,
        )

    # Party wall must remain internal: it may touch the dissolved interior
    # but must not form a majority of the inside-face ring.
    for divider in shared_dividers:
        x0, y0, x1, y1 = (float(v) for v in divider.wall_bounds_pdf_pts)
        if not all(math.isfinite(v) for v in (x0, y0, x1, y1)):
            continue
        from shapely.geometry import box

        wall = box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        span = max(abs(x1 - x0), abs(y1 - y0))
        touch = dissolved.exterior.intersection(wall.buffer(0.3)).length
        if span > 0 and touch > 0.55 * span:
            return _abstain(
                "party_wall_used_as_inside_face_edge",
                walk=walk,
                garage_bridges=len(garage_bridges),
                outdoor_excluded=outdoor_holes > 0,
            )

    ring = _clockwise_page_ring(dissolved.exterior)
    if len(ring) < 5:
        return _abstain(
            "inside_face_ring_not_closed",
            walk=walk,
            garage_bridges=len(garage_bridges),
            outdoor_excluded=outdoor_holes > 0,
        )

    garage_included = False
    if garage_labeled:
        garage_pts = [
            point
            for token, point in labels
            if token.startswith("GARAGE") or token in _GARAGE_LABELS
        ]
        garage_included = any(
            dissolved.contains(pt) or dissolved.covers(pt) for pt in garage_pts
        )
        if not garage_included:
            return _abstain(
                "garage_label_outside_inside_face_envelope",
                walk=walk,
                garage_bridges=len(garage_bridges),
                outdoor_excluded=outdoor_holes > 0,
            )

    return InsideFaceThermalEnvelopeShadow(
        status="CANDIDATE",
        reason="inside_face_thermal_envelope_requires_independent_source_seal",
        inside_face_clockwise_pdf_pts=ring,
        outside_face_clockwise_pdf_pts=walk.clockwise_pdf_pts,
        outer_wall_native_path_ids=walk.outer_wall_native_path_ids,
        internal_party_wall_native_path_ids=walk.internal_party_wall_native_path_ids,
        garage_topology_bridge_count=len(garage_bridges),
        garage_included=garage_included or (not garage_labeled),
        outdoor_excluded=outdoor_holes > 0 or bool(outdoor_points),
        enclosed_dwelling_zone_count=walk.enclosed_dwelling_zone_count,
    )
