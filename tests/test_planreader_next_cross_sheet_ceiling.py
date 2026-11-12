"""New ceiling issuer source lane: plan geometry on one sheet, RCP finish on another."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import subprocess
import sys

import fitz
import pytest

from planreader_next.engine import SourceConflict, load_native_page
from planreader_next.height_evidence import rcp_material_height_callouts
from planreader_next.rcp_zone_scope import propose_rcp_source_zone_rectangles
from planreader_next.building import measure_building_components
from tests.test_planreader_next_building import proof, get, missing


@pytest.fixture()
def cross_sheet(proof, tmp_path):
    original, old_pages, original_selection = proof
    newer = tmp_path / "three-page-source-with-rcp.pdf"
    doc = fitz.open(original)
    rcp = doc.new_page(width=500, height=500)
    rcp.draw_rect(fitz.Rect(20, 50, 480, 450))
    rcp.draw_rect(fitz.Rect(80, 200, 360, 370))
    # One original native PDF text block containing two adjacent callout
    # lines, matching the actual RCP source contract (not nearby text guess).
    rcp.insert_text((175, 272), "IPF1\n2500", fontsize=11)
    doc.save(newer)
    doc.close()
    pages = {i: load_native_page(newer, i) for i in (0,1,2)}
    selection = deepcopy(original_selection)
    selection["source_sha256"] = pages[0].source_sha256
    assert all(page.source_sha256 == pages[0].source_sha256 for page in pages.values())
    rcp_height = rcp_material_height_callouts(pages[2])
    zones = propose_rcp_source_zone_rectangles(pages[2])
    assert len(rcp_height) == 1, rcp_height
    assert len(zones["source_zone_rectangle_candidates"]) == 1, zones
    zone = zones["source_zone_rectangle_candidates"][0]
    assert zone["material_code_candidate"] == "IPF1"
    assert zone["height_mm"] == "2500"
    ceiling = selection["ceilings"][0]
    ceiling["rcp_page_index"] = 2
    ceiling["rcp_source_rectangle_ref"] = zone["source_rectangle_ref"]
    ceiling["finish_word_ref"] = rcp_height[0]["material_word_ref"]
    ceiling["rcp_height_word_ref"] = rcp_height[0]["height_word_ref"]
    ceiling["rcp_cross_sheet_correspondence_reviewed"] = True
    return newer, pages, selection


def test_two_source_pages_issue_one_review_only_ceiling_area(cross_sheet):
    _, pages, selected = cross_sheet
    output = measure_building_components(pages, selected)
    ceiling = get(output,"ceiling_finish")
    assert ceiling["quantity"] == "13.270425"
    assert ceiling["finish_code"] == "IPF1"
    assert ceiling["page_index"] == 0
    assert ceiling["evidence_refs"]["finish_source_page_index"] == 2
    assert ceiling["evidence_refs"]["rcp_source_rectangle_ref"] == selected["ceilings"][0]["rcp_source_rectangle_ref"]
    assert ceiling["height_policy_basis"] == "SOURCE_RCP_LOCAL_CEILING_ZONE_OVERRIDE"
    assert ceiling["height_mm_source_candidate"] == "2500"
    assert ceiling["height_source_receipt"]["height_source_kind"] == "rcp_material_height_callout"
    assert "height_source_receipt" in ceiling
    assert ceiling["commercial_publishable"] is False
    assert not ceiling["benchmark_credit"]
    assert output["commercial_publishable"] is False
    assert not missing(output,"ceiling_finish")


@pytest.mark.parametrize("change,error", [
    ({"rcp_cross_sheet_correspondence_reviewed": False},"cross_sheet_ceiling_source_or_review_missing"),
    ({"rcp_source_rectangle_ref": "whole-page"},"cross_sheet_ceiling_rcp_zone_not_uniquely_source_owned"),
    ({"rcp_height_word_ref": "not-the-figure"},"cross_sheet_ceiling_height_material_pair_not_unique"),
    ({"finish_word_ref": "not-rcp-material"},"rcp_finish_word_not_owned_by_source_page"),
    ({"height_word_ref": "not-plan-length-axis"},"native_word_receipt_missing"),
    ({"boundary_basis": "floor_area_copy"},"reviewed_surface_boundary_not_confirmed"),
])
def test_cross_sheet_ceiling_refuses_unowned_geometry_finish_or_review(cross_sheet,change,error):
    _, pages, selected = cross_sheet
    selected["ceilings"][0].update(change)
    packet=measure_building_components(pages,selected)
    assert missing(packet,"ceiling_finish")[0]["reason_code"] == error
    assert not any(row["trade"] == "ceiling_finish" for row in packet["quantities"])
    # A bad ceiling claim cannot erase a separately measured floor/door.
    assert get(packet,"floor_finish")["quantity"] == "13.270425"
    assert get(packet,"door_count")["quantity"] == "1"


def test_same_rcp_rectangle_cannot_be_doubly_counted(cross_sheet):
    _, pages, selected = cross_sheet
    duplicate = deepcopy(selected["ceilings"][0])
    duplicate["ceiling_id"] = "ceiling-zone-two"
    # Even if the plan shape is changed independently, the same RCP physical
    # zone cannot authenticate two different ceiling quantity rows.
    selected["ceilings"].append(duplicate)
    with pytest.raises(SourceConflict, match="duplicate_ceiling_rcp_source_zone_claim"):
        measure_building_components(pages,selected)


def test_cross_sheet_rcp_finished_area_cli_loads_all_three_original_pages(cross_sheet,tmp_path):
    pdf, pages, selected = cross_sheet
    path=tmp_path/"reviewed-source-ceiling-selections.json"
    out=tmp_path/"source-reviewed-ceiling.json"
    path.write_text(json.dumps(selected),encoding="utf8")
    command=[
        sys.executable,"-m","planreader_next","takeoff",
        "--pdf",str(pdf),"--selection",str(path),"--output",str(out),
    ]
    root=Path(__file__).resolve().parents[1]
    first=subprocess.run(command,cwd=root,text=True,capture_output=True)
    assert first.returncode == 0, first.stderr
    packet=json.loads(out.read_text(encoding="utf8"))
    assert packet["source_pages"] == [0,1,2]
    assert get(packet,"ceiling_finish")["quantity"] == "13.270425"
    assert get(packet,"ceiling_finish")["height_mm_source_candidate"] == "2500"
    second=subprocess.run(command,cwd=root,text=True,capture_output=True)
    assert second.returncode == 2
    assert "FileExistsError" in second.stderr

def test_existing_single_page_ids_remain_byte_for_byte_identical(proof):
    """Signed draft lineage remains unchanged when new cross-page lane is off."""
    from hashlib import sha256
    _, pages, selection = proof
    output = measure_building_components(pages, selection)
    room = selection["ceilings"][0]
    finish = get(output, "ceiling_finish")
    old_receipts = (
        room["width_word_ref"], room["height_word_ref"],
        room["room_label_word_ref"], room["finish_word_ref"],
    )
    old_trace = "|".join((
        pages[0].source_sha256, "0", room["rectangle_ref"],
        *old_receipts, room["room_id"], "ceiling_finish",
    ))
    assert finish["row_id"] == sha256(old_trace.encode("utf-8")).hexdigest()[:24]
    assert finish["quantity"] == "13.270425"
    assert "finish_source_page_index" not in finish["evidence_refs"]
