"""A120 ceiling zones come from stroked ink, never unstroked white fills."""
from __future__ import annotations

import os
from pathlib import Path

from planreader_next.engine import NativePage, NativeRectangle, NativeSegment, NativeWord, load_native_page
from planreader_next.rcp_stroked_zones import (
    bind_callouts_to_stroked_rings,
    propose_rcp_stroked_ceiling_zones,
    stroked_source_line_segments,
)
from pb_maryborough_customer_authority import MARYBOROUGH_SOURCE_SHA256


def _word(ref: str, text: str, x: float, y: float):
    return NativeWord(ref, text, (x, y, x + 11, y + 18))


def test_unstroked_rect_edges_are_not_ceiling_borders():
    page = NativePage(
        "a" * 64, 8,
        (_word("word:b1:l0:w0:i0", "2400", 90, 70), _word("word:b1:l1:w0:i1", "GRID", 74, 70)),
        (NativeRectangle("white-fill", (0, 0, 400, 300), True),),
        (
            NativeSegment("d141i0e0", "rect_edge", 0, 0, 400, 0, False),
            NativeSegment("d10i0", "line", 80, 40, 160, 40, True),
        ),
    )
    assert [item.ref for item in stroked_source_line_segments(page)] == ["d10i0"]


def test_unique_callout_inside_stroked_ring_is_topology_only():
    page = NativePage(
        "a" * 64, 8,
        (
            _word("word:b1:l0:w0:i0", "2400", 100, 100),
            _word("word:b1:l1:w0:i1", "GRID", 84, 100),
        ),
        (NativeRectangle("white-fill", (0, 0, 500, 400), True),),
        (NativeSegment("d10i0", "line", 50, 50, 200, 50, True),),
    )
    regions = [{
        "region_id": "office-grid",
        "status": "candidate",
        "likely_cavity_pocket": False,
        "boundary_polygon_pdf_pts": [(60, 60), (180, 60), (180, 160), (60, 160)],
        "wall_source_path_indices": [10],
    }]
    packet = bind_callouts_to_stroked_rings(page, regions)
    assert packet["source_height_material_pairs"] == 1
    assert packet["commercial_publishable"] is False
    assert packet["white_fill_rectangles_are_not_zones"] is True
    assert len(packet["source_zone_stroked_candidates"]) == 1
    zone = packet["source_zone_stroked_candidates"][0]
    assert zone["material_code_candidate"] == "GRID"
    assert zone["height_mm"] == "2400"
    assert zone["source_rectangle_ref"] is None
    assert zone["ceiling_zone_authenticated"] is False
    assert zone["connected_same_finish_callout_count"] == 1


def test_same_finish_callouts_in_one_ring_merge_as_connected_sections():
    page = NativePage(
        "a" * 64, 8,
        (
            _word("word:b10:l0:w0:i0", "3000", 90, 90),
            _word("word:b10:l1:w0:i1", "FPB", 74, 90),
            _word("word:b11:l0:w0:i2", "3000", 140, 110),
            _word("word:b11:l1:w0:i3", "FPB", 124, 110),
        ),
        (),
        (),
    )
    regions = [{
        "region_id": "open-fpb",
        "status": "candidate",
        "likely_cavity_pocket": False,
        "boundary_polygon_pdf_pts": [(50, 50), (200, 50), (200, 180), (50, 180)],
        "wall_source_path_indices": [1, 2, 3],
    }]
    packet = bind_callouts_to_stroked_rings(page, regions)
    assert len(packet["source_zone_stroked_candidates"]) == 1
    zone = packet["source_zone_stroked_candidates"][0]
    assert zone["connected_same_finish_callout_count"] == 2
    assert zone["material_code_candidate"] == "FPB"


def test_doorway_open_gap_ring_is_still_a_ceiling_zone_seed():
    page = NativePage(
        "a" * 64, 8,
        (
            _word("word:b1:l0:w0:i0", "2400", 100, 100),
            _word("word:b1:l1:w0:i1", "GRID", 84, 100),
        ),
        (),
        (),
    )
    regions = [{
        "region_id": "office-grid",
        "status": "abstained",
        "reason_codes": ["open_wall_gap_unresolved"],
        "likely_cavity_pocket": False,
        "boundary_polygon_pdf_pts": [(60, 60), (180, 60), (180, 160), (60, 160)],
        "wall_source_path_indices": [10, 11, 12],
    }]
    packet = bind_callouts_to_stroked_rings(page, regions)
    assert len(packet["source_zone_stroked_candidates"]) == 1
    zone = packet["source_zone_stroked_candidates"][0]
    assert zone["material_code_candidate"] == "GRID"
    assert zone["height_mm"] == "2400"
    assert zone["ceiling_zone_authenticated"] is False
    assert zone["commercial_publishable"] is False


