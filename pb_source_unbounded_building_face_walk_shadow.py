"""Trace the source-owned UNBOUNDED outside face, not a closed dwelling loop.

This is a review-only *wall-network* walk. A building with two dwellings can
have two internal free-space faces sharing a PARTY wall, but only ONE outside
face. Never use a clockwise/left-turn closed UNIT ring as the building's
outside perimeter. No inferred wall, snapping, quantities or FIRM authority.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

from pb_source_shared_dwelling_envelope_shadow import (
    CandidateSharedBuildingDivider,
)

CONTACT_PT = 0.03
_SNAP_PT = 2.5  # commercial snap is never a join here
# Union AABB can sit a fraction of a point outside the outer wall face.
# That outdoor film is not a dwelling leak and is not a 2.5 pt snap.
_AABB_FILM_PT = 0.5


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
    # Review-only sample of exact source path indices from unresolved outside
    # wall-like bands. A composite can include conflicting owners: these are
    # candidate IDs to investigate, NOT authenticated exterior wall faces.
    unresolved_outside_native_path_id_sample: tuple[int, ...] = ()
    # Native role audit never manufactures exterior wall evidence.
    source_outside_band_count_before_role_audit: int = 0
    source_proven_nonwall_band_count: int = 0
    source_outside_role_audit_applied: bool = False
    # Shadow trace for review when other source-wall components remain.
    # Never use this ring to issue a customer quantity or report FIRM.
    diagnostic_unsealed_ring_pdf_pts: tuple[tuple[float, float], ...] = ()
    building_footprint_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = {
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
            "snap_join_applied": False,
            "convex_hull_applied": False,
            "layer_name_is_not_outer_role": True,
            "undirected_degree_is_not_outside_face_authority": True,
        }
        if self.unresolved_outside_native_path_id_sample:
            payload["unresolved_outside_native_path_id_sample"] = list(
                self.unresolved_outside_native_path_id_sample
            )
            payload["unresolved_owner_ids_are_review_only"] = True
        if self.source_outside_role_audit_applied:
            payload["source_outside_band_count_before_role_audit"] = (
                self.source_outside_band_count_before_role_audit
            )
            payload["source_proven_nonwall_band_count"] = (
                self.source_proven_nonwall_band_count
            )
            payload["source_outside_role_audit_noncommercial"] = True
        # Preserve byte-compatible old receipts when no unsealed preview
        # exists. Only outside-component ABSTAIN adds a diagnostic field.
        if self.diagnostic_unsealed_ring_pdf_pts:
            payload["diagnostic_unsealed_ring_pdf_pts"] = [
                list(point) for point in self.diagnostic_unsealed_ring_pdf_pts
            ]
            payload["diagnostic_unsealed_not_measurement"] = True
        return payload


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


def _source_frame_rule_overlaps_bar(geom: Polygon, row: Mapping[str, Any]) -> bool:
    """Require original frame-line geometry to match the alleged outside bar.

    A source path index from a proven sheet frame is insufficient if the
    supplied wall-like bar is physically somewhere else on the drawing.
    """
    from shapely.geometry import LineString

    items = row.get("items") or ()
    if len(items) != 1 or not items[0] or items[0][0] != "l":
        return False
    try:
        points = []
        for point in items[0][1:3]:
            if hasattr(point, "x"):
                coords = float(point.x), float(point.y)
            else:
                coords = float(point[0]), float(point[1])
            if not all(math.isfinite(v) for v in coords):
                return False
            points.append(coords)
        if len(points) != 2 or points[0] == points[1]:
            return False
        source_line = LineString(points)
        overlap = geom.buffer(CONTACT_PT).intersection(source_line).length
        return overlap >= min(1.0, 0.1 * source_line.length)
    except (IndexError, KeyError, TypeError, ValueError, OverflowError):
        return False


def _original_native_line_overlaps_bar(geom: Polygon, row: Mapping[str, Any]) -> bool:
    """Native PDF source ink on the alleged bar, never a blind position snap."""
    from shapely.geometry import LineString

    for item in row.get("items") or ():
        if not item or item[0] != "l" or len(item) < 3:
            continue
        try:
            points = []
            for point in item[1:3]:
                xy = ((float(point.x), float(point.y)) if hasattr(point, "x")
                      else (float(point[0]), float(point[1])))
                if not all(map(math.isfinite, xy)):
                    raise ValueError("source_nonfinite")
                points.append(xy)
            line = LineString(points)
            if line.length >= 1.0 and geom.buffer(CONTACT_PT).intersection(line).length >= min(1.0, 0.1 * line.length):
                return True
        except (ValueError, TypeError, IndexError, OverflowError):
            continue
    return False


def _pure_original_source_nonwall_bar(
    geom: Polygon, ids: tuple[int, ...],
    drawings: Sequence[Mapping[str, Any] | object],
) -> bool:
    """Every native owner must be independently classified non-wall, with ink."""
    prefixes = ("annotation_", "structure_slab")
    if not ids:
        return False
    owners = [drawings[i] for i in ids]
    if not all(
        isinstance(row, Mapping)
        and str(row.get("layer") or "").lower().startswith(prefixes)
        for row in owners
    ):
        return False
    from pb_source_native_exterior_endpoint_authority_shadow import (
        ROLE_EXCLUSION, classify_source_native_path_role,
    )
    if any(classify_source_native_path_role(row) != ROLE_EXCLUSION for row in owners):
        return False
    return any(_original_native_line_overlaps_bar(geom, row) for row in owners)


def _source_words_near_bar(geom: Polygon, words, *, radius: float) -> tuple[str, ...]:
    center = geom.centroid
    return tuple(label for label, point in _word_centers(words)
                 if center.distance(point) <= radius)


def _native_source_stroke_only(ids, drawings) -> bool:
    return bool(ids) and all(
        drawings[i].get("type") == "s" and drawings[i].get("fill") is None
        and type(drawings[i].get("width")) in (float, int)
        and 0 < float(drawings[i]["width"]) <= 0.85
        for i in ids
    )


def _source_mixed_title_frame_nonwall(geom: Polygon, ids, drawings, sheet_nonwall) -> bool:
    """Source authenticated frame plus attached native annotation, no wall."""
    if not sheet_nonwall or not any(i in sheet_nonwall for i in ids):
        return False
    if not all(
        i in sheet_nonwall
        or str(drawings[i].get("layer") or "").lower().startswith("annotation_")
        for i in ids
    ):
        return False
    if any(
        i in sheet_nonwall
        and not _original_native_line_overlaps_bar(geom, drawings[i])
        for i in ids
    ):
        return False
    return any(_original_native_line_overlaps_bar(geom, drawings[i]) for i in ids)


def _source_printed_scale_graphic_nonwall(geom: Polygon, ids, drawings, words) -> bool:
    """Require source drawn scale bar + SCALE and spaced original printed ticks."""
    if not _native_source_stroke_only(ids, drawings):
        return False
    if not all(
        str(drawings[i].get("layer") or "").lower() in ("", "annotation_general")
        for i in ids
    ):
        return False
    if not any(_original_native_line_overlaps_bar(geom, drawings[i]) for i in ids):
        return False
    rows = _word_centers(words)
    for name, title in rows:
        if name != "SCALE":
            continue
        numbers = [
            (int(label), point) for label, point in rows
            if label in {str(k) for k in range(10)}
            and 0 < point.x - title.x < 360
            and 0 < point.y - title.y < 16
        ]
        by_number = {n: point for n, point in numbers}
        if not all(n in by_number for n in range(7)):
            continue
        steps = [by_number[n + 1].x - by_number[n].x for n in range(6)]
        if min(steps) <= 0 or max(steps) - min(steps) > 1.5:
            continue
        x0, y0, x1, y1 = geom.bounds
        if (by_number[0].x - 10 <= x0 <= x1 <= by_number[6].x + 170
                and title.y - 25 <= y0 <= y1 <= title.y + 27):
            return True
    return False


def _source_named_compact_outside_post(geom: Polygon, ids, drawings, words) -> bool:
    """Native compact solid square and original POST/ALFRESCO printed words."""
    if len(ids) != 1:
        return False
    source = drawings[ids[0]]
    layer = str(source.get("layer") or "").lower()
    if "wall" not in layer or "external" not in layer:
        return False
    if source.get("type") != "f" or source.get("fill") is None:
        return False
    if max(source["fill"]) > 0.4:
        return False
    width, height = geom.bounds[2] - geom.bounds[0], geom.bounds[3] - geom.bounds[1]
    if not (0.5 <= min(width, height) and max(width, height) <= 6.0
            and max(width, height) / min(width, height) < 1.8):
        return False
    return (
        "POST" in _source_words_near_bar(geom, words, radius=75)
        and "ALFRESCO" in _source_words_near_bar(geom, words, radius=95)
    )


def _source_named_service_nonwall(geom: Polygon, ids, drawings, words) -> bool:
    """Original stormwater downpipe or bottled gas source symbols, not walls."""
    if len(ids) < 2 or not _native_source_stroke_only(ids, drawings):
        return False
    layers = {str(drawings[i].get("layer") or "").lower() for i in ids}
    if not layers or not all(layer.startswith("service_") for layer in layers):
        return False
    if not any(_original_native_line_overlaps_bar(geom, drawings[i]) for i in ids):
        return False
    labels = _source_words_near_bar(geom, words, radius=40)
    if "service_stormwatergeneral" in layers:
        return "DP" in labels
    if layers == {"service_gas.bottled"} and len(ids) >= 3:
        return geom.bounds[2] - geom.bounds[0] < 20 and geom.bounds[3] - geom.bounds[1] < 30
    return False


def _source_outdoor_nonwall_tick(geom: Polygon, ids, drawings, words) -> bool:
    """Small native outdoor slab/roof/datum mark, not a solid filled wall."""
    if len(ids) < 2 or not _native_source_stroke_only(ids, drawings):
        return False
    width, height = geom.bounds[2] - geom.bounds[0], geom.bounds[3] - geom.bounds[1]
    if max(width, height) > 15.0 or min(width, height) <= 0:
        return False
    layers = {str(drawings[i].get("layer") or "").lower() for i in ids}
    if "structure_slab" not in layers or not (
        "structure_roof" in layers or "finish_floor" in layers
    ):
        return False
    if not any(_original_native_line_overlaps_bar(geom, drawings[i]) for i in ids):
        return False
    labels = _source_words_near_bar(geom, words, radius=95)
    return any(x in labels for x in ("ALFRESCO", "PORCH", "DECK", "PATIO"))


def _source_numbered_dimension_tick(geom: Polygon, ids, drawings, words) -> bool:
    """Short, unfilled native extension intersecting printed dimension chain."""
    import re

    if len(ids) < 2 or not _native_source_stroke_only(ids, drawings):
        return False
    width, height = geom.bounds[2] - geom.bounds[0], geom.bounds[3] - geom.bounds[1]
    if min(width, height) <= 0 or max(width, height) > 15.0:
        return False
    layers = {str(drawings[i].get("layer") or "").lower() for i in ids}
    if not any("wall" in layer and "external" in layer for layer in layers):
        return False
    if any(layer.startswith("enclosure_wallinternal") for layer in layers):
        return False
    if not any(_original_native_line_overlaps_bar(geom, drawings[i]) for i in ids):
        return False
    labels = _source_words_near_bar(geom, words, radius=55)
    numbers = [label for label in labels if re.fullmatch(r"[0-9][0-9,]*", label)]
    return len(set(numbers)) >= 2


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


def _native_path_bounds_pdf_pts(row: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    """Exact native rect or stroke AABB; never invents missing path geometry."""
    rect = row.get("rect")
    if rect is not None:
        try:
            x0, y0, x1, y1 = (float(v) for v in rect[:4])
            if all(math.isfinite(v) for v in (x0, y0, x1, y1)):
                return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        except (TypeError, ValueError, IndexError):
            pass
    xs: list[float] = []
    ys: list[float] = []
    for item in row.get("items") or ():
        if not item:
            continue
        kind = item[0]
        try:
            if kind == "l" and len(item) >= 3:
                for point in item[1:3]:
                    if hasattr(point, "x"):
                        xs.append(float(point.x))
                        ys.append(float(point.y))
                    else:
                        xs.append(float(point[0]))
                        ys.append(float(point[1]))
            elif kind in {"re", "qu"} and len(item) >= 2:
                r = item[1]
                x0, y0, x1, y1 = (float(v) for v in r[:4])
                xs.extend((x0, x1))
                ys.extend((y0, y1))
        except (TypeError, ValueError, IndexError, AttributeError):
            continue
    if not xs or not ys:
        return None
    if not all(math.isfinite(v) for v in (*xs, *ys)):
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def _local_residual_path_ids(
    bar_geom: Any,
    path_ids: Sequence[int],
    source_drawings: Sequence[Mapping[str, Any] | object],
) -> tuple[int, ...]:
    """Path IDs whose native geometry intersects the outside residual bar.

    Aggregated wall bars can carry foreign path IDs from distant co-merged
    strokes. Residual role audit must not treat those foreign WallExternal
    IDs as local owners of a remote outside band.
    """
    probe = bar_geom.buffer(CONTACT_PT)
    local: list[int] = []
    for idx in path_ids:
        if not (type(idx) is int and 0 <= idx < len(source_drawings)):
            continue
        row = source_drawings[idx]
        if not isinstance(row, Mapping):
            continue
        bounds = _native_path_bounds_pdf_pts(row)
        if bounds is None:
            continue
        x0, y0, x1, y1 = bounds
        # Degenerate strokes still need a positive probe footprint.
        if abs(x1 - x0) <= CONTACT_PT and abs(y1 - y0) <= CONTACT_PT:
            hit = Point(x0, y0).buffer(CONTACT_PT)
        else:
            hit = box(x0, y0, x1, y1)
        if probe.intersects(hit):
            local.append(idx)
    return tuple(local)


class _LocalResidualBar:
    """Bar view exposing only locally intersecting native path IDs."""

    __slots__ = ("_ids", "polygon")

    def __init__(self, bar: Any, local_ids: Sequence[int]):
        self.polygon = bar.polygon
        self._ids = tuple(local_ids)

    def native_path_indices(self) -> tuple[int, ...]:
        return self._ids


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


def _as_polygons(geom) -> tuple[Polygon, ...]:
    if geom is None or getattr(geom, "is_empty", True):
        return ()
    if isinstance(geom, Polygon):
        return (geom,) if geom.is_valid else ()
    parts = getattr(geom, "geoms", ())
    found: list[Polygon] = []
    for part in parts:
        found.extend(_as_polygons(part))
    return tuple(found)


def _party_covering_components(
    components: Sequence[Any],
    divider: CandidateSharedBuildingDivider,
) -> tuple[Polygon, ...]:
    wall = box(*divider.wall_bounds_pdf_pts)
    hit = []
    for part in components:
        if not isinstance(part, Polygon) or not part.is_valid or part.is_empty:
            continue
        if part.intersects(wall):
            hit.append(part)
    return tuple(hit)


def _bounded_free_space_faces(primary: Polygon) -> tuple[Polygon, ...]:
    """Conditioned-space faces inside the wall-paint bbox, not sheet-outside.

    Wall-cavity pinholes are valid polygons with interiors, but they are not
    dwelling rooms. Rooms live in the complement of the painted bars. A face
    that reaches the inset clip edge is still open to the page / outdoors.
    The inset drops only the AABB-to-wall outdoor film; it is smaller than
    SNAP_PT and smaller than a source opening.
    """
    x0, y0, x1, y1 = primary.bounds
    if (x1 - x0) <= 2 * _AABB_FILM_PT or (y1 - y0) <= 2 * _AABB_FILM_PT:
        return ()
    clip = box(x0 + _AABB_FILM_PT, y0 + _AABB_FILM_PT, x1 - _AABB_FILM_PT, y1 - _AABB_FILM_PT)
    free = clip.difference(primary)
    edge = clip.boundary
    faces = []
    for part in _as_polygons(free):
        if part.area <= 0 or not math.isfinite(part.area):
            continue
        if part.distance(edge) <= CONTACT_PT:
            continue
        faces.append(part)
    return tuple(faces)


def walk_source_unbounded_building_face(
    wall_bars: Sequence[Any],
    source_words: Sequence[Mapping[str, Any] | Sequence[Any]],
    *,
    shared_dividers: Sequence[CandidateSharedBuildingDivider] = (),
    source_wall_union: Any | None = None,
    source_drawings: Sequence[Mapping[str, Any] | object] | None = None,
) -> OutsideFacingBuildingWalk:
    """Walk OUTSIDE-facing source wall network; fail closed on unjoined zones.

    Reuse the original already-computed wall/hosted-opening union from the
    source preflight when supplied; do not make duplicate OCR/geometry passes.
    A missing party wall or a source-named room still open to the outside
    is not repaired by a sketch, a bounding hull or a direct endpoint snap.
    Optional ``source_drawings`` only supplies native path identity for
    source-negative non-wall role discrimination; it never invents walls.
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
    occupancy_faces: tuple[Polygon, ...] = ()
    if shared_dividers:
        if len(shared_dividers) != 1:
            return OutsideFacingBuildingWalk(
                "ABSTAINED",
                "several_party_dividers_require_dwelling_zone_graph",
                enclosed_region_count=len(closed),
                internal_party_wall_native_path_ids=party_ids,
            )
        covering = _party_covering_components(components, shared_dividers[0])
        if len(covering) != 1:
            return OutsideFacingBuildingWalk(
                "ABSTAINED",
                "outside_face_source_wall_domain_not_unique_and_closed",
                internal_party_wall_native_path_ids=party_ids,
            )
        primary = covering[0]
    elif len(closed) != 1:
        return OutsideFacingBuildingWalk(
            "ABSTAINED",
            "outside_face_source_wall_domain_not_unique_and_closed",
            internal_party_wall_native_path_ids=party_ids,
        )
    else:
        primary = closed[0]
    holes = tuple(Polygon(r) for r in primary.interiors)
    occupancy_faces = holes
    dwelling_count = 0
    if shared_dividers:
        divider = shared_dividers[0]
        words = _word_centers(source_words)
        sides = _occupied_party_regions(holes, words, divider)
        if not sides["left"] or not sides["right"]:
            free_faces = _bounded_free_space_faces(primary)
            if free_faces:
                occupancy_faces = free_faces
                sides = _occupied_party_regions(free_faces, words, divider)
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
    # The wall paint is a polygon with ROOM holes. An independently drawn
    # internal physical partition or cabinet wall can occupy a room hole
    # without touching the primary wall-paint network; it remains INSIDE
    # the building exterior ring. Compare to the filled outer footprint,
    # not the wall-paint polygon (whose holes would falsely eject it).
    # Truly outside structural bodies remain a hard abstention.
    candidate_outer_domain = Polygon(primary.exterior).buffer(0.05)
    # Original sheets include remote black annotation, slab and service paint
    # which can be collected as wall-shaped geometry. Existing source role
    # classification independently distinguishes those non-wall natives.
    # The same physical exterior walker and union remain unchanged; this
    # check never crops coordinates or creates a missing wall.
    outside = [
        (bar, owned) for bar in wall_bars
        if (owned := _owner(bar)) is not None
        and not candidate_outer_domain.covers(owned[0])
    ]
    excluded_nonwall = 0
    unresolved: list[tuple[Any, tuple[int, ...]]] = []
    if source_drawings is not None:
        from pb_source_native_exterior_endpoint_authority_shadow import (
            ROLE_EXCLUSION,
            ROLE_EXTERIOR_OUTER_FACE,
            ROLE_INTERNAL_WALL,
            classify_source_native_path_role,
        )
        from pb_source_outer_house_continuity_shadow import (
            ROLE_OUTDOOR,
            ROLE_POST,
            classify_outside_envelope_role,
        )
        from pb_source_sheet_frame_roles_shadow import (
            source_sheet_frame_nonwall_path_ids,
        )

        sheet_nonwall = source_sheet_frame_nonwall_path_ids(
            source_drawings, source_words,
        )

        def _service_or_roof_layer(row: Mapping[str, Any]) -> bool:
            compact = "".join(
                c for c in str(row.get("layer") or "").lower() if c.isalnum()
            )
            return any(
                token in compact
                for token in ("service", "storm", "gas", "roof", "finish")
            )

        def _nonwall_residual_path(idx: int) -> bool:
            # Only *independently source-authenticated* nonwalls can be
            # excluded. A thin unlayered, unfilled source stroke may be a real
            # external wall face: its style alone cannot prove sheet furniture.
            # Genuine full title-frame membership is verified separately.
            if idx in sheet_nonwall:
                return True
            row = source_drawings[idx]
            return (
                classify_source_native_path_role(row) == ROLE_EXCLUSION
                and _service_or_roof_layer(row)
            )

        for bar, (geom, ids) in outside:
            # A stale/partial native-path index or conflicting viewport
            # makes the candidate unresolved. Never trust one excluded
            # owner in a mixed structural/unknown composite.
            valid = all(
                type(idx) is int and 0 <= idx < len(source_drawings)
                and isinstance(source_drawings[idx], Mapping)
                for idx in ids
            )
            if not valid:
                unresolved.append((bar, ids))
                continue
            local_ids = _local_residual_path_ids(geom, ids, source_drawings)
            if not local_ids:
                # No independently located native path on this residual
                # band; fail closed rather than drop or invent owners.
                unresolved.append((bar, local_ids))
                continue
            viewports = {
                str(
                    source_drawings[idx].get("source_viewport_id")
                    or source_drawings[idx].get("viewport_id")
                    or ""
                ).strip()
                for idx in local_ids
            }
            if len(viewports) != 1:
                unresolved.append((bar, local_ids))
                continue
            local_bar = _LocalResidualBar(bar, local_ids)
            path_roles = {
                classify_source_native_path_role(source_drawings[idx])
                for idx in local_ids
            }
            role, _reason = classify_outside_envelope_role(
                local_bar, source_drawings, source_words,
            )
            if role in (ROLE_OUTDOOR, ROLE_POST):
                excluded_nonwall += 1
            elif sheet_nonwall and all(
                idx in sheet_nonwall
                or classify_source_native_path_role(source_drawings[idx])
                == ROLE_EXCLUSION
                for idx in local_ids
            ):
                # A layerless sheet frame + annotation composite is neither
                # a house wall nor an excuse to drop a mixed physical owner.
                excluded_nonwall += 1
            elif (
                ROLE_EXTERIOR_OUTER_FACE not in path_roles
                and ROLE_INTERNAL_WALL not in path_roles
                and all(_nonwall_residual_path(idx) for idx in local_ids)
            ):
                excluded_nonwall += 1
            else:
                unresolved.append((bar, local_ids))
    else:
        unresolved = [(bar, ids) for bar, (_geom, ids) in outside]
    extra = len(unresolved)
    if extra:
        # Both occupied dwelling zones are independently enclosed, but
        # unresolved source-wall components exist beyond the outer ring.
        # Retain a source-native preview for reviewer attribution ONLY.
        # The authoritative clockwise_pdf_pts and wall IDs stay empty.
        preview_ring = _clockwise_page_ring(primary.exterior)
        return OutsideFacingBuildingWalk(
            "ABSTAINED",
            "source_other_structural_walls_outside_candidate",
            enclosed_region_count=len(holes),
            enclosed_dwelling_zone_count=dwelling_count,
            other_source_wall_band_count=extra,
            unresolved_outside_native_path_id_sample=tuple(dict.fromkeys(
                int(pid) for _bar, ids in unresolved for pid in ids
                if type(pid) is int and pid >= 0
            ))[:64],
            source_outside_band_count_before_role_audit=len(outside),
            source_proven_nonwall_band_count=excluded_nonwall,
            source_outside_role_audit_applied=source_drawings is not None,
            internal_party_wall_native_path_ids=party_ids,
            diagnostic_unsealed_ring_pdf_pts=(
                preview_ring if 5 <= len(preview_ring) <= 20_000 else ()
            ),
        )
    for label, point in _word_centers(source_words):
        if label in {
            "ALFRESCO",
            "PORCH",
            "PATIO",
            "VERANDA",
            "VERANDAH",
            "DECK",
        } and any(face.contains(point) for face in occupancy_faces):
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


