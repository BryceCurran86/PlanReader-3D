"""Generic spatial/viewport room-label to ceiling material-height association shadow.

Shadow-only, default-off source-evidence module (Item 4). Replaces brittle
same-`block_no` coupling with explicit viewport bounds, room polygon containment
or bounded unique spatial proximity, and strict ambiguity/conflict/legend vetoes.
Does NOT alter live ceiling issuers or grant commercial publication authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Sequence

from shapely.geometry import Point, Polygon

SHADOW_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class ViewportScopeInput:
    source_sha256: str
    page_id: str
    viewport_id: str
    bbox_pdf_pts: tuple[float, float, float, float]


@dataclass(frozen=True)
class RoomLabelSpatialObservation:
    room_id: str
    room_label: str
    source_sha256: str
    page_id: str
    viewport_id: str
    bbox_pdf_pts: tuple[float, float, float, float]
    block_no: int | None = None
    room_polygon_pdf_pts: tuple[tuple[float, float], ...] | None = None


@dataclass(frozen=True)
class CeilingMaterialHeightObservation:
    observation_id: str
    material_code: str
    height_mm: int | None
    source_sha256: str
    page_id: str
    viewport_id: str
    bbox_pdf_pts: tuple[float, float, float, float]
    block_no: int | None = None
    in_legend_or_title_region: bool = False
    raked_height_range_mm: tuple[int, int] | None = None


@dataclass(frozen=True)
class RoomCeilingSpatialAssociation:
    room_id: str
    room_label: str
    status: str  # "CORROBORATED_SPATIAL_SHADOW" | "ABSTAINED"
    association_mode: str  # "polygon_containment" | "bounded_nearest_room_label" | "none"
    material_code: str | None
    height_mm: int | None
    raked_height_range_mm: tuple[int, int] | None
    supporting_observation_ids: tuple[str, ...]
    recovered_across_distinct_block_no: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class SpatialCeilingLabelAssociationReport:
    status: str
    source_sha256: str
    page_id: str
    viewport_id: str
    room_associations: tuple[RoomCeilingSpatialAssociation, ...]
    same_block_no_count: int
    cross_block_spatial_recovered_count: int
    vetoed_ambiguous_observation_ids: tuple[str, ...]
    vetoed_legend_observation_ids: tuple[str, ...]
    vetoed_out_of_scope_observation_ids: tuple[str, ...]
    receipt_sha256: str
    commercial_projection_allowed: bool = False
    shadow_only: bool = True
    schema_version: str = SHADOW_SCHEMA_VERSION


def _center(b: tuple[float, float, float, float]) -> tuple[float, float]:
    return (0.5 * (float(b[0]) + float(b[2])), 0.5 * (float(b[1]) + float(b[3])))


def _inside_bbox(inner: tuple[float, float, float, float], outer: tuple[float, float, float, float]) -> bool:
    return (
        float(inner[0]) >= float(outer[0]) - 0.5
        and float(inner[1]) >= float(outer[1]) - 0.5
        and float(inner[2]) <= float(outer[2]) + 0.5
        and float(inner[3]) <= float(outer[3]) + 0.5
    )


def associate_ceiling_labels_spatially_shadow(
    *,
    viewport: ViewportScopeInput,
    rooms: Sequence[RoomLabelSpatialObservation],
    ceiling_observations: Sequence[CeilingMaterialHeightObservation],
    max_association_radius_pts: float = 90.0,
    min_uniqueness_margin_ratio: float = 0.65,
) -> SpatialCeilingLabelAssociationReport:
    """Associate ceiling material/height observations to rooms without requiring same block_no."""
    valid_rooms = [
        r
        for r in rooms
        if (
            r.source_sha256 == viewport.source_sha256
            and r.page_id == viewport.page_id
            and r.viewport_id == viewport.viewport_id
            and _inside_bbox(r.bbox_pdf_pts, viewport.bbox_pdf_pts)
        )
    ]

    room_polys: dict[str, Polygon] = {}
    for r in valid_rooms:
        if r.room_polygon_pdf_pts and len(r.room_polygon_pdf_pts) >= 3:
            poly = Polygon(r.room_polygon_pdf_pts)
            if poly.is_valid and poly.area > 0.0:
                room_polys[r.room_id] = poly

    vetoed_legend: list[str] = []
    vetoed_out_of_scope: list[str] = []
    vetoed_ambiguous: list[str] = []
    assigned_by_room: dict[str, list[tuple[CeilingMaterialHeightObservation, str, bool]]] = {
        r.room_id: [] for r in valid_rooms
    }
    same_block_count = 0
    cross_block_count = 0

    for obs in ceiling_observations:
        if obs.in_legend_or_title_region:
            vetoed_legend.append(obs.observation_id)
            continue
        if (
            obs.source_sha256 != viewport.source_sha256
            or obs.page_id != viewport.page_id
            or obs.viewport_id != viewport.viewport_id
            or not _inside_bbox(obs.bbox_pdf_pts, viewport.bbox_pdf_pts)
        ):
            vetoed_out_of_scope.append(obs.observation_id)
            continue
        if not valid_rooms:
            vetoed_out_of_scope.append(obs.observation_id)
            continue

        oc = _center(obs.bbox_pdf_pts)
        pt = Point(oc[0], oc[1])

        # Mode 1: Strict room polygon containment when polygons are provided
        if room_polys:
            containing = [r for r in valid_rooms if r.room_id in room_polys and room_polys[r.room_id].contains(pt)]
            if len(containing) == 1:
                owner = containing[0]
                distinct_blk = owner.block_no is None or obs.block_no is None or owner.block_no != obs.block_no
                if distinct_blk:
                    cross_block_count += 1
                else:
                    same_block_count += 1
                assigned_by_room[owner.room_id].append((obs, "polygon_containment", distinct_blk))
            elif len(containing) > 1:
                vetoed_ambiguous.append(obs.observation_id)
            else:
                vetoed_out_of_scope.append(obs.observation_id)
            continue

        # Mode 2: Bounded nearest room label with strict ambiguity margin veto
        scored = sorted(
            (
                (math.hypot(oc[0] - _center(r.bbox_pdf_pts)[0], oc[1] - _center(r.bbox_pdf_pts)[1]), r)
                for r in valid_rooms
            ),
            key=lambda pair: pair[0],
        )
        d1, r1 = scored[0]
        if d1 > max_association_radius_pts:
            vetoed_out_of_scope.append(obs.observation_id)
            continue
        if len(scored) > 1:
            d2 = scored[1][0]
            if d2 <= 0.0 or (d1 / d2) > min_uniqueness_margin_ratio:
                vetoed_ambiguous.append(obs.observation_id)
                continue
        distinct_blk = r1.block_no is None or obs.block_no is None or r1.block_no != obs.block_no
        if distinct_blk:
            cross_block_count += 1
        else:
            same_block_count += 1
        assigned_by_room[r1.room_id].append((obs, "bounded_nearest_room_label", distinct_blk))

    room_results: list[RoomCeilingSpatialAssociation] = []
    for r in valid_rooms:
        hits = assigned_by_room.get(r.room_id, [])
        if not hits:
            room_results.append(
                RoomCeilingSpatialAssociation(
                    room_id=r.room_id,
                    room_label=r.room_label,
                    status="ABSTAINED",
                    association_mode="none",
                    material_code=None,
                    height_mm=None,
                    raked_height_range_mm=None,
                    supporting_observation_ids=(),
                    recovered_across_distinct_block_no=False,
                    reason_codes=("no_owned_ceiling_observation",),
                )
            )
            continue

        mats = {o.material_code.strip().upper() for o, _, _ in hits if o.material_code and o.material_code.strip()}
        heights = {o.height_mm for o, _, _ in hits if o.height_mm is not None}
        raked = {o.raked_height_range_mm for o, _, _ in hits if o.raked_height_range_mm is not None}
        obs_ids = tuple(sorted(o.observation_id for o, _, _ in hits))
        mode = hits[0][1]
        any_cross_block = any(cb for _, _, cb in hits)

        reasons: list[str] = []
        if len(mats) != 1:
            reasons.append("conflicting_or_missing_ceiling_material_in_room")
        if len(heights) > 1 or len(raked) > 1 or (heights and raked):
            reasons.append("conflicting_ceiling_height_in_room")

        if reasons:
            room_results.append(
                RoomCeilingSpatialAssociation(
                    room_id=r.room_id,
                    room_label=r.room_label,
                    status="ABSTAINED",
                    association_mode=mode,
                    material_code=None,
                    height_mm=None,
                    raked_height_range_mm=None,
                    supporting_observation_ids=obs_ids,
                    recovered_across_distinct_block_no=any_cross_block,
                    reason_codes=tuple(reasons),
                )
            )
        else:
            room_results.append(
                RoomCeilingSpatialAssociation(
                    room_id=r.room_id,
                    room_label=r.room_label,
                    status="CORROBORATED_SPATIAL_SHADOW",
                    association_mode=mode,
                    material_code=next(iter(mats)),
                    height_mm=next(iter(heights)) if heights else None,
                    raked_height_range_mm=next(iter(raked)) if raked else None,
                    supporting_observation_ids=obs_ids,
                    recovered_across_distinct_block_no=any_cross_block,
                    reason_codes=("spatial_ceiling_label_associated_shadow",),
                )
            )

    payload = {
        "sha": viewport.source_sha256,
        "page": viewport.page_id,
        "vp": viewport.viewport_id,
        "rooms": [(ra.room_id, ra.status, ra.material_code, ra.height_mm, ra.raked_height_range_mm) for ra in room_results],
        "vetoed_ambiguous": sorted(vetoed_ambiguous),
        "vetoed_legend": sorted(vetoed_legend),
    }
    receipt = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    any_ok = any(ra.status == "CORROBORATED_SPATIAL_SHADOW" for ra in room_results)

    return SpatialCeilingLabelAssociationReport(
        status="SPATIAL_CEILING_ASSOCIATION_SHADOW_READY" if any_ok else "ABSTAINED",
        source_sha256=viewport.source_sha256,
        page_id=viewport.page_id,
        viewport_id=viewport.viewport_id,
        room_associations=tuple(room_results),
        same_block_no_count=same_block_count,
        cross_block_spatial_recovered_count=cross_block_count,
        vetoed_ambiguous_observation_ids=tuple(sorted(vetoed_ambiguous)),
        vetoed_legend_observation_ids=tuple(sorted(vetoed_legend)),
        vetoed_out_of_scope_observation_ids=tuple(sorted(vetoed_out_of_scope)),
        receipt_sha256=receipt,
    )
