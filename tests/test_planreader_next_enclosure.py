"""Executable opening-as-wall topology preview, including the frozen 3Laurel page."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
import subprocess
import sys

import pytest

from decimal import Decimal

from planreader_next.enclosure import _draft_floors, propose_room_enclosures
from planreader_next.engine import NativePage, SourceConflict, load_native_page
from planreader_next.hash_chain import bind_polygon_hash_axes, bind_wall_hash_length
from tests.original_source_3laurel import ORIGINAL_SHA256, require_original_3laurel
from tests.test_layered_wall_doorway_room_face_wiring_v1 import layered_room_pdf


def make_synthetic(tmp_path, *, door=True, swing=True):
    path = tmp_path / "synthetic-wall-room.pdf"
    path.write_bytes(layered_room_pdf(door=door, swing=swing))
    return path, load_native_page(path, 0)


def test_authenticated_swing_opening_is_a_temporary_wall_only(tmp_path):
    path, native = make_synthetic(tmp_path)
    before = sha256(path.read_bytes()).hexdigest()
    packet = propose_room_enclosures(native, path)
    assert packet["source_sha256"] == before
    assert packet["source_pdf_unchanged"] is True
    assert packet["original_door_window_geometry_retained"] is True
    assert packet["candidate_enclosed_regions"] == 1
    assert packet["virtual_fill_count"] == 1
    fill = packet["virtual_wall_fills"][0]
    assert fill["kind"] == "swing_doorway"
    assert fill["topology_only"] is True
    assert fill["physical_wall"] is False
    assert fill["retain_source_opening"] is True
    assert len(fill["bbox_pdf_pts"]) == 4
    ring = packet["regions"][0]
    assert ring["topology_closure_ids"] == [fill["closure_id"]]
    assert ring["boundary_polygon_pdf_pts"]
    assert any("layered_doorway_closure:" in owner
               for edge in ring["edge_owner_ids"] for owner in edge)
    assert ring["room_identity_authenticated"] is False
    assert ring["metric_area_authenticated"] is False
    assert packet["commercial_publishable"] is False
    assert packet["benchmark_credit"] is False
    assert packet["official_score"] is None
    assert sha256(path.read_bytes()).hexdigest() == before


def test_unwitnessed_opening_is_not_filled_or_marked_as_room(tmp_path):
    path, native = make_synthetic(tmp_path, door=True, swing=False)
    packet = propose_room_enclosures(native, path)
    assert packet["virtual_fill_count"] == 0
    assert packet["candidate_enclosed_regions"] == 0
    assert packet["unresolved_wall_gap_count"] >= 1


def _draft_region(polygon, *, hole_count=0, bbox=None):
    xs = [pt[0] for pt in polygon]
    ys = [pt[1] for pt in polygon]
    return {
        "region_id": "draft-shape",
        "status": "candidate",
        "single_room_shape_hint": True,
        "finish_zones": [{"finish": "VINYL"}],
        "finish_marker_words": [{"text": "VINYL", "native_word_ref": "word:vinyl"}],
        "room_label_words": [{"text": "BED", "native_word_ref": "word:bed"}],
        "open_plan_physical_area": False,
        "bbox_pdf_pts": bbox or [min(xs), min(ys), max(xs), max(ys)],
        "boundary_polygon_pdf_pts": polygon,
        "hole_count": hole_count,
    }


def test_l_concave_and_holed_faces_do_not_publish_bbox_product_as_floor(monkeypatch):
    from planreader_next.hash_chain import HashBoundLength

    page = NativePage("a" * 64, 0, (), (), ())
    width = HashBoundLength(Decimal("10000"), ("word:w",), (0.0, 100.0), 0.0, "horizontal")
    height = HashBoundLength(Decimal("10000"), ("word:h",), (0.0, 100.0), 0.0, "vertical")
    monkeypatch.setattr(
        "planreader_next.hash_chain.bind_polygon_hash_axes",
        lambda page, coords: (width, height),
    )
    ell = [[0, 0], [100, 0], [100, 50], [50, 50], [50, 100], [0, 100]]
    concave = [[0, 0], [100, 0], [100, 100], [60, 100], [60, 40], [40, 40], [40, 100], [0, 100]]
    rectangle = [[0, 0], [100, 0], [100, 100], [0, 100]]
    assert _draft_floors(page, [_draft_region(ell)]) == []
    assert _draft_floors(page, [_draft_region(concave)]) == []
    assert _draft_floors(page, [_draft_region(rectangle, hole_count=1)]) == []
    drafts = _draft_floors(page, [_draft_region(rectangle)])
    assert len(drafts) == 1
    assert drafts[0]["quantity_m2"] == "100"
    split_edge = [
        [0, 0], [100, 0], [100, 40], [100.01, 40], [100.01, 70], [100, 70],
        [100, 100], [0, 100],
    ]
    split_drafts = _draft_floors(page, [_draft_region(split_edge)])
    assert len(split_drafts) == 1
    assert split_drafts[0]["quantity_m2"] == "100"


def test_open_plan_living_and_kitchen_stay_one_physical_area(tmp_path):
    import fitz

    document = fitz.open()
    page = document.new_page(width=400.0, height=300.0)
    ocg = document.add_ocg("Enclosure_WallInternal", on=True)
    page.draw_rect(fitz.Rect(96, 76, 254, 80), color=None, fill=(0, 0, 0), oc=ocg)
    page.draw_rect(fitz.Rect(96, 180, 254, 184), color=None, fill=(0, 0, 0), oc=ocg)
    page.draw_rect(fitz.Rect(96, 80, 100, 180), color=None, fill=(0, 0, 0), oc=ocg)
    page.draw_rect(fitz.Rect(250, 80, 254, 180), color=None, fill=(0, 0, 0), oc=ocg)
    page.insert_text((120.0, 120.0), "LIVING", fontsize=10.0)
    page.insert_text((180.0, 120.0), "KITCHEN", fontsize=10.0)
    page.insert_text((150.0, 150.0), "VINYL", fontsize=9.0)
    path = tmp_path / "open-plan.pdf"
    path.write_bytes(document.tobytes())
    document.close()
    native = load_native_page(path, 0)
    packet = propose_room_enclosures(native, path)
    assert packet["candidate_enclosed_regions"] == 1
    region = packet["regions"][0]
    assert region["open_plan_physical_area"] is True
    assert set(w["text"] for w in region["room_label_words"]) >= {"LIVING", "KITCHEN"}
    assert region["single_room_shape_hint"] is True


def test_permanent_original_wall_stays_wall_without_fake_closure(tmp_path):
    path, native = make_synthetic(tmp_path, door=False)
    packet = propose_room_enclosures(native, path)
    assert packet["virtual_fill_count"] == 0
    assert packet["candidate_enclosed_regions"] == 1


def test_foreign_or_stale_hash_is_rejected(tmp_path):
    path, native = make_synthetic(tmp_path)
    with pytest.raises(SourceConflict, match="source_sha256_mismatch"):
        propose_room_enclosures(replace(native, source_sha256="0" * 64), path)


def test_suggest_command_includes_enclosure_preview_without_measuring(tmp_path):
    path, _ = make_synthetic(tmp_path)
    out = tmp_path / "source-enclosures.json"
    completed = subprocess.run([
        sys.executable, "-m", "planreader_next", "suggest",
        "--pdf", str(path), "--page", "0", "--project-id", "synthetic",
        "--revision-id", "r1", "--output", str(out), "--with-boundaries",
    ], capture_output=True, text=True, check=True)
    assert json.loads(completed.stdout)["candidate_enclosed_regions"] == 1
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["enclosure_preview"]["virtual_fill_count"] == 1
    # Native rectangles / dimensions are still required for a metric takeoff.
    assert "quantities" not in report
    assert report["enclosure_preview"]["commercial_publishable"] is False
    assert report["enclosure_preview"]["official_score"] is None
    with pytest.raises(subprocess.CalledProcessError):
        subprocess.run([
            sys.executable, "-m", "planreader_next", "boundaries",
            "--pdf", str(path), "--page", "0", "--output", str(out),
        ], capture_output=True, text=True, check=True)


def _plan_plus_section_ffl_fcl(tmp_path):
    import fitz

    document = fitz.open()
    plan = document.new_page(width=200, height=200)
    plan.insert_text((40, 40), "MEDIA", fontsize=10)
    section = document.new_page(width=400, height=300)
    section.draw_line(fitz.Point(120, 70), fitz.Point(120, 210))
    section.insert_text((112, 140), "2700", fontsize=8)
    section.insert_text((128, 68), "FCL", fontsize=7)
    section.insert_text((128, 214), "FFL", fontsize=7)
    section.draw_line(fitz.Point(150, 66), fitz.Point(150, 210))
    section.insert_text((142, 136), "2740", fontsize=8)
    section.insert_text((158, 64), "TP", fontsize=7)
    section.draw_line(fitz.Point(180, 110), fitz.Point(180, 210))
    section.insert_text((172, 158), "2100", fontsize=8)
    path = tmp_path / "plan-plus-section-ffl-fcl.pdf"
    path.write_bytes(document.tobytes())
    document.close()
    return path


def test_plan_page_uses_unique_section_ffl_fcl_as_room_height(tmp_path):
    path = _plan_plus_section_ffl_fcl(tmp_path)
    page = load_native_page(path, 0)
    default = propose_room_enclosures(page, path)
    assert default["room_height_from_ffl_fcl"]["status"] == "CROSS_SHEET_HEIGHT_SOURCE_SCAN_DEFERRED"
    assert default["room_height_from_ffl_fcl"]["height_applied_to_any_room"] is False
    result = propose_room_enclosures(page, path, include_cross_sheet_height=True)
    ceiling = result["room_height_from_ffl_fcl"]
    assert ceiling["status"] == "SECTION_FFL_FCL_REVIEW_REQUIRED"
    assert ceiling["length_mm"] == "2700"
    assert ceiling["source_page_indexes"] == [1]
    assert ceiling["room_height_is_ffl_fcl"] is True
    assert ceiling["plan_axis_is_not_ceiling_height"] is True
    assert ceiling["cut_room_identity_authenticated"] is False
    assert ceiling["applicable_room_ids"] == []
    assert ceiling["applicable_room_scope_authenticated"] is False
    assert ceiling["ceiling_zone_scope_authenticated"] is False
    assert ceiling["height_applied_to_any_room"] is False
    assert ceiling["commercial_publishable"] is False
    assert ceiling["official_score"] is None
    assert result["draft_floor_candidates"] == []
    assert ceiling["length_mm"] != "2740"
    assert ceiling["length_mm"] != "2100"


def test_normal_suggest_stays_fast_without_opt_in(tmp_path):
    path, _ = make_synthetic(tmp_path)
    out = tmp_path / "cursor-fast-path.json"
    completed = subprocess.run([
        sys.executable, "-m", "planreader_next", "suggest",
        "--pdf", str(path), "--page", "0", "--project-id", "synthetic",
        "--revision-id", "r1", "--output", str(out),
    ], capture_output=True, text=True, check=True)
    packet = json.loads(out.read_text(encoding="utf8"))
    assert "enclosure_preview" not in packet
    assert json.loads(completed.stdout)["candidate_enclosed_regions"] == 0


def test_original_3laurel_page3_closes_openings_but_keeps_unresolved_gaps():
    original = require_original_3laurel()
    page = load_native_page(original, 2)
    assert page.source_sha256 == ORIGINAL_SHA256
    result = propose_room_enclosures(page, original, include_sliding=True)
    assert result["virtual_fill_count"] >= 39
    assert result["candidate_enclosed_regions"] >= 9
    assert result["single_room_shape_hints"] >= 4
    assert result["unresolved_regions"] >= 1
    assert result["unresolved_wall_gap_count"] >= 1
    kinds = {f["kind"] for f in result["virtual_wall_fills"]}
    assert {
        "swing_doorway", "source_stroke_closure",
        "sliding_leaf_frame_closure", "panel_lift_door_topology_closure",
    } <= kinds
    cavity = [f for f in result["virtual_wall_fills"] if f["kind"] == "cavity_slider_cs_closure"]
    assert result["cavity_slider_closures"] == len(cavity)
    assert result["cavity_slider_closures"] >= 1
    assert all(f["topology_only"] and not f["physical_wall"] for f in cavity)
    for fill in cavity:
        assert any(str(ref).startswith("word:") for ref in fill["native_opening_word_refs"])
    garage = [r for r in result["regions"]
              if {w["text"] for w in r["room_label_words"]} == {"GARAGE"}
              and {w["text"] for w in r["finish_marker_words"]} == {"CONCRETE"}]
    assert len(garage) == 1
    assert garage[0]["status"] == "candidate"
    panel = [f for f in result["virtual_wall_fills"]
             if f["kind"] == "panel_lift_door_topology_closure"]
    assert len(panel) == 1 and len(panel[0]["native_opening_word_refs"]) == 4
    assert panel[0]["topology_only"] is True
    assert panel[0]["physical_wall"] is False
    assert panel[0]["door_panel_is_not_wall"] is True
    bedrooms = [
        r for r in result["regions"]
        if r["single_room_shape_hint"]
        and {x["text"] for x in r["room_label_words"]} == {"BED"}
        and {x["text"] for x in r["finish_marker_words"]} == {"VINYL"}
    ]
    assert len(bedrooms) == 3
    south_widths = []
    for bedroom in bedrooms:
        width, height = bind_polygon_hash_axes(page, bedroom["boundary_polygon_pdf_pts"])
        if width is not None:
            south_widths.append(width)
        assert height is None
    assert len(south_widths) == 2
    assert all(item.length_mm == Decimal("3010") for item in south_widths)
    assert all(len(item.word_refs) == 2 for item in south_widths)
    media = [
        r for r in result["regions"]
        if r["single_room_shape_hint"]
        and {w["text"] for w in r["room_label_words"]} == {"MEDIA"}
    ]
    assert len(media) == 1
    media_width, media_height = bind_polygon_hash_axes(page, media[0]["boundary_polygon_pdf_pts"])
    assert media_width is not None and media_width.length_mm == Decimal("4210")
    assert len(media_width.word_refs) == 2
    assert media_height is None
    # Party-wall height hashes only carry opening figures (870). Floor m²
    # abstains until a unique height figure owns that internal face.
    # MEDIA south 870 is a CS opening, not the 4210 leftover width.
    assert result["draft_floor_candidates"] == []
    ceiling = result["room_height_from_ffl_fcl"]
    assert ceiling["status"] == "CROSS_SHEET_HEIGHT_SOURCE_SCAN_DEFERRED"
    assert ceiling["length_mm"] is None
    assert ceiling["room_height_is_ffl_fcl"] is False
    assert ceiling["cut_room_identity_authenticated"] is False
    assert ceiling["height_applied_to_any_room"] is False
    assert ceiling["commercial_publishable"] is False
    assert ceiling["official_score"] is None
    # FFL-to-FCL evidence still exists on the real original section page 7;
    # its separate source-owned height test covers the positive path.
    faces = result["topology_face_receipts"]
    assert faces["commercial_publishable"] is False
    assert faces["finished_face_authenticated"] is False
    assert faces["physical_item_authenticated"] is False
    assert faces["topology_only"] is True
    dim_index = result["dimension_index"]
    assert dim_index["commercial_publishable"] is False
    assert dim_index["official_score"] is None
    assert dim_index["role"] == "UNMATCHED"
    assert dim_index["figure_count"] >= 1
    assert all(item["role"] == "UNMATCHED" for item in dim_index["figures"])
    assert all(item["millimetres"] != "870" or item["role"] == "UNMATCHED" for item in dim_index["figures"])
    invented = [
        r for r in result["regions"]
        if r["single_room_shape_hint"]
        and {w["text"] for w in r["room_label_words"]} <= {"LIVING", "KITCHEN", "KIT", "DINING"}
    ]
    assert invented == []
    assert all(not r["room_identity_authenticated"] for r in result["regions"])
    assert result["commercial_publishable"] is False
    assert result["official_score"] is None
    assert "quantities" not in result


def test_original_maryborough_page7_stroke_pairs_stay_topology_only():
    import os
    from pathlib import Path

    from pb_maryborough_customer_authority import MARYBOROUGH_SOURCE_SHA256

    named = os.environ.get("PLANREADER_MARYBOROUGH_ORIGINAL_PDF", "").strip()
    default = Path(__file__).resolve().parents[1] / "documents" / "sources" / "Arch_Combined_Maryborough_Service_Station.pdf"
    original = Path(named) if named else default
    if not original.is_file():
        pytest.skip("ORIGINAL_SOURCE_NOT_RUN: private Maryborough original not provisioned; this is not an original-source pass")
    page = load_native_page(original, 6)
    assert page.source_sha256 == MARYBOROUGH_SOURCE_SHA256
    result = propose_room_enclosures(page, original, stroke_pair_wall_faces=True)
    assert result["commercial_publishable"] is False
    assert result["official_score"] is None
    assert result["benchmark_credit"] is False
    assert "quantities" not in result
    assert result["draft_floor_candidates"] == []
    assert "page_primitive_cap_exceeded" not in result["reason_codes"]
    assert result["dimension_index"]["role"] == "UNMATCHED"
    assert all(not r["room_identity_authenticated"] for r in result["regions"])
    assert all(r["topology_only"] for r in result["regions"])