def _topology_host_pairs(
    drawings: Sequence[Mapping[str, Any] | object],
    source_words: Sequence[Mapping[str, Any] | Sequence[Any]],
) -> tuple[frozenset[int], ...]:
    pairs: list[frozenset[int]] = []

    def _add(left, right) -> None:
        try:
            a, b = int(left), int(right)
        except (TypeError, ValueError):
            return
        if a != b:
            pairs.append(frozenset((a, b)))

    if not drawings:
        return ()
    from pb_source_garage_door_footprint_continuity import (
        detect_exterior_garage_door_footprint_bridges,
    )
    from pb_source_neutral_wall_seam_continuity import detect_source_neutral_wall_seams
    from pb_source_swing_door_footprint_continuity import (
        detect_exterior_swing_door_footprint_bridges,
    )
    from pb_source_window_footprint_continuity import (
        detect_exterior_window_footprint_bridges,
    )

    try:
        from pb_source_sliding_door_footprint_continuity import (
            detect_exterior_sliding_door_footprint_bridges,
        )
    except ImportError:
        def detect_exterior_sliding_door_footprint_bridges(*_a, **_k):
            return ()

    for seam in detect_source_neutral_wall_seams(drawings, page_index=-1):
        _add(seam.first_host_path_id, seam.second_host_path_id)
    if source_words:
        for bridge in detect_exterior_window_footprint_bridges(drawings, source_words):
            _add(bridge.left_host_path_id, bridge.right_host_path_id)
        for bridge in detect_exterior_garage_door_footprint_bridges(drawings, source_words):
            _add(bridge.start_host_path_id, bridge.end_host_path_id)
        for bridge in detect_exterior_swing_door_footprint_bridges(drawings, source_words):
            _add(bridge.first_host_path_id, bridge.second_host_path_id)
        for bridge in detect_exterior_sliding_door_footprint_bridges(drawings, source_words):
            _add(
                getattr(bridge, "first_host_path_id", None),
                getattr(bridge, "second_host_path_id", None),
            )
    unique = []
    seen = set()
    for pair in pairs:
        if pair in seen:
            continue
        seen.add(pair)
        unique.append(pair)
    return tuple(unique)


