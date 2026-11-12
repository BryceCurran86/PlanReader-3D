"""A120-first ceiling-zone candidates from visibly stroked source ink.

Unstroked white fill rectangles are not walls, ceiling borders or zones.
A material/height bubble is a seed, not a polygon. Same uninterrupted
finish in one stroked ring is one zone; conflicting finishes abstain.
This is not a ceiling m², room identity or customer row.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from shapely.geometry import Point, Polygon

from .engine import NativePage, NativeSegment, SourceConflict, authenticated_pdf_snapshot, confirm_source_snapshot
from .height_evidence import rcp_material_height_callouts
from pb_layered_wall_doorway_room_ring_shadow import _WALL_END_SUPPORT_SPAN


def stroked_source_line_segments(page: NativePage) -> tuple[NativeSegment, ...]:
    """Keep original stroked line ink only. Fill-only rect edges are not borders."""
    return tuple(
        segment for segment in page.segments
        if segment.kind == "line" and segment.stroke_present is True
    )


def _callout_point(page: NativePage, receipt: Mapping[str, Any]) -> Point | None:
    words = {word.ref: word for word in page.words}
    height = words.get(receipt.get("height_word_ref"))
    if height is None:
        return None
    x0, y0, x1, y1 = height.bbox
    return Point((x0 + x1) / 2.0, (y0 + y1) / 2.0)


def _ceiling_topology_region(region: Mapping[str, Any]) -> bool:
    """A ceiling continues over a doorway gap; it does not invent a missing wall.

    Floor rings may abstain on ``open_wall_gap_unresolved``. That same enclosed
    ink is still a topology-only ceiling-zone seed when the only defect is a
    doorway-sized wall interruption. An exterior-leaking field is never a zone.
    """
    if region.get("likely_cavity_pocket"):
        return False
    status = region.get("status")
    if status == "candidate":
        return True
    reasons = tuple(region.get("reason_codes") or ())
    return status == "abstained" and reasons == ("open_wall_gap_unresolved",)


def _ring_blockers(region: Mapping[str, Any]) -> dict[str, Any]:
    """Keep the source ring's ABSTAIN/ownership on the ceiling seed.

    An unclosed doorway ring may seed topology, but it is not a measured
    ceiling, wall identity or customer row.
    """
    reasons = [str(item) for item in (region.get("reason_codes") or ()) if item]
    status = str(region.get("status") or "")
    owners = region.get("edge_owner_ids") or ()
    return {
        "source_ring_status": status,
        "source_ring_reason_codes": reasons,
        "edge_owner_ids": [list(item) for item in owners],
        "bounding_closure_ids": [str(item) for item in (region.get("bounding_closure_ids") or ())],
        "opening_gap_unresolved": "open_wall_gap_unresolved" in reasons,
        "ceiling_measurement_blocked": True,
        "customer_row_blocked": True,
        "physical_room_authenticated": False,
        "physical_wall_identity_authenticated": False,
        "finished_wall_face_authenticated": False,
        "pdf_point_heuristic_only": True,
    }


def bind_callouts_to_stroked_rings(
    page: NativePage,
    regions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Unique callouts inside a source-closed stroked ring, never white-fill boxes."""
    callouts = rcp_material_height_callouts(page)
    abstentions: list[dict[str, str]] = []
    zones: list[dict[str, Any]] = []
    placed: set[str] = set()

    for region in regions:
        if not isinstance(region, Mapping):
            continue
        if not _ceiling_topology_region(region):
            continue
        coords = region.get("boundary_polygon_pdf_pts") or []
        if len(coords) < 3:
            continue
        polygon = Polygon([(float(x), float(y)) for x, y in coords])
        if not polygon.is_valid or polygon.is_empty:
            continue
        hits: list[dict[str, Any]] = []
        for receipt in callouts:
            point = _callout_point(page, receipt)
            if point is None or not polygon.contains(point):
                continue
            hits.append(receipt)
        if not hits:
            continue
        pairs = {(item["height_mm"], item["material_code_candidate"]) for item in hits}
        if len(pairs) != 1:
            abstentions.append({
                "region_id": str(region.get("region_id") or ""),
                "reason_code": "rcp_conflicting_stroked_ring_finishes",
            })
            continue
        height_mm, material = next(iter(pairs))
        for item in hits:
            placed.add(item["height_word_ref"])
        blockers = _ring_blockers(region)
        scope = (
            "ABSTAINED_OPEN_GAP_RING_NOT_MEASURED_CEILING"
            if blockers["opening_gap_unresolved"]
            else "STROKED_RING_NOT_AUTHENTICATED_RCP_ZONE"
        )
        zones.append({
            "source_sha256": page.source_sha256,
            "page_index": page.page_index,
            "region_id": region.get("region_id"),
            "height_mm": height_mm,
            "material_code_candidate": material,
            "height_word_refs": sorted(item["height_word_ref"] for item in hits),
            "material_word_refs": sorted(item["material_word_ref"] for item in hits),
            "wall_source_path_indices": list(region.get("wall_source_path_indices") or []),
            "boundary_polygon_pdf_pts": [list(pt) for pt in coords],
            "connected_same_finish_callout_count": len(hits),
            "source_rectangle_ref": None,
            "white_fill_rectangle_rejected": True,
            "candidate_scope": scope,
            "ceiling_zone_authenticated": False,
            "physical_ceiling_zone_authenticated": False,
            "commercial_publishable": False,
            "benchmark_credit": False,
            "topology_only": True,
            **blockers,
        })

    for receipt in callouts:
        if receipt["height_word_ref"] in placed:
            continue
        abstentions.append({
            "height_word_ref": receipt["height_word_ref"],
            "material_word_ref": receipt["material_word_ref"],
            "reason_code": "rcp_callout_not_inside_stroked_ring",
        })

    return {
        "source_sha256": page.source_sha256,
        "page_index": page.page_index,
        "source_height_material_pairs": len(callouts),
        "stroked_line_segment_count": len(stroked_source_line_segments(page)),
        "source_zone_stroked_candidates": zones,
        "unresolved_callouts": abstentions,
        "white_fill_rectangles_are_not_zones": True,
        "physical_ceiling_zone_authenticated": False,
        "commercial_publishable": False,
        "benchmark_credit": False,
        "official_score": None,
        "wall_end_support_span_pt_heuristic": _WALL_END_SUPPORT_SPAN,
        "pdf_point_heuristic_only": True,
        "physical_wall_identity_authenticated": False,
        "customer_row_blocked": True,
        "ceiling_measurement_blocked": True,
    }


