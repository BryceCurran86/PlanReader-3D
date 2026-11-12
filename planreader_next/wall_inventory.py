"""Topology-only source wall, opening and region inventory.

Consumes existing enclosure rings, native finished-face receipts and virtual
opening fills. Face-role labels are hypotheses. This is not a wall layer,
finished-face authority, hosted-opening quantity or customer row.
"""
from __future__ import annotations

from typing import Any, Sequence

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from .engine import NativePage
from .hash_chain import _FACE_PT, bind_polygon_hash_axes
from .topology_faces import _path_index_from_segment_ref, native_finished_face_receipts


def _hash_payload(bound: Any) -> dict[str, Any] | None:
    if bound is None:
        return None
    return {
        "length_mm": format(bound.length_mm.normalize(), "f"),
        "word_refs": list(bound.word_refs),
        "hash_stations": [float(value) for value in bound.hash_stations],
        "side": bound.side,
    }


def _parse_edge(item_id: str) -> tuple[str, int] | None:
    prefix, separator, rest = item_id.rpartition("/edge/")
    if not separator or not rest.isdigit():
        return None
    return prefix, int(rest)


def _edge_midpoint(region: dict[str, Any], edge_index: int) -> tuple[float, float] | None:
    polygon = region.get("boundary_polygon_pdf_pts") or []
    if edge_index < 0 or edge_index >= len(polygon):
        return None
    x0, y0 = polygon[edge_index]
    x1, y1 = polygon[(edge_index + 1) % len(polygon)]
    return (float(x0) + float(x1)) / 2.0, (float(y0) + float(y1)) / 2.0


def _candidate_polygons(regions: Sequence[dict[str, Any]]) -> list[tuple[dict[str, Any], Polygon]]:
    found: list[tuple[dict[str, Any], Polygon]] = []
    for region in regions:
        if region.get("status") != "candidate" or region.get("likely_cavity_pocket"):
            continue
        polygon = Polygon(region.get("boundary_polygon_pdf_pts") or [])
        if not polygon.is_valid or polygon.is_empty:
            continue
        found.append((region, polygon))
    return found


def _face_role(
    midpoint: tuple[float, float],
    region_id: str,
    polygons: Sequence[tuple[dict[str, Any], Polygon]],
    union: Any,
) -> tuple[str, str]:
    if union is None or union.is_empty:
        return "ABSTAIN", "no_union_hull"
    point = Point(midpoint)
    on_hull = point.distance(union.boundary) <= _FACE_PT
    covering = [
        region["region_id"]
        for region, polygon in polygons
        if polygon.buffer(_FACE_PT).covers(point)
    ]
    unique = list(dict.fromkeys(covering))
    if on_hull and unique == [region_id]:
        return "exterior_structural_candidate", "on_union_hull"
    if (not on_hull) and unique == [region_id]:
        return "interior_finished_face_candidate", "inside_union"
    return "ABSTAIN", "ambiguous_face_role"


def inventory_source_walls(
    page: NativePage,
    regions: Sequence[dict[str, Any]],
    fills: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Stable native wall/opening/region inventory, topology-only."""
    receipts = native_finished_face_receipts(page, regions)
    polygons = _candidate_polygons(regions)
    union = unary_union([polygon for _region, polygon in polygons]) if polygons else None
    region_by_id = {region["region_id"]: region for region in regions}

    faces: list[dict[str, Any]] = []
    for item in receipts["item_faces"]:
        parsed = _parse_edge(item["item_id"])
        region = region_by_id.get(item["region_id"])
        midpoint = _edge_midpoint(region, parsed[1]) if parsed and region is not None else None
        path = _path_index_from_segment_ref(item["face_segment_ref"])
        interrupting = [
            fill["closure_id"]
            for fill in fills
            if path is not None and path in (fill.get("native_wall_path_indices") or [])
        ]
        if midpoint is None:
            role, reason = "ABSTAIN", "edge_geometry_missing"
        else:
            role, reason = _face_role(midpoint, item["region_id"], polygons, union)
        faces.append({
            "item_id": item["item_id"],
            "item_kind": item["item_kind"],
            "face_segment_ref": item["face_segment_ref"],
            "native_path_index": path,
            "region_id": item["region_id"],
            "face_role_hypothesis": role,
            "face_role_reason": reason,
            "interrupted_by_opening_ids": interrupting,
            "physical_wall_authenticated": False,
            "finished_face_authenticated": False,
            "topology_only": True,
        })

    openings: list[dict[str, Any]] = []
    for fill in fills:
        host_regions = [
            region["region_id"]
            for region in regions
            if fill["closure_id"] in (region.get("topology_closure_ids") or [])
        ]
        host_faces = [
            face["item_id"]
            for face in faces
            if face["native_path_index"] in (fill.get("native_wall_path_indices") or [])
            and (not host_regions or face["region_id"] in host_regions)
        ]
        openings.append({
            "closure_id": fill["closure_id"],
            "kind": fill.get("kind"),
            "native_opening_word_refs": list(fill.get("native_opening_word_refs") or []),
            "native_opening_path_indices": list(fill.get("native_opening_path_indices") or []),
            "native_wall_path_indices": list(fill.get("native_wall_path_indices") or []),
            "host_region_ids": host_regions,
            "host_face_item_ids": host_faces,
            "host_wall_authenticated": False,
            "physical_opening_authenticated": False,
            "physical_wall": False,
            "door_panel_is_not_wall": True,
            "topology_only": True,
            "retain_source_opening": True,
        })

    locators: list[dict[str, Any]] = []
    for region, _polygon in polygons:
        width, height = bind_polygon_hash_axes(page, region["boundary_polygon_pdf_pts"])
        unresolved: list[str] = []
        if width is None:
            unresolved.append("no_unique_width_hash_chain")
        if height is None:
            unresolved.append("no_unique_height_hash_chain")
        face_ids = [face["item_id"] for face in faces if face["region_id"] == region["region_id"]]
        locators.append({
            "source_sha256": page.source_sha256,
            "page_index": page.page_index,
            "region_id": region["region_id"],
            "room_label_word_refs": [
                word["native_word_ref"] for word in region.get("room_label_words") or []
            ],
            "room_label_texts": [
                word["text"] for word in region.get("room_label_words") or []
            ],
            "finish_word_refs": [
                word["native_word_ref"] for word in region.get("finish_marker_words") or []
            ],
            "boundary_polygon_pdf_pts": region["boundary_polygon_pdf_pts"],
            "wall_face_item_ids": face_ids,
            "opening_closure_ids": list(region.get("topology_closure_ids") or []),
            "outer_length_hash": _hash_payload(width),
            "inner_face_or_plan_height_hash": _hash_payload(height),
            "unresolved": unresolved,
            "room_identity_authenticated": False,
            "physical_zone_authenticated": False,
            "topology_only": True,
        })

    return {
        "source_sha256": page.source_sha256,
        "page_index": page.page_index,
        "faces": faces,
        "face_count": len(faces),
        "openings": openings,
        "opening_count": len(openings),
        "region_locators": locators,
        "region_locator_count": len(locators),
        "topology_face_receipts": receipts,
        "physical_wall_authenticated": False,
        "finished_face_authenticated": False,
        "hosted_opening_authenticated": False,
        "topology_only": True,
        "commercial_publishable": False,
        "benchmark_credit": False,
        "official_score": None,
    }