def test_exterior_leaking_open_plan_with_conflicting_finishes_does_not_invent_a_wall():
    page = NativePage(
        "a" * 64, 8,
        (
            _word("word:b10:l0:w0:i0", "3000", 90, 90),
            _word("word:b10:l1:w0:i1", "FPB", 74, 90),
            _word("word:b11:l0:w0:i2", "3000", 240, 110),
            _word("word:b11:l1:w0:i3", "GRID", 224, 110),
        ),
        (),
        (),
    )
    regions = [{
        "region_id": "sales-ocean",
        "status": "abstained",
        "reason_codes": ["open_wall_gap_unresolved"],
        "likely_cavity_pocket": False,
        "boundary_polygon_pdf_pts": [(50, 50), (400, 50), (400, 180), (50, 180)],
        "wall_source_path_indices": [1],
    }]
    packet = bind_callouts_to_stroked_rings(page, regions)
    assert packet["source_zone_stroked_candidates"] == []
    assert any(
        item["reason_code"] == "rcp_conflicting_stroked_ring_finishes"
        for item in packet["unresolved_callouts"]
    )


def test_conflicting_finishes_in_one_ring_abstain():
    page = NativePage(
        "a" * 64, 8,
        (
            _word("word:b1:l0:w0:i0", "2400", 90, 90),
            _word("word:b1:l1:w0:i1", "GRID", 74, 90),
            _word("word:b2:l0:w0:i2", "3000", 140, 110),
            _word("word:b2:l1:w0:i3", "FPB", 124, 110),
        ),
        (),
        (),
    )
    regions = [{
        "region_id": "mixed",
        "status": "candidate",
        "likely_cavity_pocket": False,
        "boundary_polygon_pdf_pts": [(50, 50), (200, 50), (200, 180), (50, 180)],
        "wall_source_path_indices": [1],
    }]
    packet = bind_callouts_to_stroked_rings(page, regions)
    assert packet["source_zone_stroked_candidates"] == []
    assert any(
        item["reason_code"] == "rcp_conflicting_stroked_ring_finishes"
        for item in packet["unresolved_callouts"]
    )


def test_original_maryborough_a120_keeps_callouts_and_rejects_white_fills():
    named = os.environ.get("PLANREADER_MARYBOROUGH_ORIGINAL_PDF", "").strip()
    default = Path(__file__).resolve().parents[1] / "documents" / "sources" / "Arch_Combined_Maryborough_Service_Station.pdf"
    original = Path(named) if named else default
    if not original.is_file():
        import pytest
        pytest.skip("ORIGINAL_SOURCE_NOT_RUN: private Maryborough original not provisioned; this is not an original-source pass")
    page = load_native_page(original, 8)
    assert page.source_sha256 == MARYBOROUGH_SOURCE_SHA256
    packet = propose_rcp_stroked_ceiling_zones(page, original)
    assert packet["source_height_material_pairs"] == 18
    assert packet["commercial_publishable"] is False
    assert packet["physical_ceiling_zone_authenticated"] is False
    assert packet["white_fill_rectangles_are_not_zones"] is True
    assert all(zone["source_rectangle_ref"] is None for zone in packet["source_zone_stroked_candidates"])
    assert all(not zone["ceiling_zone_authenticated"] for zone in packet["source_zone_stroked_candidates"])
    assert packet["stroked_line_segment_count"] > 0
    assert any(
        segment.kind == "rect_edge" and segment.stroke_present is False
        for segment in page.segments
    )
    office = [
        zone for zone in packet["source_zone_stroked_candidates"]
        if zone["material_code_candidate"] == "GRID" and zone["height_mm"] == "2400"
    ]
    assert len(office) == 1
    assert office[0]["source_rectangle_ref"] is None
    assert office[0]["ceiling_zone_authenticated"] is False
    sales = [
        zone for zone in packet["source_zone_stroked_candidates"]
        if zone["material_code_candidate"] == "GRID" and zone["height_mm"] == "3000"
    ]
    assert sales == []
    kitchen = [
        zone for zone in packet["source_zone_stroked_candidates"]
        if zone["material_code_candidate"] == "FPB" and zone["height_mm"] == "3000"
        and zone["connected_same_finish_callout_count"] >= 3
    ]
    assert len(kitchen) == 1
    xs = [pt[0] for pt in kitchen[0]["boundary_polygon_pdf_pts"]]
    ys = [pt[1] for pt in kitchen[0]["boundary_polygon_pdf_pts"]]
    assert max(ys) < 1550.0
    assert any(
        item.get("reason_code") == "rcp_conflicting_stroked_ring_finishes"
        for item in packet["unresolved_callouts"]
    )
