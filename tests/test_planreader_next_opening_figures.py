"""A figure inside a door swing belongs to that opening, not the host wall."""
from __future__ import annotations

from decimal import Decimal

import fitz

from planreader_next.dimension_index import clear_dimension_index_cache
from planreader_next.enclosure import propose_room_enclosures
from planreader_next.engine import load_native_page
from tests.original_source_3laurel import ORIGINAL_SHA256, require_original_3laurel
from tests.test_layered_wall_doorway_room_face_wiring_v1 import layered_room_pdf


def _with_width_in_swing(tmp_path, millimetres="820"):
    document = fitz.open(stream=layered_room_pdf(door=True, swing=True, vertical_pairs="full_only"), filetype="pdf")
    # Swing occupies x 226..250, y 110..134 on the synthetic east door.
    document[0].insert_text((232, 122), millimetres, fontsize=8)
    path = tmp_path / "swing-width.pdf"
    path.write_bytes(document.tobytes())
    document.close()
    return path


def test_figure_inside_swing_pairs_to_the_opening_not_the_wall(tmp_path):
    clear_dimension_index_cache()
    path = _with_width_in_swing(tmp_path)
    page = load_native_page(path, 0)
    inventory = propose_room_enclosures(page, path)["source_wall_inventory"]
    paired = [item for item in inventory["openings"] if item["pair_status"] == "UNIQUE"]
    assert len(paired) == 1
    assert paired[0]["paired_length_mm"] == "820"
    assert paired[0]["opening_width_is_not_wall_length"] is True
    assert paired[0]["physical_wall"] is False
    assert paired[0]["host_face_item_ids"] or paired[0]["native_wall_path_indices"]
    assert inventory["reserved_opening_figure_word_refs"]
    locator = inventory["region_locators"][0]
    wall_refs = set((locator["outer_length_hash"] or {}).get("word_refs") or ())
    wall_refs |= set((locator["inner_face_or_plan_height_hash"] or {}).get("word_refs") or ())
    assert not wall_refs.intersection(inventory["reserved_opening_figure_word_refs"])
    assert locator["outer_length_hash"] is None or locator["outer_length_hash"]["length_mm"] != "820"
    assert all(item["paired_length_mm"] != "3600" for item in paired)
    assert all(item["paired_length_mm"] != "2400" for item in paired)
    assert inventory["commercial_publishable"] is False


def test_two_conflicting_figures_in_one_swing_abstain(tmp_path):
    clear_dimension_index_cache()
    document = fitz.open(stream=layered_room_pdf(door=True, swing=True, vertical_pairs="full_only"), filetype="pdf")
    document[0].insert_text((232, 118), "820", fontsize=8)
    document[0].insert_text((236, 128), "920", fontsize=8)
    path = tmp_path / "swing-conflict.pdf"
    path.write_bytes(document.tobytes())
    document.close()
    page = load_native_page(path, 0)
    inventory = propose_room_enclosures(page, path)["source_wall_inventory"]
    swing = [item for item in inventory["openings"] if item["kind"] == "swing_doorway"]
    assert swing
    assert all(item["pair_status"] == "ABSTAIN" for item in swing)
    assert all(item["paired_length_mm"] is None for item in swing)


def test_original_3laurel_opening_figures_do_not_steal_media_wall():
    clear_dimension_index_cache()
    original = require_original_3laurel()
    page = load_native_page(original, 2)
    assert page.source_sha256 == ORIGINAL_SHA256
    inventory = propose_room_enclosures(page, original, include_sliding=True)["source_wall_inventory"]
    paired = [item for item in inventory["openings"] if item["pair_status"] == "UNIQUE"]
    assert paired
    millimetres = {item["paired_length_mm"] for item in paired}
    assert "4210" not in millimetres
    media = [
        locator for locator in inventory["region_locators"]
        if locator["room_label_texts"] == ["MEDIA"]
    ]
    assert len(media) == 1
    assert media[0]["outer_length_hash"] is not None
    assert media[0]["outer_length_hash"]["length_mm"] == "4210"
    wall_refs = set(media[0]["outer_length_hash"]["word_refs"])
    assert not wall_refs.intersection(inventory["reserved_opening_figure_word_refs"])
    assert all(item["opening_width_is_not_wall_length"] for item in inventory["openings"])
    assert all(not item["physical_wall"] for item in paired)
    assert inventory["commercial_publishable"] is False
    assert any(item["paired_length_mm"] == "870" for item in paired)
