"""Unique jambs and wall-end contact; never a published host or height."""
from __future__ import annotations

import json
import subprocess
import sys

import fitz

from planreader_next.enclosure import propose_room_enclosures
from planreader_next.engine import load_native_page
from planreader_next.opening_hosts import native_face_cut_witnesses
from planreader_next.section_scope import source_section_cut
from tests.original_source_3laurel import ORIGINAL_SHA256, require_original_3laurel
from tests.test_layered_wall_doorway_room_face_wiring_v1 import layered_room_pdf


def test_synthetic_door_hosts_to_unique_jambs_and_wall_ends(tmp_path):
    path = tmp_path / "jamb-door.pdf"
    path.write_bytes(layered_room_pdf(door=True, swing=True, vertical_pairs="full_only"))
    page = load_native_page(path, 0)
    inventory = propose_room_enclosures(page, path)["source_wall_inventory"]
    swing = [item for item in inventory["openings"] if item["kind"] == "swing_doorway"]
    assert swing
    unique = [item for item in swing if item["host_status"] == "UNIQUE"]
    assert unique
    host = unique[0]
    assert host["physical_opening_authenticated"] is False
    assert host["host_wall_authenticated"] is False
    assert len(host["jamb_segment_refs"]) == 2
    assert len(set(host["jamb_segment_refs"])) == 2
    assert len(host["wall_end_segment_refs"]) >= 2
    assert all(face["endpoint_status"] == "UNIQUE" for face in inventory["faces"])
    assert inventory["unique_jamb_hosted_opening_count"] >= 1
    assert inventory["hosted_opening_authenticated"] is False
    assert inventory["commercial_publishable"] is False
    out = tmp_path / "walls.json"
    completed = subprocess.run([
        sys.executable, "-m", "planreader_next", "walls",
        "--pdf", str(path), "--page", "0", "--output", str(out),
    ], capture_output=True, text=True, check=True)
    summary = json.loads(completed.stdout)
    assert summary["unique_jamb_hosted_opening_count"] >= 1
    assert summary["commercial_publishable"] is False


def test_competing_jamb_cap_abstains(tmp_path):
    document = fitz.open(
        stream=layered_room_pdf(door=True, swing=True, vertical_pairs="full_only"),
        filetype="pdf",
    )
    # Second cap on the same wall band at the north jamb station.
    document[0].draw_line((250, 110), (254, 110), color=(0, 0, 0), width=0.4)
    path = tmp_path / "two-jambs.pdf"
    path.write_bytes(document.tobytes())
    document.close()
    page = load_native_page(path, 0)
    inventory = propose_room_enclosures(page, path)["source_wall_inventory"]
    swing = [item for item in inventory["openings"] if item["kind"] == "swing_doorway"]
    assert swing
    assert all(item["host_status"] != "UNIQUE" for item in swing)
    assert all(item["host_wall_authenticated"] is False for item in swing)


def test_section_cut_uses_native_face_ink_not_the_room_polygon(tmp_path):
    path = tmp_path / "cut-face.pdf"
    path.write_bytes(layered_room_pdf(door=True, swing=True, vertical_pairs="full_only"))
    page = load_native_page(path, 0)
    inventory = propose_room_enclosures(page, path)["source_wall_inventory"]
    # Inner west face sits on x=100. A short interior cut at x=140 misses every
    # native face even though it still sits inside the room polygon.
    empty = native_face_cut_witnesses(
        page, inventory["faces"], [140.0, 100.0, 140.0, 160.0],
    )
    assert empty["witness_count"] == 0
    assert empty["commercial_publishable"] is False
    hits = native_face_cut_witnesses(
        page, inventory["faces"], [100.0, 80.0, 100.0, 180.0],
    )
    assert hits["witness_count"] >= 1
    assert all(item["face_segment_ref"] for item in hits["witnesses"])
    assert all(item["physical_wall_authenticated"] is False for item in hits["witnesses"])
    assert all(item["height_applied_to_room"] is False for item in hits["witnesses"])
    west = [
        item for item in hits["witnesses"]
        if item["endpoint_a_pdf_pts"][0] == item["endpoint_b_pdf_pts"][0]
        and abs(item["endpoint_a_pdf_pts"][0] - 100.0) <= 0.35
    ]
    assert west
    assert any(item["cut_intersection_kind"] in {"point", "span"} for item in west)


def test_original_3laurel_jambs_and_aa_cut_stay_unauthenticated():
    original = require_original_3laurel()
    plan = load_native_page(original, 2)
    assert plan.source_sha256 == ORIGINAL_SHA256
    inventory = propose_room_enclosures(plan, original, include_sliding=True)[
        "source_wall_inventory"
    ]
    assert inventory["hosted_opening_authenticated"] is False
    assert inventory["physical_wall_authenticated"] is False
    assert inventory["commercial_publishable"] is False
    assert all(item["host_wall_authenticated"] is False for item in inventory["openings"])
    assert any(item["host_status"] == "UNIQUE" for item in inventory["openings"])
    unique = [item for item in inventory["openings"] if item["host_status"] == "UNIQUE"]
    assert all(len(item["jamb_segment_refs"]) == 2 for item in unique)
    assert all(item["physical_opening_authenticated"] is False for item in unique)
    bed = [
        locator for locator in inventory["region_locators"]
        if locator["room_label_texts"] == ["BED"]
    ]
    assert bed
    assert all(item["room_identity_authenticated"] is False for item in bed)
    section = load_native_page(original, 6)
    cut = source_section_cut(plan, section)
    witnesses = native_face_cut_witnesses(
        plan, inventory["faces"], cut["cut_axis_pdf_pts"],
    )
    assert witnesses["physical_wall_authenticated"] is False
    assert witnesses["height_applied_to_any_room"] is False
    assert witnesses["commercial_publishable"] is False
    assert all(item["face_segment_ref"] for item in witnesses["witnesses"])
    assert all(item["physical_wall_authenticated"] is False for item in witnesses["witnesses"])
    bed_ids = {item["region_id"] for item in bed}
    bed_faces = [
        item for item in inventory["faces"] if item["region_id"] in bed_ids
    ]
    assert bed_faces
    assert all(item["endpoint_status"] in {"UNIQUE", "ABSTAIN"} for item in bed_faces)
