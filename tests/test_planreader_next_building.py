"""Native PDF end-to-end draft measurement of walls, ceilings, door leaves and frames.

All source drawings here are independently generated PDFs; no project benchmark
truth, private plans or real customer quantities are part of these tests.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys

import fitz
import pytest

from planreader_next import SourceConflict, load_native_page
from planreader_next.building import measure_building_components


@pytest.fixture()
def proof(tmp_path):
    path = tmp_path / "building-scope-synthetic.pdf"
    doc = fitz.open()
    plan = doc.new_page(width=500, height=500)
    # Reviewed source wall centreline and a separate actual aperture span.
    plan.draw_line(fitz.Point(100, 100), fitz.Point(300, 100))
    plan.draw_line(fitz.Point(160, 100), fitz.Point(206, 100))
    plan.insert_text((185, 93), "4000", fontsize=11)
    plan.insert_text((155, 80), "PAINT", fontsize=11)
    plan.insert_text((183, 144), "D1", fontsize=11)
    # Independently reviewed source ceiling plane (not assumed from floor).
    plan.draw_rect(fitz.Rect(100, 220, 300, 220 + 200 * 3297 / 4025))
    plan.insert_text((183, 215), "4025", fontsize=11)
    plan.insert_text((72, 325), "3297", fontsize=11)
    plan.insert_text((150, 265), "FOOD", fontsize=11)
    plan.insert_text((162, 290), "IPF1", fontsize=11)
    plan.insert_text((162, 308), "FT3", fontsize=11)
    schedule = doc.new_page(width=500, height=500)
    schedule.insert_text((45, 100), "D1", fontsize=11)
    schedule.insert_text((98, 100), "920", fontsize=11)
    schedule.insert_text((155, 100), "2040", fontsize=11)
    schedule.insert_text((215, 100), "FRAME", fontsize=11)
    schedule.insert_text((60, 160), "2400", fontsize=11)
    doc.save(path)
    doc.close()
    pages = {i: load_native_page(path, i) for i in (0, 1)}
    words_plan = {w.text: w.ref for w in pages[0].words}
    words_schedule = {w.text: w.ref for w in pages[1].words}
    native_lines = [seg for seg in pages[0].segments if seg.kind == "line"]
    assert len(native_lines) >= 2
    wall_segment = max(native_lines[:2], key=lambda seg: abs(seg.x2 - seg.x1))
    aperture_segment = min(native_lines[:2], key=lambda seg: abs(seg.x2 - seg.x1))
    selection = {
        "project_id": "generated-building-demo",
        "revision_id": "r1",
        "source_sha256": pages[0].source_sha256,
        "rooms": [{
            "room_id": "room-1", "page_index": 0,
            "rectangle_ref": pages[0].rectangles[0].ref,
            "boundary_basis": "internal_finished_wall_face",
            "width_word_ref": words_plan["4025"],
            "height_word_ref": words_plan["3297"],
            "room_label_word_ref": words_plan["FOOD"],
            "finish_word_ref": words_plan["FT3"],
        }],
        "ceilings": [{
            "ceiling_id": "ceiling-zone-IPF1", "room_id": "room-1", "page_index": 0,
            "rectangle_ref": pages[0].rectangles[0].ref,
            "boundary_basis": "source_owned_ceiling_zone",
            "width_word_ref": words_plan["4025"],
            "height_word_ref": words_plan["3297"],
            "room_label_word_ref": words_plan["FOOD"],
            "finish_word_ref": words_plan["IPF1"],
        }],
        "walls": [{
            "wall_id": "wall-A", "page_index": 0,
            "face_segment_ref": wall_segment.ref,
            "face_basis": "internal_finished_wall_face",
            "length_word_ref": words_plan["4000"],
            "height_source_page_index": 1,
            "height_word_ref": words_schedule["2400"],
            "finish_word_ref": words_plan["PAINT"],
            "deduct_door_ids": ["D1-opening"],
        }],
        "doors": [{
            "door_id": "D1-opening", "host_wall_id": "wall-A",
            "plan_page_index": 0, "schedule_page_index": 1,
            "opening_reviewed": True,
            "opening_segment_ref": aperture_segment.ref,
            "host_wall_length_word_ref": words_plan["4000"],
            "plan_code_word_ref": words_plan["D1"],
            "schedule_code_word_ref": words_schedule["D1"],
            "schedule_width_word_ref": words_schedule["920"],
            "schedule_height_word_ref": words_schedule["2040"],
            "frame_reviewed": True,
            "frame_word_ref": words_schedule["FRAME"],
            "frame_configuration": "three_sided",
        }],
    }
    return path, pages, selection


def get(result, trade):
    items = [row for row in result["quantities"] if row["trade"] == trade]
    assert len(items) == 1, (trade, result)
    return items[0]


def missing(result, family):
    return [x for x in result["abstentions"] if x["family"] == family]


def test_measures_every_requested_family_with_native_source(proof):
    path, pages, selection = proof
    packet = measure_building_components(pages, selection)
    assert packet["abstentions"] == []
    assert packet["commercial_publishable"] is False
    assert packet["official_score"] is None
    assert len(packet["quantities"]) == 9
    assert get(packet, "floor_finish")["quantity"] == "13.270425"
    assert get(packet, "ceiling_finish")["quantity"] == "13.270425"
    assert get(packet, "wall_finish_gross_area")["quantity"] == "9.6"
    assert get(packet, "door_count")["quantity"] == "1"
    assert get(packet, "door_leaf_area")["quantity"] == "1.8768"
    assert get(packet, "wall_finish_net_area")["quantity"] == "7.7232"
    assert get(packet, "door_frame_count")["quantity"] == "1"
    assert get(packet, "door_frame_length")["quantity"] == "5"
    assert all(not q["commercial_publishable"] and not q["benchmark_credit"]
               for q in packet["quantities"])
    assert len({q["row_id"] for q in packet["quantities"]}) == 9
    assert all(q["source_sha256"] == pages[0].source_sha256
               for q in packet["quantities"])


def test_ceiling_requires_own_reviewed_source_zone(proof):
    _, pages, selection = proof
    selection["ceilings"][0]["boundary_basis"] = "floor_area_copy"
    packet = measure_building_components(pages, selection)
    assert missing(packet, "ceiling_finish")[0]["reason_code"] == "reviewed_surface_boundary_not_confirmed"
    assert get(packet, "floor_finish")["quantity"] == "13.270425"


def test_ceiling_finish_from_wrong_area_abstains(proof):
    _, pages, selection = proof
    selection["ceilings"][0]["finish_word_ref"] = selection["walls"][0]["finish_word_ref"]
    packet = measure_building_components(pages, selection)
    assert missing(packet, "ceiling_finish")[0]["reason_code"] == "room_or_finish_not_inside_selected_face"


def test_missing_door_schedule_cannot_create_door_or_net_wall(proof):
    _, pages, selection = proof
    selection["doors"][0]["schedule_width_word_ref"] = "fake:width"
    packet = measure_building_components(pages, selection)
    assert len(missing(packet, "door")) == 1
    assert get(packet, "wall_finish_gross_area")["quantity"] == "9.6"
    assert missing(packet, "wall_finish_net_area")[0]["reason_code"] == "door_opening_source_authority_missing"
    assert not any(row["trade"] in {"door_count", "door_leaf_area", "door_frame_length", "wall_finish_net_area"}
                   for row in packet["quantities"])


def test_unverified_frame_keeps_door_but_refuses_frame(proof):
    _, pages, selection = proof
    selection["doors"][0]["frame_reviewed"] = False
    packet = measure_building_components(pages, selection)
    assert get(packet, "door_count")["quantity"] == "1"
    assert get(packet, "door_leaf_area")["quantity"] == "1.8768"
    assert not any(q["trade"].startswith("door_frame") for q in packet["quantities"])
    assert missing(packet, "door_frame")[0]["reason_code"] == "frame_geometry_not_reviewed"


def test_missing_wall_height_abstains_wall_area_without_default(proof):
    _, pages, selection = proof
    selection["walls"][0]["height_word_ref"] = "unknown"
    selection["walls"][0]["assumed_height_mm"] = 2400
    packet = measure_building_components(pages, selection)
    assert missing(packet, "wall_finish")[0]["reason_code"] == "native_source_word_not_owned_by_page"
    assert not any(q["trade"].startswith("wall_finish") or q["trade"] == "wall_length"
                   for q in packet["quantities"])


def test_four_sided_frame_is_independently_measured(proof):
    _, pages, selection = proof
    selection["doors"][0]["frame_configuration"] = "four_sided"
    packet = measure_building_components(pages, selection)
    assert get(packet, "door_frame_length")["quantity"] == "5.92"


def test_wrong_plan_schedule_door_identity_fails_closed(proof):
    _, pages, selection = proof
    selection["doors"][0]["plan_code_word_ref"] = selection["walls"][0]["finish_word_ref"]
    packet = measure_building_components(pages, selection)
    assert missing(packet, "door")[0]["reason_code"] == "plan_schedule_door_code_mismatch"


def test_disconnected_aperture_not_measured_or_deducted(proof):
    _, pages, selection = proof
    selection["doors"][0]["opening_segment_ref"] = selection["walls"][0]["face_segment_ref"]
    packet = measure_building_components(pages, selection)
    assert missing(packet, "door")[0]["reason_code"] == "door_aperture_not_on_single_authenticated_host_line"
    assert missing(packet, "wall_finish_net_area")[0]["reason_code"] == "door_opening_source_authority_missing"


def test_wall_net_requires_complete_explicit_door_universe(proof):
    _, pages, selection = proof
    selection["walls"][0]["deduct_door_ids"] = []
    packet = measure_building_components(pages, selection)
    assert get(packet, "door_leaf_area")["quantity"] == "1.8768"
    assert missing(packet, "wall_finish_net_area")[0]["reason_code"] == "reviewed_wall_door_universe_incomplete"


def test_door_id_and_physical_aperture_cannot_duplicate(proof):
    _, pages, selection = proof
    selection["doors"].append(dict(selection["doors"][0], door_id="another-physical-id"))
    with pytest.raises(SourceConflict, match="duplicate_physical_door_aperture"):
        measure_building_components(pages, selection)


def test_wall_source_cannot_be_borrowed_from_another_pdf(proof, tmp_path):
    _, pages, selection = proof
    other = fitz.open()
    other.new_page()
    path = tmp_path / "other.pdf"
    other.save(path)
    other.close()
    with pytest.raises(SourceConflict, match="multi_page_source_sha_or_index_conflict"):
        measure_building_components({0: pages[0], 1: load_native_page(path, 0)}, selection)


def test_untrusted_numeric_overrides_do_not_change_measured_values(proof):
    _, pages, selection = proof
    selection["doors"][0].update(width_mm=3000, height_mm=3000, price=10000)
    selection["walls"][0].update(height_mm=9999, net_area_m2=9999)
    selection["ceilings"][0].update(area_m2=8000)
    packet = measure_building_components(pages, selection)
    assert get(packet, "door_leaf_area")["quantity"] == "1.8768"
    assert get(packet, "wall_finish_net_area")["quantity"] == "7.7232"
    assert get(packet, "ceiling_finish")["quantity"] == "13.270425"


def test_cli_takeoff_collects_two_pdf_pages_and_is_create_only(proof, tmp_path):
    path, pages, selection = proof
    selected = tmp_path / "reviewed-building.json"
    output = tmp_path / "building-quantity-draft.json"
    selected.write_text(json.dumps(selection), encoding="utf-8")
    command = [sys.executable, "-m", "planreader_next", "takeoff",
               "--pdf", str(path), "--selection", str(selected), "--output", str(output)]
    root = Path(__file__).resolve().parents[1]
    first = subprocess.run(command, cwd=root, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    produced = json.loads(output.read_text(encoding="utf-8"))
    assert produced["source_pages"] == [0, 1]
    assert get(produced, "wall_length")["quantity"] == "4"
    assert get(produced, "door_frame_length")["quantity"] == "5"
    assert get(produced, "ceiling_finish")["quantity"] == "13.270425"
    second = subprocess.run(command, cwd=root, capture_output=True, text=True)
    assert second.returncode == 2
    assert "FileExistsError" in second.stderr


def test_missing_door_schedule_height_cannot_be_assumed(proof):
    _, pages, selection = proof
    selection["doors"][0].update(schedule_height_word_ref="missing:height",
                                  assumed_height_mm=2100, external=True)
    packet = measure_building_components(pages, selection)
    assert missing(packet, "door")[0]["reason_code"] == "native_source_word_not_owned_by_page"
    assert missing(packet, "wall_finish_net_area")[0]["reason_code"] == "door_opening_source_authority_missing"
    assert not any(row["trade"].startswith("door_frame") for row in packet["quantities"])


def test_ceiling_physical_zone_identity_must_not_be_reused(proof):
    _, pages, selection = proof
    selection["ceilings"].append(deepcopy(selection["ceilings"][0]))
    with pytest.raises(SourceConflict, match="duplicate_ceilings_physical_id"):
        measure_building_components(pages, selection)


def test_wall_receipt_cannot_be_sold_twice_under_new_wall_id(proof):
    _, pages, selection = proof
    second = deepcopy(selection["walls"][0])
    second["wall_id"] = "wall-copy"
    second["deduct_door_ids"] = []
    selection["walls"].append(second)
    with pytest.raises(SourceConflict, match="duplicate_physical_wall_segment"):
        measure_building_components(pages, selection)


def test_frame_schedule_label_from_different_row_does_not_authorize_frame(proof):
    _, pages, selection = proof
    selection["doors"][0]["frame_word_ref"] = selection["walls"][0]["height_word_ref"]
    packet = measure_building_components(pages, selection)
    assert get(packet, "door_count")["quantity"] == "1"
    assert missing(packet, "door_frame")[0]["reason_code"] == "frame_presence_not_verified_from_schedule"


def test_same_ceiling_geometry_cannot_be_sold_under_new_zone_id(proof):
    _, pages, selection = proof
    other = deepcopy(selection["ceilings"][0])
    other["ceiling_id"] = "different-zone-id"
    selection["ceilings"].append(other)
    with pytest.raises(SourceConflict, match="duplicate_ceilings_source_surface"):
        measure_building_components(pages, selection)


def test_same_floor_source_cannot_be_sold_under_new_room_id(proof):
    _, pages, selection = proof
    other = deepcopy(selection["rooms"][0])
    other["room_id"] = "different-room-id"
    selection["rooms"].append(other)
    with pytest.raises(SourceConflict, match="duplicate_rooms_source_surface"):
        measure_building_components(pages, selection)


def test_generic_door_word_is_not_a_numbered_schedule_identity(proof):
    # Independent lexical gate: a "DOOR" note is not numbered D1.
    from dataclasses import replace

    _, pages, selection = proof
    altered = {
        index: replace(
            page,
            words=tuple(replace(w, text="DOOR") if w.text == "D1" else w
                        for w in page.words),
        )
        for index, page in pages.items()
    }
    packet = measure_building_components(altered, selection)
    assert missing(packet, "door")[0]["reason_code"] == "door_code_not_source_identified"
    assert missing(packet, "door_frame")[0]["reason_code"] == "door_source_authority_missing"
    assert missing(packet, "wall_finish_net_area")[0]["reason_code"] == "door_opening_source_authority_missing"
    assert not any(q["trade"] in {"door_count", "door_frame_count", "door_frame_length"}
                   for q in packet["quantities"])

def _section_height_extended_proof(pages, selection):
    """Synthetic cross-sheet 2400 FFL-FCL extension on reviewed wall fixture."""
    from planreader_next.engine import NativePage, NativeWord, NativeSegment
    from planreader_next.height_evidence import section_ffl_fcl_heights

    second = pages[1]
    height_word_ref = selection["walls"][0]["height_word_ref"]
    height_word = next(w for w in second.words if w.ref == height_word_ref)
    hx = (height_word.bbox[0]+height_word.bbox[2])/2
    sections = NativePage(
        second.source_sha256, second.page_index,
        second.words + (
            NativeWord("w:FFL:section","FFL",(hx-9,199,hx+2,207)),
            NativeWord("w:FCL:section","FCL",(hx-9,101,hx+2,109)),
        ),
        second.rectangles,
        second.segments + (
            NativeSegment("dimline:height","line",hx,105,hx,204),
        ),
    )
    new_pages = dict(pages)
    new_pages[1] = sections
    candidates=section_ffl_fcl_heights(sections)
    assert len(candidates)==1
    assert candidates[0]["height_word_ref"]==height_word_ref
    return new_pages,candidates[0]


def test_section_ffl_fcl_height_receipt_binds_only_reviewed_wall_draft(proof):
    _,pages,selection=proof
    pages,receipt=_section_height_extended_proof(pages,selection)
    row=selection["walls"][0]
    row["height_source_receipt"]=receipt
    row["height_applies_to_wall_reviewed"]=True
    packet=measure_building_components(pages,selection)
    gross=get(packet,"wall_finish_gross_area")
    assert gross["quantity"]=="9.6"
    assert gross["evidence_refs"]["height_source_kind"]=="ffl_to_fcl_section"
    assert gross["evidence_refs"]["height_dimension_segment_refs"]==("dimline:height",)
    assert gross["commercial_publishable"] is False


def test_wall_height_source_receipt_requires_actual_scope_and_no_injected_override(proof):
    _,pages,selection=proof
    pages,receipt=_section_height_extended_proof(pages,selection)
    row=selection["walls"][0]
    row["height_source_receipt"]=receipt
    row["assumed_height_mm"]=2100
    packet=measure_building_components(pages,selection)
    assert missing(packet,"wall_finish")[0]["reason_code"]=="wall_height_scope_not_reviewed"
    assert not any(r["trade"]=="wall_finish_gross_area" for r in packet["quantities"])
    row["height_applies_to_wall_reviewed"]=True
    row["height_source_receipt"]=dict(receipt,height_mm="2740")
    packet=measure_building_components(pages,selection)
    assert missing(packet,"wall_finish")[0]["reason_code"]=="height_receipt_value_mismatch"
    assert get(packet,"door_count")["quantity"]=="1"


def test_ceiling_height_callout_is_separate_optional_metadata_never_area_override(proof):
    from planreader_next.engine import NativePage, NativeWord
    from planreader_next.height_evidence import rcp_material_height_callouts

    _,pages,selection=proof
    original=pages[0]
    old_ref=selection["ceilings"][0]["finish_word_ref"]
    finish=next(w for w in original.words if w.ref==old_ref)
    new_finish=NativeWord("word:b700:l0:w0:i700","IPF1",finish.bbox)
    x0,y0,x1,y1=finish.bbox
    new_height=NativeWord("word:b700:l1:w0:i701","2400",(x0,y0+17,x1,y1+17))
    room_words=tuple(new_finish if w.ref==old_ref else w for w in original.words)
    amended=NativePage(
        original.source_sha256,original.page_index,
        room_words+(new_height,),original.rectangles,original.segments,
    )
    updated=dict(pages)
    updated[0]=amended
    receipt=rcp_material_height_callouts(amended)
    assert len(receipt)==1
    selection["ceilings"][0]["finish_word_ref"]=new_finish.ref
    selection["ceilings"][0]["height_source_receipt"]=receipt[0]
    selection["ceilings"][0]["height_ceiling_zone_reviewed"]=True
    output=measure_building_components(updated,selection)
    ceiling=get(output,"ceiling_finish")
    assert ceiling["quantity"]=="13.270425"
    assert ceiling["height_mm_source_candidate"]=="2400"
    assert ceiling["height_material_word_ref"]==new_finish.ref
    assert ceiling["commercial_publishable"] is False
    selection["ceilings"][0]["height_source_receipt"]=dict(receipt[0],height_mm="2740")
    output=measure_building_components(updated,selection)
    assert get(output,"ceiling_finish")["quantity"]=="13.270425"
    assert "height_mm_source_candidate" not in get(output,"ceiling_finish")
    assert missing(output,"ceiling_height")[0]["reason_code"]=="height_receipt_value_mismatch"
