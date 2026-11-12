"""Maryborough labelled neighbourhoods and unique RCP identity links."""
from __future__ import annotations

import os
from pathlib import Path

from planreader_next.enclosure import _label_viewports, _phrase_labels, propose_room_enclosures
from planreader_next.engine import NativePage, NativeRectangle, NativeSegment, NativeWord, load_native_page
from planreader_next.rcp_room_link import unique_plan_rcp_room_label_links
from pb_maryborough_customer_authority import MARYBOROUGH_SOURCE_SHA256


def _word(ref: str, text: str, x: float, y: float):
    return NativeWord(ref, text, (x, y, x + 20, y + 10))


def test_title_block_office_is_not_a_room_neighbourhood():
    page = NativePage(
        "0" * 64, 0,
        (
            _word("word:b1:l0:w0:i1", "OFFICE", 10, 10),
            _word("word:b1:l0:w0:i2", "LEVEL", 40, 10),
            _word("word:b2:l0:w0:i3", "OFFICE", 200, 200),
        ),
        (), (),
    )
    boxes = _label_viewports(page, margin=8.0)
    assert len(boxes) == 1
    x0, y0, x1, y1 = boxes[0]
    assert x0 <= 200 <= x1 and y0 <= 200 <= y1
    assert not (x0 <= 10 <= x1 and y0 <= 10 <= y1)


def test_wash_up_and_cold_room_phrases_seed_neighbourhoods():
    page = NativePage(
        "0" * 64, 0,
        (
            _word("word:b4:l0:w0:i1", "WASH", 40, 80),
            _word("word:b4:l0:w1:i2", "UP", 40, 50),
            _word("word:b5:l0:w0:i3", "COLD", 200, 80),
            _word("word:b5:l0:w1:i4", "ROOM", 200, 50),
            _word("word:b6:l0:w0:i5", "REFUSE", 40, 200),
        ),
        (), (),
    )
    boxes = _label_viewports(page, margin=8.0)
    assert len(boxes) == 3
    texts = _phrase_labels(page)
    assert {item["text"] for item in texts} == {"WASH UP", "COLD ROOM"}


def test_food_prep_phrase_seeds_a_neighbourhood():
    page = NativePage(
        "0" * 64, 0,
        (
            _word("word:b3:l0:w0:i1", "FOOD", 100, 80),
            _word("word:b3:l0:w0:i2", "PREP", 100, 50),
        ),
        (), (),
    )
    boxes = _label_viewports(page, margin=8.0)
    assert len(boxes) == 1
    x0, y0, x1, y1 = boxes[0]
    assert x0 <= 100 <= x1 and y0 <= 50 <= y1 and y0 <= 80 <= y1


def test_unique_office_label_links_plan_region_to_rcp_zone():
    plan = NativePage(
        "a" * 64, 6,
        (_word("word:b9:l0:w0:i1", "OFFICE", 100, 190),),
        (),
        (NativeSegment("d1i0", "line", 90, 180, 170, 180, True),),
    )
    rcp = NativePage(
        "a" * 64, 8,
        (
            NativeWord("word:b1:l0:w0:i0", "2400", (90, 70, 101, 88)),
            NativeWord("word:b1:l1:w0:i1", "GRID", (74, 70, 85, 88)),
            NativeWord("word:b8:l0:w0:i8", "OFFICE", (100, 80, 120, 90)),
            NativeWord("word:b2:l0:w0:i2", "3000", (290, 90, 301, 108)),
            NativeWord("word:b2:l1:w0:i3", "FPB", (274, 90, 285, 108)),
        ),
        (NativeRectangle("white-mask", (0, 0, 500, 300), True),),
        (),
    )
    enclosure = {
        "source_sha256": plan.source_sha256,
        "page_index": 6,
        "regions": [{
            "region_id": "office-ring",
            "status": "candidate",
            "likely_cavity_pocket": False,
            "room_label_words": [{"text": "OFFICE", "native_word_ref": "word:b9:l0:w0:i1"}],
        }],
    }
    rcp_zones = {
        "source_sha256": rcp.source_sha256,
        "page_index": 8,
        "source_zone_stroked_candidates": [{
            "region_id": "office-grid-ring",
            "height_mm": "2400",
            "material_code_candidate": "GRID",
            "boundary_polygon_pdf_pts": [(60, 40), (160, 40), (160, 150), (60, 150)],
        }],
    }
    packet = unique_plan_rcp_room_label_links(plan, rcp, enclosure, rcp_zones)
    assert packet["link_count"] == 1
    link = packet["links"][0]
    assert link["plan_region_id"] == "office-ring"
    assert link["rcp_source_rectangle_ref"] is None
    assert link["rcp_stroked_region_id"] == "office-grid-ring"
    assert link["rcp_height_mm"] == "2400"
    assert link["physical_ceiling_zone_authenticated"] is False
    assert packet["commercial_publishable"] is False


def test_white_fill_rectangles_do_not_link_plan_rooms():
    plan = NativePage(
        "a" * 64, 6,
        (_word("word:b9:l0:w0:i1", "OFFICE", 100, 190),),
        (), (),
    )
    rcp = NativePage(
        "a" * 64, 8,
        (NativeWord("word:b8:l0:w0:i8", "OFFICE", (100, 80, 120, 90)),),
        (NativeRectangle("white-mask", (0, 0, 500, 300), True),),
        (),
    )
    enclosure = {
        "source_sha256": plan.source_sha256,
        "page_index": 6,
        "regions": [{
            "region_id": "office-ring",
            "status": "candidate",
            "likely_cavity_pocket": False,
            "room_label_words": [{"text": "OFFICE", "native_word_ref": "word:b9:l0:w0:i1"}],
        }],
    }
    packet = unique_plan_rcp_room_label_links(plan, rcp, enclosure)
    assert packet["link_count"] == 0
    assert any(
        item["reason_code"] == "rcp_zone_not_unique_for_room_label"
        for item in packet["abstentions"]
    )


def test_original_maryborough_page7_keeps_topology_rooms_unauthenticated():
    named = os.environ.get("PLANREADER_MARYBOROUGH_ORIGINAL_PDF", "").strip()
    default = Path(__file__).resolve().parents[1] / "documents" / "sources" / "Arch_Combined_Maryborough_Service_Station.pdf"
    original = Path(named) if named else default
    if not original.is_file():
        import pytest
        pytest.skip("ORIGINAL_SOURCE_NOT_RUN: private Maryborough original not provisioned; this is not an original-source pass")
    page = load_native_page(original, 6)
    assert page.source_sha256 == MARYBOROUGH_SOURCE_SHA256
    assert any(item["text"] == "FOOD PREP" for item in _phrase_labels(page))
    boxes = _label_viewports(page)
    assert boxes
    packet = propose_room_enclosures(page, original, stroke_pair_wall_faces=True)
    assert packet["commercial_publishable"] is False
    assert packet["official_score"] is None
    assert "page_primitive_cap_exceeded" not in packet["reason_codes"]
    assert packet["draft_floor_candidates"] == []
    labelled = [
        region for region in packet["regions"]
        if region["status"] == "candidate" and region["room_label_words"]
    ]
    assert all(not region["room_identity_authenticated"] for region in packet["regions"])
    rcp = load_native_page(original, 8)
    links = unique_plan_rcp_room_label_links(page, rcp, packet)
    assert links["commercial_publishable"] is False
    assert links["physical_ceiling_zone_authenticated"] is False
    assert all(not item["physical_room_authenticated"] for item in links["links"])
    assert labelled or links["link_count"] == 0
