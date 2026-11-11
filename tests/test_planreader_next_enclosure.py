"""Executable opening-as-wall topology preview, including the frozen 3Laurel page."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
import subprocess
import sys

import pytest

from planreader_next.enclosure import propose_room_enclosures
from planreader_next.engine import SourceConflict, load_native_page
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
    assert result["virtual_fill_count"] == 39
    assert result["candidate_enclosed_regions"] == 9
    assert result["single_room_shape_hints"] == 4
    assert result["unresolved_regions"] == 2
    assert result["unresolved_wall_gap_count"] == 11
    kinds = {f["kind"] for f in result["virtual_wall_fills"]}
    assert kinds == {
        "swing_doorway", "source_stroke_closure",
        "sliding_leaf_frame_closure", "panel_lift_door_topology_closure",
    }
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
    assert all(not r["room_identity_authenticated"] for r in result["regions"])
    assert result["commercial_publishable"] is False
    assert result["official_score"] is None
    assert "quantities" not in result
