"""Topology-only wall/opening/region inventory; never a published quantity."""
from __future__ import annotations

from decimal import Decimal
import json
import subprocess
import sys

from planreader_next.enclosure import propose_room_enclosures
from planreader_next.engine import load_native_page
from planreader_next.hash_chain import bind_polygon_hash_axes
from tests.original_source_3laurel import ORIGINAL_SHA256, require_original_3laurel
from tests.test_layered_wall_doorway_room_face_wiring_v1 import layered_room_pdf


def test_synthetic_inventory_keeps_fills_off_the_wall_list(tmp_path):
    path = tmp_path / "layered-walls.pdf"
    path.write_bytes(layered_room_pdf(door=True, swing=True, vertical_pairs="full_only"))
    page = load_native_page(path, 0)
    packet = propose_room_enclosures(page, path)
    inventory = packet["source_wall_inventory"]
    assert inventory["commercial_publishable"] is False
    assert inventory["official_score"] is None
    assert inventory["topology_only"] is True
    assert inventory["physical_wall_authenticated"] is False
    assert inventory["hosted_opening_authenticated"] is False
    assert inventory["face_count"] == packet["topology_face_receipts"]["receipt_count"]
    assert inventory["opening_count"] == packet["virtual_fill_count"] >= 1
    assert all(not opening["physical_wall"] for opening in inventory["openings"])
    assert all(opening["door_panel_is_not_wall"] for opening in inventory["openings"])
    face_ids = {face["item_id"] for face in inventory["faces"]}
    for fill in packet["virtual_wall_fills"]:
        assert fill["kind"] != "room_finished_face"
    assert inventory["region_locator_count"] >= 1
    locator = inventory["region_locators"][0]
    assert locator["room_identity_authenticated"] is False
    assert locator["physical_zone_authenticated"] is False
    assert set(locator["wall_face_item_ids"]) <= face_ids
    out = tmp_path / "walls.json"
    completed = subprocess.run([
        sys.executable, "-m", "planreader_next", "walls",
        "--pdf", str(path), "--page", "0", "--output", str(out),
    ], capture_output=True, text=True, check=True)
    summary = json.loads(completed.stdout)
    assert summary["face_count"] == inventory["face_count"]
    assert summary["commercial_publishable"] is False
    second = subprocess.run([
        sys.executable, "-m", "planreader_next", "walls",
        "--pdf", str(path), "--page", "0", "--output", str(out),
    ], capture_output=True, text=True)
    assert second.returncode == 2


def test_original_3laurel_page3_inventory_is_not_authenticated_walls():
    original = require_original_3laurel()
    page = load_native_page(original, 2)
    assert page.source_sha256 == ORIGINAL_SHA256
    packet = propose_room_enclosures(page, original, include_sliding=True)
    inventory = packet["source_wall_inventory"]
    assert inventory["commercial_publishable"] is False
    assert inventory["official_score"] is None
    assert inventory["topology_only"] is True
    assert inventory["physical_wall_authenticated"] is False
    assert inventory["finished_face_authenticated"] is False
    assert inventory["hosted_opening_authenticated"] is False
    assert inventory["face_count"] == packet["topology_face_receipts"]["receipt_count"]
    assert inventory["face_count"] >= 1
    assert all(not face["physical_wall_authenticated"] for face in inventory["faces"])
    media = [
        locator for locator in inventory["region_locators"]
        if locator["room_label_texts"] == ["MEDIA"]
    ]
    assert len(media) == 1
    assert media[0]["room_identity_authenticated"] is False
    assert "no_unique_height_hash_chain" in media[0]["unresolved"]
    width = media[0]["outer_length_hash"]
    assert width is not None and width["length_mm"] == "4210"
    region = next(
        region for region in packet["regions"]
        if region["region_id"] == media[0]["region_id"]
    )
    bound_width, bound_height = bind_polygon_hash_axes(page, region["boundary_polygon_pdf_pts"])
    assert bound_width is not None and bound_width.length_mm == Decimal("4210")
    assert bound_height is None
    assert inventory["opening_count"] == packet["virtual_fill_count"]
    assert any(opening["native_wall_path_indices"] for opening in inventory["openings"])
    assert any(opening["native_opening_word_refs"] for opening in inventory["openings"])
    garage = [
        locator for locator in inventory["region_locators"]
        if locator["room_label_texts"] == ["GARAGE"]
    ]
    assert len(garage) <= 1
    if garage:
        assert garage[0]["room_identity_authenticated"] is False
        assert garage[0]["physical_zone_authenticated"] is False