def propose_rcp_stroked_ceiling_zones(
    page: NativePage, pdf_path: str | Path,
) -> dict[str, Any]:
    """Close topology rings from A120 stroked walls, then bind unique callouts."""
    from pb_layered_wall_doorway_room_ring_shadow import (
        _PRIMITIVE_CAP,
        _selected_primitive_count,
        build_layered_wall_doorway_room_rings,
    )

    path = Path(pdf_path)
    digest, source_bytes, identity = authenticated_pdf_snapshot(path)
    if digest != page.source_sha256:
        raise SourceConflict("source_sha256_mismatch")
    import fitz
    with fitz.open(stream=source_bytes, filetype="pdf") as document:
        if page.page_index < 0 or page.page_index >= len(document):
            raise SourceConflict("source_page_mismatch")
        drawings = document[page.page_index].get_drawings()
    confirm_source_snapshot(path, digest, identity)
    if _selected_primitive_count(drawings) > _PRIMITIVE_CAP:
        raise SourceConflict("page_primitive_cap_exceeded")
    result = build_layered_wall_doorway_room_rings(
        drawings,
        source_sha256=page.source_sha256,
        page_index=page.page_index,
        sliding_leaf_frame_closure=True,
        panel_lift_label_closure=True,
        source_words=[
            {"text": word.text, "bbox_pdf_pts": word.bbox, "source_ref": word.ref}
            for word in page.words
        ],
        stroke_pair_wall_faces=True,
        wall_end_stroke_closures=True,
    )
    regions = []
    for ring in result.rings:
        x0, y0, x1, y1 = ring.bbox_pdf_pts
        likely_cavity = min(x1 - x0, y1 - y0) <= 16.0 and ring.area_pt2 < 2000.0
        regions.append({
            "region_id": ring.record_id,
            "status": ring.status.value,
            "reason_codes": list(ring.reason_codes),
            "likely_cavity_pocket": likely_cavity,
            "boundary_polygon_pdf_pts": [list(pt) for pt in ring.polygon_pdf_pts],
            "wall_source_path_indices": list(ring.bounding_wall_path_indices),
            "edge_owner_ids": [list(item) for item in ring.edge_owner_ids],
            "bounding_closure_ids": list(ring.bounding_closure_ids),
        })
    packet = bind_callouts_to_stroked_rings(page, regions)
    packet["stroked_ring_count"] = len(result.rings)
    packet["candidate_stroked_rings"] = sum(
        1 for region in regions
        if region["status"] == "candidate" and not region["likely_cavity_pocket"]
    )
    packet["reason_codes"] = list(result.reason_codes)
    return packet
