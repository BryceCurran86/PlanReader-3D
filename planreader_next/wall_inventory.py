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
from .opening_figures import pair_opening_figures
from .opening_hosts import native_face_cut_witnesses, native_face_endpoints, pair_opening_hosts
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


def _region_polygon(region: dict[str, Any]) -> Polygon | None:
    polygon = Polygon(region.get("boundary_polygon_pdf_pts") or [])
    if not polygon.is_valid or polygon.is_empty:
        return None
    return polygon


def _candidate_polygons(regions: Sequence[dict[str, Any]]) -> list[tuple[dict[str, Any], Polygon]]:
    found: list[tuple[dict[str, Any], Polygon]] = []
    for region in regions:
        if region.get("status") != "candidate" or region.get("likely_cavity_pocket"):
            continue
        polygon = _region_polygon(region)
        if polygon is None:
            continue
        found.append((region, polygon))
    return found


def _open_ring_polygons(regions: Sequence[dict[str, Any]]) -> list[tuple[dict[str, Any], Polygon]]:
    """Abstained rings keep unique hash millimetres. They are not closed locators."""
    found: list[tuple[dict[str, Any], Polygon]] = []
    for region in regions:
        if region.get("status") != "abstained" or region.get("likely_cavity_pocket"):
            continue
        polygon = _region_polygon(region)
        if polygon is None:
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
    *,
    cut_axis_pdf_pts: Sequence[float] | None = None,
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
        ends = native_face_endpoints(page, item["face_segment_ref"])
        faces.append({
            "item_id": item["item_id"],
            "item_kind": item["item_kind"],
            "face_segment_ref": item["face_segment_ref"],
            "native_path_index": path,
            "region_id": item["region_id"],
            "face_role_hypothesis": role,
            "face_role_reason": reason,
            "interrupted_by_opening_ids": interrupting,
            "endpoint_a_pdf_pts": ends["endpoint_a_pdf_pts"],
            "endpoint_b_pdf_pts": ends["endpoint_b_pdf_pts"],
            "endpoint_status": ends["endpoint_status"],
            "physical_wall_authenticated": False,
            "finished_face_authenticated": False,
            "topology_only": True,
        })

    figure_pairs = pair_opening_figures(page, fills)
    pair_by_id = {item["closure_id"]: item for item in figure_pairs}
    host_pairs = pair_opening_hosts(page, fills, faces)
    host_by_id = {item["closure_id"]: item for item in host_pairs}
    reserved_opening_figures = {
        ref
        for item in figure_pairs
        if item["pair_status"] == "UNIQUE"
        for ref in item["paired_figure_word_refs"]
    }

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
        pair = pair_by_id.get(fill["closure_id"], {})
        host = host_by_id.get(fill["closure_id"], {})
        openings.append({
            "closure_id": fill["closure_id"],
            "kind": fill.get("kind"),
            "native_opening_word_refs": list(fill.get("native_opening_word_refs") or []),
            "native_opening_path_indices": list(fill.get("native_opening_path_indices") or []),
            "native_wall_path_indices": list(fill.get("native_wall_path_indices") or []),
            "host_region_ids": host_regions,
            "host_face_item_ids": host_faces,
            "paired_figure_word_refs": list(pair.get("paired_figure_word_refs") or []),
            "paired_length_mm": pair.get("paired_length_mm"),
            "paired_dimension_line_refs": list(pair.get("paired_dimension_line_refs") or []),
            "pair_status": pair.get("pair_status", "NONE"),
            "pair_reason": pair.get("pair_reason", "no_unique_opening_figure"),
            "opening_width_is_not_wall_length": True,
            "jamb_segment_refs": list(host.get("jamb_segment_refs") or []),
            "wall_end_segment_refs": list(host.get("wall_end_segment_refs") or []),
            "jamb_hosted_face_item_ids": list(host.get("jamb_hosted_face_item_ids") or []),
            "jamb_stations_pdf_pts": list(host.get("jamb_stations_pdf_pts") or []),
            "host_status": host.get("host_status", "NONE"),
            "host_reason": host.get("host_reason", "no_unique_jamb_pair"),
            "host_wall_authenticated": False,
            "physical_opening_authenticated": False,
            "physical_wall": False,
            "door_panel_is_not_wall": True,
            "topology_only": True,
            "retain_source_opening": True,
        })

    def _locator_row(region: dict[str, Any]) -> dict[str, Any]:
        width, height = bind_polygon_hash_axes(page, region["boundary_polygon_pdf_pts"])
        width_payload = _hash_payload(width)
        height_payload = _hash_payload(height)
        unresolved: list[str] = []
        if width_payload is None:
            unresolved.append("no_unique_width_hash_chain")
        elif reserved_opening_figures.issuperset(width_payload["word_refs"]):
            width_payload = None
            unresolved.append("opening_figure_reserved")
        if height_payload is None:
            unresolved.append("no_unique_height_hash_chain")
        elif reserved_opening_figures.issuperset(height_payload["word_refs"]):
            height_payload = None
            unresolved.append("opening_figure_reserved")
        if (
            region.get("open_plan_room_label_texts")
            and region.get("private_room_label_texts")
        ):
            unresolved.append("mixed_private_labels_in_open_plan_ring")
        reasons = [str(code) for code in (region.get("reason_codes") or [])]
        if "open_wall_gap_unresolved" in reasons:
            unresolved.append("open_wall_gap_unresolved")
        face_ids = [face["item_id"] for face in faces if face["region_id"] == region["region_id"]]
        return {
            "source_sha256": page.source_sha256,
            "page_index": page.page_index,
            "region_id": region["region_id"],
            "region_status": region.get("status"),
            "region_reason_codes": reasons,
            "room_label_word_refs": [
                word["native_word_ref"] for word in region.get("room_label_words") or []
            ],
            "room_label_texts": [
                word["text"] for word in region.get("room_label_words") or []
            ],
            "open_plan_room_label_texts": list(region.get("open_plan_room_label_texts") or []),
            "private_room_label_texts": list(region.get("private_room_label_texts") or []),
            "finish_word_refs": [
                word["native_word_ref"] for word in region.get("finish_marker_words") or []
            ],
            "boundary_polygon_pdf_pts": region["boundary_polygon_pdf_pts"],
            "wall_face_item_ids": face_ids,
            "opening_closure_ids": list(region.get("topology_closure_ids") or []),
            "outer_length_hash": width_payload,
            "inner_face_or_plan_height_hash": height_payload,
            "unresolved": unresolved,
            "room_identity_authenticated": False,
            "physical_zone_authenticated": False,
            "topology_only": True,
        }

    locators = [_locator_row(region) for region, _polygon in polygons]
    open_rings = []
    for region, _polygon in _open_ring_polygons(regions):
        row = _locator_row(region)
        if row["outer_length_hash"] is None and row["inner_face_or_plan_height_hash"] is None:
            continue
        open_rings.append(row)

    return {
        "source_sha256": page.source_sha256,
        "page_index": page.page_index,
        "faces": faces,
        "face_count": len(faces),
        "openings": openings,
        "opening_count": len(openings),
        "paired_opening_figure_count": sum(item["pair_status"] == "UNIQUE" for item in openings),
        "unique_jamb_hosted_opening_count": sum(item["host_status"] == "UNIQUE" for item in openings),
        "reserved_opening_figure_word_refs": sorted(reserved_opening_figures),
        "native_face_cut_witnesses": (
            native_face_cut_witnesses(page, faces, cut_axis_pdf_pts)
            if cut_axis_pdf_pts is not None else None
        ),
        "region_locators": locators,
        "region_locator_count": len(locators),
        "open_ring_hash_chains": open_rings,
        "open_ring_hash_chain_count": len(open_rings),
        "topology_face_receipts": receipts,
        "physical_wall_authenticated": False,
        "finished_face_authenticated": False,
        "hosted_opening_authenticated": False,
        "topology_only": True,
        "commercial_publishable": False,
        "benchmark_credit": False,
        "official_score": None,
    }
