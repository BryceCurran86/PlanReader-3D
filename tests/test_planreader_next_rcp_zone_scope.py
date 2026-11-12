"""Original source ceiling bubble-to-rectangle match stays a review candidate."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import pytest

from planreader_next.engine import NativePage, NativeRectangle, NativeSegment, NativeWord, SourceConflict, load_native_page
from planreader_next.rcp_zone_scope import (
    propose_rcp_source_zone_rectangles,
    associate_reviewed_rcp_zone_with_plan_face,
)


def _word(ref: str, text: str, x: float, y: float):
    return NativeWord(ref, text, (x, y, x + 11, y + 18))


def _rcp_fixture():
    words = (
        _word("word:b1:l0:w0:i0", "2400", 90, 70),
        _word("word:b1:l1:w0:i1", "GRID", 74, 70),
        _word("word:b2:l0:w0:i2", "3000", 290, 90),
        _word("word:b2:l1:w0:i3", "FPB", 274, 90),
    )
    rectangles = (
        NativeRectangle("zone:grid", (60, 40, 160, 150), True),
        NativeRectangle("zone:fpb", (255, 45, 375, 170), True),
        NativeRectangle("whole-plan", (0, 0, 500, 300), True),
    )
    return NativePage("a" * 64, 8, words, rectangles, ())


def _plan_fixture(sha="a"*64):
    return NativePage(
        sha, 6,
        (_word("room-word", "OFFICE", 100, 190),),
        (), (NativeSegment("wall-face", "line", 90, 180, 170, 180),),
    )


def test_two_distinct_rcp_height_material_bubbles_link_to_two_source_rectangles():
    result = propose_rcp_source_zone_rectangles(_rcp_fixture())
    assert result["source_height_material_pairs"] == 2
    assert not result["unresolved_callouts"]
    assert {(x["source_rectangle_ref"], x["height_mm"], x["material_code_candidate"])
            for x in result["source_zone_rectangle_candidates"]} == {
        ("zone:grid", "2400", "GRID"),
        ("zone:fpb", "3000", "FPB"),
    }
    assert all(not x["ceiling_zone_authenticated"] and not x["commercial_publishable"]
               for x in result["source_zone_rectangle_candidates"])


def test_same_original_source_cross_sheet_link_needs_reviewer_and_does_not_authenticate():
    plan, rcp = _plan_fixture(), _rcp_fixture()
    chosen = {
        "source_rectangle_ref": "zone:grid",
        "height_word_ref": "word:b1:l0:w0:i0",
        "item_id": "OFFICE-ceiling",
        "plan_face_segment_ref": "wall-face",
        "plan_room_label_word_ref": "room-word",
    }
    with pytest.raises(SourceConflict, match="cross_sheet_room_zone_correspondence_not_reviewed"):
        associate_reviewed_rcp_zone_with_plan_face(
            plan, rcp, **chosen, cross_sheet_correspondence_reviewed=False,
        )
    linked = associate_reviewed_rcp_zone_with_plan_face(
        plan, rcp, **chosen, cross_sheet_correspondence_reviewed=True,
    )
    assert linked["height_mm"] == "2400"
    assert linked["ceiling_material_code_candidate"] == "GRID"
    assert linked["rcp_source_rectangle_ref"] == "zone:grid"
    assert linked["plan_face_segment_ref"] == "wall-face"
    assert linked["cross_sheet_correspondence_reviewed"]
    assert not linked["physical_ceiling_zone_authenticated"]
    assert not linked["physical_wall_role_authenticated"]
    assert not linked["wall_finish_to_fcl_authenticated"]
    assert not linked["commercial_publishable"]


def test_unowned_cross_sheet_plan_face_or_wrong_original_digest_rejected():
    plan, rcp = _plan_fixture(), _rcp_fixture()
    args = dict(
        source_rectangle_ref="zone:grid",
        height_word_ref="word:b1:l0:w0:i0",
        item_id="OFFICE-ceiling",
        plan_face_segment_ref="wrong-face",
        plan_room_label_word_ref="room-word",
        cross_sheet_correspondence_reviewed=True,
    )
    with pytest.raises(SourceConflict, match="plan_face_source_segment_invalid"):
        associate_reviewed_rcp_zone_with_plan_face(plan, rcp, **args)
    args["plan_face_segment_ref"] = "wall-face"
    with pytest.raises(SourceConflict, match="cross_sheet_height_source_sha_mismatch"):
        associate_reviewed_rcp_zone_with_plan_face(
            _plan_fixture("c"*64), rcp, **args,
        )


def test_near_duplicate_source_rectangle_is_ambiguous():
    page = _rcp_fixture()
    near = NativeRectangle("zone:almost-grid", (58, 38, 162, 152), True)
    page = NativePage(page.source_sha256, page.page_index,
                      page.words, page.rectangles + (near,), page.segments)
    r = propose_rcp_source_zone_rectangles(page)
    assert {x["source_rectangle_ref"] for x in r["source_zone_rectangle_candidates"]} == {"zone:fpb"}
    assert {"height_word_ref": "word:b1:l0:w0:i0",
            "reason_code": "rcp_overlapping_rectangles_ambiguous"} in r["unresolved_callouts"]


def test_conflicting_height_material_bubbles_in_same_original_rectangle_abstain():
    p = _rcp_fixture()
    conflicting = (
        _word("word:b3:l0:w0:i4", "3000", 94, 118),
        _word("word:b3:l1:w0:i5", "FPB", 78, 118),
    )
    p = NativePage(p.source_sha256, p.page_index, p.words + conflicting,
                   p.rectangles, p.segments)
    r = propose_rcp_source_zone_rectangles(p)
    assert {x["source_rectangle_ref"] for x in r["source_zone_rectangle_candidates"]} == {"zone:fpb"}
    assert sum(x["reason_code"] == "rcp_conflicting_bubbles_in_candidate_zone"
               for x in r["unresolved_callouts"]) == 2


def test_real_maryborough_rcp_geometry_grouping_if_original_provisioned():
    import os
    original = os.environ.get("PLANREADER_MARYBOROUGH_ORIGINAL_PDF")
    if not original or not Path(original).is_file():
        pytest.skip("ORIGINAL_SOURCE_NOT_RUN")
    page = load_native_page(Path(original), 8)
    assert page.source_sha256 == "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
    out = propose_rcp_source_zone_rectangles(page)
    assert out["source_height_material_pairs"] == 18
    assert len(out["source_zone_rectangle_candidates"]) == 13
    assert len(out["unresolved_callouts"]) == 1
    assert any(x["height_mm"] == "2400" and x["material_code_candidate"] == "GRID"
               for x in out["source_zone_rectangle_candidates"])
    assert any(x["height_mm"] == "3000" and x["material_code_candidate"] == "FPB"
               for x in out["source_zone_rectangle_candidates"])
    assert not out["commercial_publishable"] and out["official_score"] is None


def test_real_rcp_zone_cli_optin_is_create_only(tmp_path):
    import json
    import os
    import subprocess
    import sys

    original = os.environ.get("PLANREADER_MARYBOROUGH_ORIGINAL_PDF")
    if not original or not Path(original).is_file():
        pytest.skip("ORIGINAL_SOURCE_NOT_RUN")
    output = tmp_path / "height-and-source-rectangle-candidates.json"
    cmd = [sys.executable, "-m", "planreader_next", "heights",
           "--drawing-type", "rcp", "--pdf", original, "--page", "8",
           "--with-source-zone-rectangles", "--output", str(output)]
    root = Path(__file__).resolve().parents[1]
    first = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    data = json.loads(output.read_text(encoding="utf8"))
    assert len(data["height_evidence"]) == 18
    assert len(data["source_zone_rectangle_candidates"]) == 13
    assert len(data["source_zone_unresolved_callouts"]) == 1
    assert not data["commercial_publishable"]
    second = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    assert second.returncode == 2 and "FileExistsError" in second.stderr


def test_section_cannot_relabel_itself_as_an_rcp_zone(tmp_path):
    import os
    import subprocess
    import sys

    original = os.environ.get("PLANREADER_3LAUREL_ORIGINAL_PDF")
    if not original or not Path(original).is_file():
        pytest.skip("ORIGINAL_SOURCE_NOT_RUN")
    output = tmp_path / "not-rcp-zone.json"
    cmd = [sys.executable, "-m", "planreader_next", "heights",
           "--drawing-type", "section", "--pdf", original, "--page", "6",
           "--with-source-zone-rectangles", "--output", str(output)]
    root = Path(__file__).resolve().parents[1]
    response = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    assert response.returncode == 2
    assert not output.exists()
    assert "source_zone_rectangles_only_valid_for_rcp" in response.stderr
