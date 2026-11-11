"""Topology-only room enclosures: temporarily fill authenticated door/window gaps.

Reuses the existing producer-owned wall-layer ring authority. A virtual fill
is NEVER a physical wall, floor/ceiling area, door deduction or customer row.
The native source (including the original opening geometry) stays untouched.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
import math

from shapely.geometry import Point, Polygon

from pb_layered_wall_doorway_room_ring_shadow import (
    build_layered_wall_doorway_room_rings,
)
from .engine import NativePage, SourceConflict, _digest

_ROOM_WORDS = frozenset({
    "BED", "BEDROOM", "BATH", "BATHROOM", "ENSUITE", "ENS", "WC", "LAUNDRY",
    "GARAGE", "LIVING", "DINING", "KITCHEN", "KIT", "ENTRY", "MEDIA", "HALL",
    "STUDY", "ROBE", "WIR", "ALFRESCO", "LOUNGE", "PANTRY", "OFFICE", "MASTER",
    "MEALS", "FAMILY",
})
_OPEN_PLAN_WORDS = frozenset({
    "LIVING", "DINING", "KITCHEN", "KIT", "MEALS", "LOUNGE", "FAMILY",
})
_FINISH_WORDS = frozenset({
    "VINYL", "TILES", "CARPET", "CONCRETE", "EPOXY", "TIMBER", "LAMINATE",
    "HYBRID", "TILE", "FT1", "FT2", "FT3", "FT4", "FT5",
})


def _fill_bbox(closure: Any) -> list[float]:
    """Full wall-band footprint temporarily filled across an opening, in PDF pt."""
    lo, hi = closure.gap_interval
    low, high = closure.band
    return (
        [lo, low, hi, high] if closure.horizontal
        else [low, lo, high, hi]
    )


def _inside_words(page: NativePage, polygon: Polygon, tokens: frozenset[str]) -> list[dict[str, str]]:
    found = []
    for word in page.words:
        text = word.text.strip().upper()
        if text not in tokens:
            continue
        x0, y0, x1, y1 = word.bbox
        point = Point((x0 + x1) / 2, (y0 + y1) / 2)
        if polygon.contains(point):
            found.append({"text": text, "native_word_ref": word.ref})
    return found


def propose_room_enclosures(
    page: NativePage, pdf_path: str | Path, *, include_sliding: bool = True,
) -> dict[str, Any]:
    """Candidate room polygons from wall ink plus temporary opening barriers.

    The source PDF is SHA verified against the already extracted NativePage.
    Even a fully closed ring is only a diagrammatic room-boundary suggestion.
    Source window/door geometry is retained verbatim for later measurement.
    """
    path = Path(pdf_path)
    if _digest(path) != page.source_sha256:
        raise SourceConflict("source_sha256_mismatch")
    import fitz

    before = path.stat()
    with fitz.open(path) as document:
        if page.page_index < 0 or page.page_index >= len(document):
            raise SourceConflict("source_page_mismatch")
        drawings = document[page.page_index].get_drawings()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise SourceConflict("source_changed_during_read")
    if len(drawings) > 20000 or len(page.segments) > 20000:
        raise SourceConflict("page_primitive_cap_exceeded")

    result = build_layered_wall_doorway_room_rings(
        drawings,
        source_sha256=page.source_sha256,
        page_index=page.page_index,
        sliding_leaf_frame_closure=include_sliding,
        panel_lift_label_closure=True,
        source_words=[
            {"text": w.text, "bbox_pdf_pts": w.bbox, "source_ref": w.ref}
            for w in page.words
        ],
    )
    virtual_fills = [
        {
            "closure_id": item.closure_id,
            "kind": item.kind,
            "bbox_pdf_pts": _fill_bbox(item),
            "native_opening_path_indices": list(item.native_path_indices),
            "native_wall_path_indices": list(item.wall_path_indices),
            "native_opening_word_refs": list(item.native_word_refs),
            "physical_header_and_jamb_walls_preserved": True,
            "door_panel_is_not_wall": True,
            "physical_wall": False,
            "topology_only": True,
            "retain_source_opening": True,
        }
        for item in result.closures
    ]

    regions = []
    for ring in result.rings:
        polygon = Polygon(ring.polygon_pdf_pts)
        if not polygon.is_valid or polygon.is_empty or not math.isfinite(polygon.area):
            raise SourceConflict("source_ring_geometry_invalid")
        room_words = _inside_words(page, polygon, _ROOM_WORDS)
        finish_words = _inside_words(page, polygon, _FINISH_WORDS)
        distinct_rooms = sorted({word["text"] for word in room_words})
        distinct_finishes = sorted({word["text"] for word in finish_words})
        private_rooms = [name for name in distinct_rooms if name not in _OPEN_PLAN_WORDS]
        open_plan_labels = [name for name in distinct_rooms if name in _OPEN_PLAN_WORDS]
        open_plan_physical_area = bool(open_plan_labels) and not private_rooms
        may_be_single_room = (
            ring.status.value == "candidate"
            and len(distinct_finishes) == 1
            and (len(distinct_rooms) == 1 or open_plan_physical_area)
        )
        x0, y0, x1, y1 = ring.bbox_pdf_pts
        likely_cavity_pocket = (
            not room_words
            and min(x1 - x0, y1 - y0) <= 16.0
            and ring.area_pt2 < 2000.0
        )
        regions.append({
            "region_id": ring.record_id,
            "status": ring.status.value,
            "reason_codes": list(ring.reason_codes),
            "boundary_polygon_pdf_pts": [list(pt) for pt in ring.polygon_pdf_pts],
            "bbox_pdf_pts": list(ring.bbox_pdf_pts),
            "area_pdf_pt2_not_metric": ring.area_pt2,
            "edge_owner_ids": [list(ids) for ids in ring.edge_owner_ids],
            "wall_source_path_indices": list(ring.bounding_wall_path_indices),
            "topology_closure_ids": list(ring.bounding_closure_ids),
            "room_label_words": room_words,
            "finish_marker_words": finish_words,
            "finish_zones": [{"finish": name} for name in distinct_finishes],
            "open_plan_physical_area": open_plan_physical_area,
            "single_room_shape_hint": may_be_single_room and not likely_cavity_pocket,
            "likely_cavity_pocket": likely_cavity_pocket,
            "room_identity_authenticated": False,
            "finished_face_authenticated": False,
            "metric_area_authenticated": False,
            "topology_only": True,
            "review_required": True,
        })

    return {
        "schema_version": "0.3.0",
        "source_sha256": page.source_sha256,
        "page_index": page.page_index,
        "mode": "temporary_wall_fill_at_source_attested_openings",
        "sliding_door_closures_enabled": include_sliding,
        "source_pdf_unchanged": True,
        "original_door_window_geometry_retained": True,
        "virtual_wall_fills": virtual_fills,
        "regions": regions,
        "candidate_enclosed_regions": sum(
            r["status"] == "candidate" and not r["likely_cavity_pocket"] for r in regions
        ),
        "single_room_shape_hints": sum(r["single_room_shape_hint"] for r in regions),
        "unresolved_regions": sum(r["status"] != "candidate" for r in regions),
        "cavity_pocket_regions": sum(r["likely_cavity_pocket"] for r in regions),
        "unresolved_wall_gap_count": result.unresolved_gap_count,
        "wall_strip_count": result.wall_strip_count,
        "wall_gap_count": result.wall_gap_count,
        "virtual_fill_count": len(virtual_fills),
        "cavity_slider_closures": sum(f["kind"] == "cavity_slider_cs_closure" for f in virtual_fills),
        "reason_codes": list(result.reason_codes),
        "draft_floor_candidates": _draft_floors(page, regions),
        "commercial_publishable": False,
        "benchmark_credit": False,
        "official_score": None,
    }


def _draft_floors(page: NativePage, regions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Existing figured-word takeoff against enclosure bboxes. Never a native face proof."""
    from .engine import SourceConflict, _figured_mm

    drafts: list[dict[str, Any]] = []
    for region in regions:
        if region["status"] != "candidate" or not region["single_room_shape_hint"]:
            continue
        if len(region["finish_zones"]) != 1 or not region["finish_marker_words"]:
            continue
        x0, y0, x1, y1 = (float(v) for v in region["bbox_pdf_pts"])
        horizontal, vertical = [], []
        for word in page.words:
            try:
                _figured_mm(word)
            except SourceConflict:
                continue
            cx = (word.bbox[0] + word.bbox[2]) / 2.0
            cy = (word.bbox[1] + word.bbox[3]) / 2.0
            if x0 <= cx <= x1 and (abs(cy - y0) <= 32 or abs(cy - y1) <= 32):
                horizontal.append(word)
            if y0 <= cy <= y1 and (abs(cx - x0) <= 32 or abs(cx - x1) <= 32):
                vertical.append(word)
        if len(horizontal) != 1 or len(vertical) != 1 or horizontal[0].ref == vertical[0].ref:
            continue
        width_mm = _figured_mm(horizontal[0])
        height_mm = _figured_mm(vertical[0])
        labels = sorted({item["text"] for item in region["room_label_words"]})
        drafts.append({
            "region_id": region["region_id"],
            "room_label": " / ".join(labels) if region["open_plan_physical_area"] else labels[0],
            "finish_code": region["finish_zones"][0]["finish"],
            "width_word_ref": horizontal[0].ref,
            "height_word_ref": vertical[0].ref,
            "quantity_m2": format((width_mm * height_mm / 1000000).normalize(), "f"),
            "unit": "m2",
            "boundary_basis": "enclosure_preview_bbox_review_required",
            "status": "MEASURED_DRAFT_REVIEW_REQUIRED",
            "commercial_publishable": False,
            "benchmark_credit": False,
        })
    return drafts
