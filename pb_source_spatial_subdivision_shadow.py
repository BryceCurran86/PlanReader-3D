"""Shadow: source-owned spatial subdivision with outside/courtyard classification.

AntiGravity P4 on GPT1's research->repo handoff.
Builds 2D spatial subdivision from source wall bodies and native space keys:
1. One explicit outside face (unbounded world).
2. Internal courtyard holes (open-to-sky voids enclosed by walls).
3. Attached carport / outdoor regions (partially enclosed or semi-outdoor).
4. Disconnected structures / decoys (sheds, landscape lines, adversarial decoys).
5. Oriented wall boundary faces (exterior envelope, courtyard envelope, partition).

Zero customer quantities, zero FIRM, no convex hull, no artificial area issuance.
"""
from __future__ import annotations

import enum
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import median
from typing import Any

from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

from pb_migration_contracts import EvidenceResolutionStatus
from pb_new_numbered_space_key import NumberedSpaceKeyResult
from pb_source_native_wall_body_junction_graph_shadow import (
    CONTACT_PT,
    _unique_source_wall_bars,
    classify_source_wall_body_junctions,
)


class SpatialRegionKind(str, enum.Enum):
    OUTSIDE_UNBOUNDED = "outside_unbounded"
    INTERIOR_ENCLOSED_ROOM = "interior_enclosed_room"
    INTERNAL_COURTYARD_HOLE = "internal_courtyard_hole"
    ATTACHED_OUTDOOR_REGION = "attached_outdoor_region"
    DISCONNECTED_STRUCTURE_OR_DECOY = "disconnected_structure_or_decoy"
    UNVERIFIED_ENCLOSED_CANDIDATE = "unverified_enclosed_candidate"
    NATIVE_SOURCE_MICRO_VOID = "native_source_micro_void"


REASON_SPATIAL_OK = "spatial_subdivision_candidate_observed"
REASON_INSUFFICIENT_WALLS = "insufficient_source_wall_bodies_for_building"
REASON_NO_OUTSIDE_FACE = "explicit_outside_face_not_resolved"
REASON_DISCONNECTED_DECOY = "disconnected_decoy_component_rejected"
REASON_OPEN_BOUNDARY_LEAK = "open_wall_boundary_leaks_to_outside"
REASON_UNVERIFIED_ENCLOSURE = "closed_native_geometry_in_disconnected_component_not_conditioned_space"
REASON_MICRO_SOURCE_VOID = "sub_room_scale_enclosure_in_native_wall_ink"
REASON_OTHER_WALL_INK_OUTSIDE = "source_exterior_other_wall_ink_outside_candidate"
REASON_PARTIAL_CYCLE_ROOM = "interior_geometry_in_unclosed_building_with_other_wall_ink_outside"


@dataclass(frozen=True)
class SpatialRegionRecord:
    region_id: str
    kind: SpatialRegionKind
    bounds_pdf_pts: tuple[float, float, float, float]
    polygon_pdf_pts: tuple[tuple[float, float], ...]
    area_pdf_pts: float
    label: str | None
    semantic_role: str
    bounding_wall_body_ids: tuple[str, ...]
    bounding_native_path_ids: tuple[int, ...]
    is_hole_in_building: bool
    is_conditioned_living: bool
    status: EvidenceResolutionStatus
    reason: str
    physical_space_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_id": self.region_id,
            "kind": self.kind.value,
            "bounds_pdf_pts": list(self.bounds_pdf_pts),
            "polygon_pdf_pts": [list(pt) for pt in self.polygon_pdf_pts],
            "area_pdf_pts": round(self.area_pdf_pts, 3),
            "label": self.label,
            "semantic_role": self.semantic_role,
            "bounding_wall_body_ids": list(self.bounding_wall_body_ids),
            "bounding_native_path_ids": list(self.bounding_native_path_ids),
            "is_hole_in_building": self.is_hole_in_building,
            "is_conditioned_living": self.is_conditioned_living,
            "status": self.status.value,
            "reason": self.reason,
            "physical_space_authenticated": False,
            "measurement_authorized": False,
        }