def diagnose_source_outside_face_neighbors(
    wall_bars: Sequence[Any],
    native_path_id: int,
    *,
    drawings: Sequence[Mapping[str, Any] | object] = (),
    source_words: Sequence[Mapping[str, Any] | Sequence[Any]] = (),
    shared_dividers: Sequence[CandidateSharedBuildingDivider] = (),
    source_wall_union: Any | None = None,
) -> dict[str, object]:
    """Receipts for one source path on the canonical outside face.

    An interior T-junction may give undirected degree > 2. That is not
    missing ink and is not an instruction to snap. The canonical walk
    still follows the unbounded union exterior, not this neighbor count.
    """
    try:
        query_id = int(native_path_id)
    except (TypeError, ValueError):
        query_id = -1
    owners = []
    for bar in wall_bars:
        owned = _owner(bar)
        if owned is None:
            continue
        owners.append((owned[0], owned[1], bar))
    query = [(geom, ids, bar) for geom, ids, bar in owners if query_id in ids]
    party_ids = frozenset(i for d in shared_dividers for i in d.wall_native_path_ids)
    topology = _topology_host_pairs(drawings, source_words)
    grey_pairs = []
    if drawings:
        from pb_source_neutral_wall_seam_continuity import (
            detect_source_neutral_wall_seams,
        )
        grey_pairs = [
            {
                "first_host_path_id": seam.first_host_path_id,
                "second_host_path_id": seam.second_host_path_id,
                "neutral_fill_path_ids": list(seam.neutral_fill_path_ids),
                "kind": "source_neutral_grey_wall_seam_continuity_only",
                "measurement_authorized": False,
            }
            for seam in detect_source_neutral_wall_seams(drawings, page_index=-1)
            if query_id in (seam.first_host_path_id, seam.second_host_path_id)
        ]
    union = source_wall_union
    if union is None and owners:
        union = unary_union([geom for geom, _ids, _bar in owners])
    primary = None
    if union is not None:
        parts = list(union.geoms) if hasattr(union, "geoms") else [union]
        if shared_dividers and len(shared_dividers) == 1:
            covering = _party_covering_components(parts, shared_dividers[0])
            if len(covering) == 1:
                primary = covering[0]
        else:
            closed = [p for p in parts if isinstance(p, Polygon) and p.is_valid and p.interiors]
            if len(closed) == 1:
                primary = closed[0]
    neighbors = []
    if query:
        q_geom = unary_union([geom for geom, _ids, _bar in query])
        seen: set[tuple[int, ...]] = set()
        for geom, ids, _bar in owners:
            if query_id in ids:
                continue
            dist = float(q_geom.distance(geom))
            if not math.isfinite(dist):
                continue
            id_set = frozenset(ids)
            pair_hit = any(query_id in pair and pair & id_set for pair in topology)
            if dist > CONTACT_PT and not pair_hit:
                if dist <= _SNAP_PT:
                    neighbors.append({
                        "native_path_ids": list(ids),
                        "kind": "near_miss_unauthenticated_no_snap",
                        "separation_pdf_pts": round(dist, 4),
                        "physical_join_authenticated": False,
                    })
                continue
            if party_ids.intersection(ids):
                kind = "party_interior_divider_contact"
            elif pair_hit:
                kind = "source_neutral_or_opening_topology_only"
            elif primary is not None and primary.exterior.intersection(geom.buffer(0.02)).length >= 0.25 * max(
                geom.bounds[2] - geom.bounds[0], geom.bounds[3] - geom.bounds[1],
            ):
                kind = "representation_contact_exterior"
            else:
                kind = "interior_t_or_partition_contact"
            key = tuple(sorted(ids))
            if key in seen:
                continue
            seen.add(key)
            neighbors.append({
                "native_path_ids": list(ids),
                "kind": kind,
                "separation_pdf_pts": round(dist, 4),
                "physical_join_authenticated": False,
            })
        neighbors.sort(key=lambda row: (row["separation_pdf_pts"], row["native_path_ids"]))
    walk = walk_source_unbounded_building_face(
        wall_bars,
        source_words,
        shared_dividers=shared_dividers,
        source_wall_union=source_wall_union,
    )
    contact_degree = sum(
        1 for row in neighbors
        if row["kind"] != "near_miss_unauthenticated_no_snap"
    )
    return {
        "native_path_id": query_id,
        "neighbor_count": contact_degree,
        "undirected_degree_gt_2": contact_degree > 2,
        "undirected_degree_does_not_veto_outside_face": True,
        "neighbors": neighbors,
        "grey_seam_pairs": grey_pairs,
        "canonical_walk_status": walk.status,
        "canonical_walk_reason": walk.reason,
        "outer_wall_native_path_ids": list(walk.outer_wall_native_path_ids),
        "internal_party_wall_native_path_ids": list(walk.internal_party_wall_native_path_ids),
        "snap_join_applied": False,
        "convex_hull_applied": False,
        "physical_wall_authenticated": False,
        "building_footprint_authenticated": False,
        "measurement_authorized": False,
        "official_frozen120_score_change": 0,
    }
