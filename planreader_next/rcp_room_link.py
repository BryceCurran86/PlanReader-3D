"""Unique plan-room label to unique RCP zone, never nearest-text mapping.

A room name that appears once on the plan region and once on the RCP sheet,
inside exactly one source zone rectangle, is an identity match. Competing
same-name labels abstain. This is not a ceiling m² or a reviewed height join.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from shapely.geometry import Point, Polygon

from .engine import NativePage, SourceConflict


def unique_plan_rcp_room_label_links(
    plan: NativePage,
    rcp: NativePage,
    enclosure: Mapping[str, Any],
    rcp_zones: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Link uniquely labelled plan regions to uniquely containing stroked RCP zones.

    White fill-only PDF rectangles are not zones. Connected same-finish
    sections already merged in ``rcp_zones`` stay one physical zone.
    """
    if plan.source_sha256 != rcp.source_sha256:
        raise SourceConflict("plan_rcp_source_sha_mismatch")
    if plan.page_index == rcp.page_index:
        raise SourceConflict("plan_rcp_pages_not_distinct")
    if (
        not isinstance(enclosure, Mapping)
        or enclosure.get("source_sha256") != plan.source_sha256
        or enclosure.get("page_index") != plan.page_index
    ):
        raise SourceConflict("plan_rcp_enclosure_source_mismatch")
    if rcp_zones is None:
        rcp_zones = {}
    if (
        rcp_zones
        and (
            rcp_zones.get("source_sha256") not in (None, rcp.source_sha256)
            or rcp_zones.get("page_index") not in (None, rcp.page_index)
        )
    ):
        raise SourceConflict("plan_rcp_zone_source_mismatch")
    region_labels: dict[str, list[str]] = {}
    for region in enclosure.get("regions") or []:
        if not isinstance(region, Mapping):
            continue
        if region.get("status") != "candidate" or region.get("likely_cavity_pocket"):
            continue
        region_id = region.get("region_id")
        if type(region_id) is not str or not region_id:
            continue
        texts = [
            str(word["text"]).strip().upper()
            for word in region.get("room_label_words") or []
            if isinstance(word, dict) and word.get("text")
        ]
        unique = list(dict.fromkeys(texts))
        if len(unique) == 1:
            region_labels.setdefault(unique[0], []).append(region_id)

    rcp_words: dict[str, list[Any]] = {}
    for word in rcp.words:
        text = word.text.strip().upper()
        if not text:
            continue
        rcp_words.setdefault(text, []).append(word)

    links: list[dict[str, Any]] = []
    abstentions: list[dict[str, str]] = []
    for text, region_ids in region_labels.items():
        if len(region_ids) != 1:
            abstentions.append({
                "room_label_text": text,
                "reason_code": "plan_room_label_not_unique",
            })
            continue
        matches = rcp_words.get(text) or []
        if len(matches) != 1:
            abstentions.append({
                "room_label_text": text,
                "reason_code": "rcp_room_label_not_unique",
            })
            continue
        word = matches[0]
        point = Point(
            (word.bbox[0] + word.bbox[2]) / 2.0,
            (word.bbox[1] + word.bbox[3]) / 2.0,
        )
        containing = []
        for zone in rcp_zones.get("source_zone_stroked_candidates") or []:
            coords = zone.get("boundary_polygon_pdf_pts") or []
            if len(coords) < 3:
                continue
            poly = Polygon([(float(x), float(y)) for x, y in coords])
            if not poly.is_valid or poly.is_empty:
                continue
            if poly.contains(point) or poly.covers(point):
                containing.append(zone)
        if len(containing) != 1:
            abstentions.append({
                "room_label_text": text,
                "reason_code": "rcp_zone_not_unique_for_room_label",
            })
            continue
        zone = containing[0]
        links.append({
            "plan_region_id": region_ids[0],
            "plan_room_label_text": text,
            "rcp_room_label_word_ref": word.ref,
            "rcp_source_rectangle_ref": None,
            "rcp_stroked_region_id": zone.get("region_id"),
            "rcp_height_mm": zone.get("height_mm"),
            "rcp_material_code_candidate": zone.get("material_code_candidate"),
            "physical_room_authenticated": False,
            "physical_ceiling_zone_authenticated": False,
            "cross_sheet_correspondence_reviewed": False,
            "commercial_publishable": False,
            "benchmark_credit": False,
        })
    return {
        "source_sha256": plan.source_sha256,
        "plan_page_index": plan.page_index,
        "rcp_page_index": rcp.page_index,
        "links": links,
        "link_count": len(links),
        "abstentions": abstentions,
        "physical_ceiling_zone_authenticated": False,
        "commercial_publishable": False,
        "benchmark_credit": False,
        "official_score": None,
    }