@dataclass(frozen=True)
class SpatialBoundaryFaceRecord:
    boundary_id: str
    wall_body_id: str
    native_path_ids: tuple[int, ...]
    left_region_id: str
    right_region_id: str
    left_kind: str
    right_kind: str
    is_exterior_envelope: bool
    is_courtyard_envelope: bool
    is_interior_partition: bool
    separation_distance_pts: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "boundary_id": self.boundary_id,
            "wall_body_id": self.wall_body_id,
            "native_path_ids": list(self.native_path_ids),
            "left_region_id": self.left_region_id,
            "right_region_id": self.right_region_id,
            "left_kind": self.left_kind,
            "right_kind": self.right_kind,
            "is_exterior_envelope": self.is_exterior_envelope,
            "is_courtyard_envelope": self.is_courtyard_envelope,
            "is_interior_partition": self.is_interior_partition,
            "separation_distance_pts": round(self.separation_distance_pts, 4),
        }


@dataclass(frozen=True)
class SpatialSubdivisionResult:
    status: EvidenceResolutionStatus
    reason: str
    total_region_count: int
    interior_room_count: int
    courtyard_hole_count: int
    attached_outdoor_count: int
    disconnected_decoy_count: int
    unverified_enclosed_count: int = 0
    micro_source_void_count: int = 0
    regions: tuple[SpatialRegionRecord, ...] = ()
    boundary_faces: tuple[SpatialBoundaryFaceRecord, ...] = ()
    outside_region_id: str = ""
    has_explicit_outside_face: bool = False
    primary_building_body_count: int = 0
    physical_space_authenticated: bool = False
    measurement_authorized: bool = False
    commercial_publishable: bool = False
    official_frozen120_score_change: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "reason": self.reason,
            "total_region_count": self.total_region_count,
            "interior_room_count": self.interior_room_count,
            "courtyard_hole_count": self.courtyard_hole_count,
            "attached_outdoor_count": self.attached_outdoor_count,
            "disconnected_decoy_count": self.disconnected_decoy_count,
            "unverified_enclosed_count": self.unverified_enclosed_count,
            "micro_source_void_count": self.micro_source_void_count,
            "outside_region_id": self.outside_region_id,
            "has_explicit_outside_face": self.has_explicit_outside_face,
            "primary_building_body_count": self.primary_building_body_count,
            "regions": [r.to_dict() for r in self.regions],
            "boundary_faces": [f.to_dict() for f in self.boundary_faces],
            "physical_space_authenticated": False,
            "measurement_authorized": False,
            "commercial_publishable": False,
            "official_frozen120_score_change": 0,
        }


def _is_outdoor_name(name: str) -> bool:
    t = " " + re.sub(r"[^A-Z ]", " ", name.upper()) + " "
    return any(x in t for x in (
        " ALFRESCO ", " AL FRESCO ", " OUTDOOR ", " OUTDOOR LIVING ",
        " CARPORT ", " COURT ", " COURTYARD ", " PORTICO ",
        " ALFRESCO ", " PATIO ", " PORCH ", " TERRACE ", " VERANDAH ",
        " BALCONY ", " DRIVEWAY ", " DECK ", " PERGOLA ",
        " WATER TANK ", " GARDEN ", " ATRIUM ", " VOID ",
        " LANAI ", " CABANA ",
    ))


def _is_courtyard_name(name: str) -> bool:
    t = " " + re.sub(r"[^A-Z ]", " ", name.upper()) + " "
    return any(x in t for x in (
        " COURT ", " COURTYARD ", " ATRIUM ", " INTERNAL VOID ", " VOID ",
    ))


def _clean_coords(poly: Polygon) -> tuple[tuple[float, float], ...]:
    if poly.exterior is None:
        return ()
    return tuple(
        (round(float(x), 3), round(float(y), 3))
        for x, y in list(poly.exterior.coords)[:-1]
    )


