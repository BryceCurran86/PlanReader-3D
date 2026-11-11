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
from planreader_next.hash_chain import bind_wall_hash_length
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
        "planreader_next.hash_chain.bind_room_hash_axes",
        lambda page, bbox: (width, height),
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
        x0, _y0, x1, y1 = (float(v) for v in bedroom["bbox_pdf_pts"])
        bound = bind_wall_hash_length(
            page, horizontal_wall=True, face_perp=y1, lo=x0, hi=x1, outward=1.0,
        )
        if bound is not None:
            south_widths.append(bound)
    assert len(south_widths) == 2
    assert all(item.length_mm == Decimal("3010") for item in south_widths)
    assert all(len(item.word_refs) == 2 for item in south_widths)
    assert all(not r["room_identity_authenticated"] for r in result["regions"])
    assert result["commercial_publishable"] is False
    assert result["official_score"] is None
    assert "quantities" not in result
