"""Component-aware floor-finish geometry derived only from drawing evidence.

A compound footprint may mix enclosed rooms with open verandahs.  The structural
footprint for slab/DPM/mesh follows the evidenced outer component geometry, while
an internal floor finish inside an enclosed rectangular room is measured to the
clear wall faces when a wall thickness is independently corroborated.

This module contains no benchmark identities, expected quantities, project names,
or convenience thicknesses.  Missing, ambiguous, unsupported, or partial geometry
fails closed by returning ``None``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Dict, Optional

from pb_multi_space_footprint_geometry import (
    FootprintGeometryResult,
    FootprintStatus,
    SpaceType,
)


@dataclass(frozen=True)
class ComponentFloorFinishResult:
    """Traceable finish-area result for one enclosed main space plus verandahs."""

    structural_footprint_area_m2: float
    floor_finish_area_m2: float
    wall_thickness_m: float
    main_component_id: str
    main_outer_length_m: float
    main_outer_width_m: float
    main_clear_length_m: float
    main_clear_width_m: float
    main_clear_area_m2: float
    open_verandah_area_m2: float
    component_finish_areas_m2: Dict[str, float] = field(default_factory=dict)



def _component_rectangles_are_disjoint(components: list) -> bool:
    """Only sum separately sourced finish areas when their metric footprints close.

    A plausible L x W and a CONFIRMED flag do not prove the footprint polygon
    agrees with the figured dimensions.  In a compound layout an overlap is
    already counted twice by a sum of component areas; shared boundary edges
    are allowed but an interior intersection is not. No inferred transform,
    location, scale or polygon may repair a missing source footprint.
    """
    try:
        from shapely.geometry import Polygon

        if not components:
            return False
        if len({c.space_id for c in components}) != len(components):
            return False
        if any(type(c.space_id) is not str or not c.space_id.strip() for c in components):
            return False

        polygons = []
        for comp in components:
            if (
                type(comp.length_m) not in (int, float)
                or type(comp.width_m) not in (int, float)
                or type(comp.area_m2) not in (int, float)
                or any(not math.isfinite(float(v)) or v <= 0.0 for v in
                       (comp.length_m, comp.width_m, comp.area_m2))
            ):
                return False
            if not math.isclose(
                comp.area_m2, comp.length_m * comp.width_m,
                rel_tol=0.0, abs_tol=0.011,
            ):
                return False

            # For a sole enclosed rectangle, two independently evidenced
            # orthogonal dimensions suffice. Multiple components require
            # their own full source placement to prove absence of overlap.
            if not comp.polygon:
                if len(components) != 1:
                    return False
                continue
            ring = tuple(comp.polygon)
            if len(ring) == 5 and ring[0] == ring[-1]:
                ring = ring[:-1]
            if len(ring) != 4 or len(set(ring)) != 4:
                return False
            if any(
                type(pt) not in (tuple, list)
                or len(pt) != 2
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in pt)
                for pt in ring
            ):
                return False
            polygon = Polygon(ring)
            if not polygon.is_valid or polygon.is_empty or polygon.area <= 0.0:
                return False
            edges = tuple(
                (ring[(i + 1) % 4][0] - ring[i][0],
                 ring[(i + 1) % 4][1] - ring[i][1])
                for i in range(4)
            )
            lengths = tuple(math.hypot(*edge) for edge in edges)
            if min(lengths) <= 0:
                return False
            if any(
                abs(edges[i][0] * edges[(i + 1) % 4][0] +
                    edges[i][1] * edges[(i + 1) % 4][1]) >
                1e-6 * lengths[i] * lengths[(i + 1) % 4]
                for i in range(4)
            ):
                return False
            actual_sides = sorted((lengths[0], lengths[1]))
            recorded_sides = sorted((comp.length_m, comp.width_m))
            if any(abs(a - b) > 0.011 for a, b in zip(actual_sides, recorded_sides)):
                return False
            if not math.isclose(polygon.area, comp.area_m2, rel_tol=0, abs_tol=0.011):
                return False
            for earlier in polygons:
                if polygon.intersection(earlier).area > 1e-8:
                    return False
            polygons.append(polygon)
        return True
    except (ImportError, TypeError, ValueError, OverflowError, AttributeError):
        return False


def derive_component_aware_floor_finish_area(
    footprint: FootprintGeometryResult,
    wall_thickness_m: Optional[float],
) -> Optional[ComponentFloorFinishResult]:
    """Resolve a compound floor-finish area without changing structural area.

    Supported evidence shape:
    - footprint is fully confirmed with no missing components or voids;
    - exactly one evidenced rectangular ``MAIN_BUILDING`` component;
    - every other solid component is an evidenced ``VERANDAH``;
    - wall thickness is independently resolved and physically valid.

    The enclosed main component is converted from outer dimensions to clear-face
    dimensions using ``(L - 2t) * (W - 2t)``.  Verandah components remain at their
    full evidenced area because they are not enclosed by the main room's two
    opposing wall faces.  Ancillary/unspecified components and voids are left
    unresolved rather than assuming their enclosure or finish basis.
    """
    if wall_thickness_m is None or not math.isfinite(wall_thickness_m) or wall_thickness_m <= 0.0:
        return None
    if footprint.status != FootprintStatus.CONFIRMED.value or footprint.missing_components:
        return None
    if footprint.metadata.get("num_voids", 0):
        return None

    main_components = [
        c for c in footprint.components
        if not c.is_void and c.space_type == SpaceType.MAIN_BUILDING.value
    ]
    if len(main_components) != 1:
        return None

    solid_components = [c for c in footprint.components if not c.is_void]
    if any(
        c.space_type not in (SpaceType.MAIN_BUILDING.value, SpaceType.VERANDAH.value)
        for c in solid_components
    ):
        return None
    if not _component_rectangles_are_disjoint(solid_components):
        return None
    if any(
        not c.has_evidenced_dimensions or c.missing_dimensions
        for c in solid_components
    ):
        return None

    main = main_components[0]
    if main.length_m is None or main.width_m is None:
        return None
    if not math.isfinite(main.length_m) or not math.isfinite(main.width_m):
        return None
    if main.length_m <= 0.0 or main.width_m <= 0.0:
        return None

    clear_length_m = main.length_m - 2.0 * wall_thickness_m
    clear_width_m = main.width_m - 2.0 * wall_thickness_m
    if clear_length_m <= 0.0 or clear_width_m <= 0.0:
        return None

    component_finish_areas: Dict[str, float] = {}
    main_clear_area = clear_length_m * clear_width_m
    component_finish_areas[main.space_id] = round(main_clear_area, 2)

    verandah_area = 0.0
    for comp in solid_components:
        if comp.space_type != SpaceType.VERANDAH.value:
            continue
        if not math.isfinite(comp.area_m2) or comp.area_m2 < 0.0:
            return None
        verandah_area += comp.area_m2
        component_finish_areas[comp.space_id] = round(comp.area_m2, 2)

    finish_area = main_clear_area + verandah_area
    if not math.isfinite(finish_area) or finish_area <= 0.0:
        return None

    return ComponentFloorFinishResult(
        structural_footprint_area_m2=round(footprint.gross_floor_area_m2, 2),
        floor_finish_area_m2=round(finish_area, 2),
        wall_thickness_m=round(wall_thickness_m, 4),
        main_component_id=main.space_id,
        main_outer_length_m=round(main.length_m, 4),
        main_outer_width_m=round(main.width_m, 4),
        main_clear_length_m=round(clear_length_m, 4),
        main_clear_width_m=round(clear_width_m, 4),
        main_clear_area_m2=round(main_clear_area, 2),
        open_verandah_area_m2=round(verandah_area, 2),
        component_finish_areas_m2=component_finish_areas,
    )