def build_source_spatial_subdivision(
    drawings: Sequence[Mapping[str, Any] | object] = (),
    *,
    bars: Sequence[Any] | None = None,
    page_rect: tuple[float, float, float, float] | None = None,
    space_key: NumberedSpaceKeyResult | None = None,
    text_words: Sequence[Sequence[Any]] | None = None,
) -> SpatialSubdivisionResult:
    """Subdivide sheet space into outside, interior, courtyards, and outdoor."""
    if bars is None:
        bars = _unique_source_wall_bars(drawings)
    bodies, _ = classify_source_wall_body_junctions(bars, drawings)

    if len(bars) < 4 or len(bodies) < 4:
        return SpatialSubdivisionResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason=REASON_INSUFFICIENT_WALLS,
            total_region_count=0,
            interior_room_count=0,
            courtyard_hole_count=0,
            attached_outdoor_count=0,
            disconnected_decoy_count=0,
        )

    # 1. Page / canvas boundary
    if page_rect is not None:
        canvas_box = box(*page_rect)
    else:
        min_x = min(float(b.polygon.bounds[0]) for b in bars)
        min_y = min(float(b.polygon.bounds[1]) for b in bars)
        max_x = max(float(b.polygon.bounds[2]) for b in bars)
        max_y = max(float(b.polygon.bounds[3]) for b in bars)
        margin = 150.0
        canvas_box = box(min_x - margin, min_y - margin, max_x + margin, max_y + margin)

    # 2. Wall bodies union & connected components
    wall_polygons = [
        bar.polygon for bar in bars
        if bar.polygon is not None and not bar.polygon.is_empty
    ]
    wall_union = unary_union(wall_polygons)
    components = (
        list(wall_union.geoms) if hasattr(wall_union, "geoms") else [wall_union]
    )

    # Identify primary building component vs disconnected decoys
    bar_to_comp: dict[int, int] = {}
    comp_bar_counts: dict[int, int] = {idx: 0 for idx in range(len(components))}
    for b_idx, bar in enumerate(bars):
        for c_idx, comp in enumerate(components):
            if comp.intersects(bar.polygon):
                bar_to_comp[b_idx] = c_idx
                comp_bar_counts[c_idx] += 1
                break

    primary_c_idx = (
        max(comp_bar_counts, key=comp_bar_counts.get) if comp_bar_counts else 0
    )
    primary_comp = components[primary_c_idx]
    primary_outer_poly = (
        Polygon(primary_comp.exterior)
        if isinstance(primary_comp, Polygon) and primary_comp.exterior
        else box(*primary_comp.bounds)
    )

    # Building components: primary component + internal islands (courtyards).
    # Disconnected decoys are exterior components located outside primary envelope.
    building_c_indices = {primary_c_idx}
    for c_idx, comp in enumerate(components):
        if c_idx != primary_c_idx and primary_outer_poly.buffer(1.0).contains(comp):
            building_c_indices.add(c_idx)

    # Collect disconnected decoy or unclosed building wall bodies
    disconnected_body_ids = []
    disconnected_path_ids = []
    outside_bars = []
    for b_idx, bar in enumerate(bars):
        if bar_to_comp.get(b_idx) not in building_c_indices:
            disconnected_body_ids.append(bodies[b_idx].body_id)
            disconnected_path_ids.extend(bodies[b_idx].provenance.native_path_ids)
            outside_bars.append(bar)

    # Evaluate whether wall ink outside primary_outer_poly represents
    # an unclosed building envelope with genuine adjacent/substantial walls
    # ("source_exterior_other_wall_ink_outside_candidate"), or isolated decoys.
    has_other_wall_ink_outside = False
    if outside_bars:
        min_dist_to_primary = min(
            primary_comp.distance(b.polygon) for b in outside_bars
        ) if primary_comp is not None and not primary_comp.is_empty else 1e9

        # A single partial closed ring (e.g. left wing) with other substantial walls
        # or directly adjacent walls (doorway gap <= 50.0 pt) beyond it is NOT the outer
        # building boundary. Count every independent source-painted wall bar.
        if (
            len(outside_bars) >= 12
            or (min_dist_to_primary <= 50.0 and len(outside_bars) >= 4)
            or len(outside_bars) > comp_bar_counts.get(primary_c_idx, 0)
        ):
            has_other_wall_ink_outside = True

    # A free-space polygon cannot become a primary-building room if its
    # enclosing wall owners belong exclusively to detached components.
    disconnected_body_set = frozenset(disconnected_body_ids)
    # Compare a free-space island against the scale of *source wall bands*,
    # not a project-specific PDF-point or room-area constant. Thin wall
    # strokes can enclose tiny paint holes that are not room candidates.
    wall_band_girths = []
    for bar in bars:
        bx0, by0, bx1, by1 = bar.polygon.bounds
        width, height = bx1 - bx0, by1 - by0
        girth = min(width, height)
        if girth > 0.1 and max(width, height) >= 3.0 * girth:
            wall_band_girths.append(girth)
    minimum_room_candidate_span = (
        6.0 * median(wall_band_girths) if wall_band_girths else 0.0
    )

    # 3. Planar Free Space Subdivision
    free_space = canvas_box.difference(wall_union)
    free_geoms = (
        list(free_space.geoms) if hasattr(free_space, "geoms") else [free_space]
    )

    regions: list[SpatialRegionRecord] = []
    region_geoms: list[tuple[SpatialRegionRecord, Polygon]] = []
    boundary_faces: list[SpatialBoundaryFaceRecord] = []

    outside_region_id = ""
    has_outside = False

    # Collect known spaces from space_key or text_words
    known_spaces: list[tuple[str, str, Point]] = []
    if space_key is not None and space_key.entries:
        for entry in space_key.entries:
            for marker in entry.number_markers_pdf_pts:
                known_spaces.append((entry.name, entry.semantic_role, Point(marker)))
            if not entry.number_markers_pdf_pts and entry.key_label_bbox_pdf_pts:
                kb = entry.key_label_bbox_pdf_pts
                center = Point((kb[0] + kb[2]) / 2.0, (kb[1] + kb[3]) / 2.0)
                known_spaces.append((entry.name, entry.semantic_role, center))

    if text_words is not None:
        for w in text_words:
            if len(w) >= 5:
                cx = (float(w[0]) + float(w[2])) / 2.0
                cy = (float(w[1]) + float(w[3])) / 2.0
                txt = str(w[4]).strip().upper()
                if _is_outdoor_name(txt):
                    known_spaces.append(
                        (txt, "outdoor_or_nonroom_candidate", Point(cx, cy))
                    )

    # Process free geoms
    region_idx = 0
    for geom in free_geoms:
        if not isinstance(geom, Polygon) or geom.is_empty or not geom.is_valid:
            continue
        poly_bounds = tuple(round(float(v), 3) for v in geom.bounds)
        coords = _clean_coords(geom)
        area = float(geom.area)

        # Check if touches the canvas border -> OUTSIDE_UNBOUNDED
        touches_canvas_border = (
            abs(geom.bounds[0] - canvas_box.bounds[0]) < 1.0 or
            abs(geom.bounds[1] - canvas_box.bounds[1]) < 1.0 or
            abs(geom.bounds[2] - canvas_box.bounds[2]) < 1.0 or
            abs(geom.bounds[3] - canvas_box.bounds[3]) < 1.0
        )

        if touches_canvas_border:
            r_id = f"region:outside:{region_idx}"
            outside_region_id = r_id
            has_outside = True
            rec = SpatialRegionRecord(
                region_id=r_id,
                kind=SpatialRegionKind.OUTSIDE_UNBOUNDED,
                bounds_pdf_pts=poly_bounds,
                polygon_pdf_pts=coords,
                area_pdf_pts=area,
                label="OUTSIDE",
                semantic_role="outside_unbounded_domain",
                bounding_wall_body_ids=(),
                bounding_native_path_ids=(),
                is_hole_in_building=False,
                is_conditioned_living=False,
                status=EvidenceResolutionStatus.CANDIDATE,
                reason="unbounded_outside_domain_touching_canvas_border",
            )
            regions.append(rec)
            region_geoms.append((rec, geom))
            region_idx += 1
            continue

        # Check enclosing wall bars for this region
        touching_body_ids = []
        touching_path_ids = []
        for b_idx, bar in enumerate(bars):
            if geom.distance(bar.polygon) <= CONTACT_PT:
                touching_body_ids.append(bodies[b_idx].body_id)
                touching_path_ids.extend(bodies[b_idx].provenance.native_path_ids)

        touching_body_ids = tuple(sorted(set(touching_body_ids)))
        touching_path_ids = tuple(sorted(set(touching_path_ids)))

        # Detached closed wall loops also bound free-space polygons. They
        # are not conditioned/interior rooms of the primary structure. Keep
        # their source paths in the existing disconnected-decoy ABSTAIN
        # record below rather than publishing the same paths as both kinds.
        if not touching_body_ids:
            continue
        if all(body_id in disconnected_body_set for body_id in touching_body_ids):
            # Preserve source-closed geometric voids for plan review, but do
            # not classify them as conditioned rooms or feed wall-face ownership.
            # A separate detached-structure record retains the same path IDs
            # as a component-level diagnostic, not an extra physical room.
            span = min(
                float(poly_bounds[2] - poly_bounds[0]),
                float(poly_bounds[3] - poly_bounds[1]),
            )
            is_micro_void = (
                minimum_room_candidate_span > 0
                and span < minimum_room_candidate_span
            )
            regions.append(SpatialRegionRecord(
                region_id=f"region:unverified:{region_idx}",
                kind=(
                    SpatialRegionKind.NATIVE_SOURCE_MICRO_VOID if is_micro_void
                    else SpatialRegionKind.UNVERIFIED_ENCLOSED_CANDIDATE
                ),
                bounds_pdf_pts=poly_bounds,
                polygon_pdf_pts=coords,
                area_pdf_pts=area,
                label=None,
                semantic_role=(
                    "small_source_wall_ink_void_not_room"
                    if is_micro_void
                    else "unverified_room_sized_geometry_not_room_authority"
                ),
                bounding_wall_body_ids=touching_body_ids,
                bounding_native_path_ids=touching_path_ids,
                is_hole_in_building=False,
                is_conditioned_living=False,
                status=EvidenceResolutionStatus.ABSTAINED,
                reason=(
                    REASON_MICRO_SOURCE_VOID if is_micro_void
                    else REASON_UNVERIFIED_ENCLOSURE
                ),
            ))
            region_idx += 1
            continue

        # Find any space label inside this geometry
        matched_label = None
        matched_role = "named_interior_candidate_not_verified"
        for name, role, pt in known_spaces:
            if geom.contains(pt):
                matched_label = name
                matched_role = role
                break

        # Classify internal region:
        # Courtyard hole vs Carport/Outdoor vs Interior room
        is_courtyard = False
        is_attached_outdoor = False

        if matched_label is not None:
            if _is_courtyard_name(matched_label):
                is_courtyard = True
            elif _is_outdoor_name(matched_label):
                is_attached_outdoor = True

        if is_courtyard:
            r_id = f"region:courtyard:{region_idx}"
            rec = SpatialRegionRecord(
                region_id=r_id,
                kind=SpatialRegionKind.INTERNAL_COURTYARD_HOLE,
                bounds_pdf_pts=poly_bounds,
                polygon_pdf_pts=coords,
                area_pdf_pts=area,
                label=matched_label,
                semantic_role=matched_role,
                bounding_wall_body_ids=touching_body_ids,
                bounding_native_path_ids=touching_path_ids,
                is_hole_in_building=True,
                is_conditioned_living=False,
                status=EvidenceResolutionStatus.CANDIDATE,
                reason="internal_courtyard_void_enclosed_by_walls",
            )
            regions.append(rec)
            region_geoms.append((rec, geom))
        elif is_attached_outdoor:
            r_id = f"region:outdoor:{region_idx}"
            rec = SpatialRegionRecord(
                region_id=r_id,
                kind=SpatialRegionKind.ATTACHED_OUTDOOR_REGION,
                bounds_pdf_pts=poly_bounds,
                polygon_pdf_pts=coords,
                area_pdf_pts=area,
                label=matched_label,
                semantic_role=matched_role,
                bounding_wall_body_ids=touching_body_ids,
                bounding_native_path_ids=touching_path_ids,
                is_hole_in_building=False,
                is_conditioned_living=False,
                status=EvidenceResolutionStatus.CANDIDATE,
                reason="attached_outdoor_region_with_semi_enclosed_walls",
            )
            regions.append(rec)
            region_geoms.append((rec, geom))
        else:
            if has_other_wall_ink_outside:
                # The candidate cycle is only a partial building section, not the
                # authenticated exterior building footprint. Bounded voids inside it
                # are unverified candidate geometry and must not issue living room
                # authority or customer finish FIRM.
                r_id = f"region:unverified:{region_idx}"
                rec = SpatialRegionRecord(
                    region_id=r_id,
                    kind=SpatialRegionKind.UNVERIFIED_ENCLOSED_CANDIDATE,
                    bounds_pdf_pts=poly_bounds,
                    polygon_pdf_pts=coords,
                    area_pdf_pts=area,
                    label=matched_label,
                    semantic_role="unverified_partial_building_room_candidate_not_room_authority",
                    bounding_wall_body_ids=touching_body_ids,
                    bounding_native_path_ids=touching_path_ids,
                    is_hole_in_building=False,
                    is_conditioned_living=False,
                    status=EvidenceResolutionStatus.ABSTAINED,
                    reason=REASON_OTHER_WALL_INK_OUTSIDE,
                )
                regions.append(rec)
                region_geoms.append((rec, geom))
            else:
                r_id = f"region:interior:{region_idx}"
                rec = SpatialRegionRecord(
                    region_id=r_id,
                    kind=SpatialRegionKind.INTERIOR_ENCLOSED_ROOM,
                    bounds_pdf_pts=poly_bounds,
                    polygon_pdf_pts=coords,
                    area_pdf_pts=area,
                    label=matched_label,
                    semantic_role=matched_role,
                    bounding_wall_body_ids=touching_body_ids,
                    bounding_native_path_ids=touching_path_ids,
                    is_hole_in_building=False,
                    is_conditioned_living=True,
                    status=EvidenceResolutionStatus.CANDIDATE,
                    reason="interior_enclosed_conditioned_room_candidate",
                )
                regions.append(rec)
                region_geoms.append((rec, geom))
        region_idx += 1

    # 4. Disconnected Decoy / Structure region record
    if disconnected_body_ids and not has_other_wall_ink_outside:
        disc_polys = [
            bars[i].polygon for i, b in enumerate(bodies)
            if b.body_id in disconnected_body_ids
        ]
        disc_bounds = tuple(
            round(float(v), 3) for v in unary_union(disc_polys).bounds
        )
        regions.append(SpatialRegionRecord(
            region_id=f"region:decoy:{region_idx}",
            kind=SpatialRegionKind.DISCONNECTED_STRUCTURE_OR_DECOY,
            bounds_pdf_pts=disc_bounds,
            polygon_pdf_pts=(),
            area_pdf_pts=0.0,
            label="DISCONNECTED_DECOY_OR_STRUCTURE",
            semantic_role="disconnected_structure_or_decoy",
            bounding_wall_body_ids=tuple(sorted(set(disconnected_body_ids))),
            bounding_native_path_ids=tuple(sorted(set(disconnected_path_ids))),
            is_hole_in_building=False,
            is_conditioned_living=False,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason=REASON_DISCONNECTED_DECOY,
        ))

    # 5. Boundary Face Classification via Longitudinal Face Sampling
    outside_reg = next(
        (r for r in regions if r.kind == SpatialRegionKind.OUTSIDE_UNBOUNDED),
        None,
    )
    for b_idx, body in enumerate(bodies):
        if body.body_id in disconnected_body_ids:
            continue
        bar = bars[b_idx]
        bx0, by0, bx1, by1 = (float(v) for v in bar.polygon.bounds)
        bcx = (bx0 + bx1) / 2.0
        bcy = (by0 + by1) / 2.0

        if (bx1 - bx0) >= (by1 - by0):
            # Horizontal wall: sample top and bottom faces
            pt_left = Point(bcx, by0 - 0.5)
            pt_right = Point(bcx, by1 + 0.5)
        else:
            # Vertical wall: sample left and right faces
            pt_left = Point(bx0 - 0.5, bcy)
            pt_right = Point(bx1 + 0.5, bcy)

        # Find closest region for left/top face
        best_left_reg = outside_reg
        min_d_left = 1e9
        for reg, poly in region_geoms:
            if poly is not None:
                d = float(poly.distance(pt_left))
                if d < min_d_left:
                    min_d_left = d
                    best_left_reg = reg

        # Find closest region for right/bottom face
        best_right_reg = outside_reg
        min_d_right = 1e9
        for reg, poly in region_geoms:
            if poly is not None:
                d = float(poly.distance(pt_right))
                if d < min_d_right:
                    min_d_right = d
                    best_right_reg = reg

        left_reg = best_left_reg
        right_reg = best_right_reg

        l_kind = (
            left_reg.kind.value if left_reg
            else SpatialRegionKind.OUTSIDE_UNBOUNDED.value
        )
        r_kind = (
            right_reg.kind.value if right_reg
            else SpatialRegionKind.OUTSIDE_UNBOUNDED.value
        )

        ext_candidates = (
            SpatialRegionKind.OUTSIDE_UNBOUNDED.value,
            SpatialRegionKind.ATTACHED_OUTDOOR_REGION.value,
        )
        is_ext = (
            (
                l_kind == SpatialRegionKind.INTERIOR_ENCLOSED_ROOM.value and
                r_kind in ext_candidates
            ) or
            (
                r_kind == SpatialRegionKind.INTERIOR_ENCLOSED_ROOM.value and
                l_kind in ext_candidates
            )
        )
        if (
            has_other_wall_ink_outside
            and is_ext
            and any(bar.polygon.distance(ob.polygon) <= 50.0 for ob in outside_bars)
        ):
            # If this wall face is adjacent to outside building wall ink, it faces
            # unclosed building interior, not genuine exterior/outdoor domain.
            is_ext = False
        is_ct = (
            (
                l_kind == SpatialRegionKind.INTERIOR_ENCLOSED_ROOM.value and
                r_kind == SpatialRegionKind.INTERNAL_COURTYARD_HOLE.value
            ) or
            (
                r_kind == SpatialRegionKind.INTERIOR_ENCLOSED_ROOM.value and
                l_kind == SpatialRegionKind.INTERNAL_COURTYARD_HOLE.value
            )
        )
        is_part = (
            l_kind == SpatialRegionKind.INTERIOR_ENCLOSED_ROOM.value and
            r_kind == SpatialRegionKind.INTERIOR_ENCLOSED_ROOM.value
        )

        boundary_faces.append(SpatialBoundaryFaceRecord(
            boundary_id=f"boundary:{body.body_id}",
            wall_body_id=body.body_id,
            native_path_ids=body.provenance.native_path_ids,
            left_region_id=left_reg.region_id if left_reg else "",
            right_region_id=right_reg.region_id if right_reg else "",
            left_kind=l_kind,
            right_kind=r_kind,
            is_exterior_envelope=is_ext,
            is_courtyard_envelope=is_ct,
            is_interior_partition=is_part,
            separation_distance_pts=0.0,
        ))

    interior_rooms = [
        r for r in regions if r.kind == SpatialRegionKind.INTERIOR_ENCLOSED_ROOM
    ]
    courtyards = [
        r for r in regions if r.kind == SpatialRegionKind.INTERNAL_COURTYARD_HOLE
    ]
    outdoor_attached = [
        r for r in regions if r.kind == SpatialRegionKind.ATTACHED_OUTDOOR_REGION
    ]
    decoys = [
        r for r in regions
        if r.kind == SpatialRegionKind.DISCONNECTED_STRUCTURE_OR_DECOY
    ]
    unverified_enclosed = [
        r for r in regions
        if r.kind == SpatialRegionKind.UNVERIFIED_ENCLOSED_CANDIDATE
    ]
    micro_source_voids = [
        r for r in regions
        if r.kind == SpatialRegionKind.NATIVE_SOURCE_MICRO_VOID
    ]

    if has_other_wall_ink_outside:
        status = EvidenceResolutionStatus.ABSTAINED
        reason = REASON_OTHER_WALL_INK_OUTSIDE
    elif has_outside:
        status = EvidenceResolutionStatus.CANDIDATE
        reason = REASON_SPATIAL_OK
    else:
        status = EvidenceResolutionStatus.ABSTAINED
        reason = REASON_NO_OUTSIDE_FACE

    return SpatialSubdivisionResult(
        status=status,
        reason=reason,
        total_region_count=len(regions),
        interior_room_count=len(interior_rooms),
        courtyard_hole_count=len(courtyards),
        attached_outdoor_count=len(outdoor_attached),
        disconnected_decoy_count=len(decoys),
        unverified_enclosed_count=len(unverified_enclosed),
        micro_source_void_count=len(micro_source_voids),
        regions=tuple(regions),
        boundary_faces=tuple(boundary_faces),
        outside_region_id=outside_region_id,
        has_explicit_outside_face=has_outside,
        primary_building_body_count=len(bodies) - len(disconnected_body_ids),
        physical_space_authenticated=False,
        measurement_authorized=False,
        commercial_publishable=False,
        official_frozen120_score_change=0,
    )
