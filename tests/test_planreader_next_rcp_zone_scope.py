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


def _visible_rect(ref: str, bounds):
    # Synthetic ceiling-border ink must actually be drawn/stroked.
    return NativeRectangle(
        ref, bounds, True,
        stroke_present=True, stroke_color=(0.0, 0.0, 0.0),
        stroke_width=1.0,
    )


def _rcp_fixture():
    words = (
        _word("word:b1:l0:w0:i0", "2400", 90, 70),
        _word("word:b1:l1:w0:i1", "GRID", 74, 70),
        _word("word:b2:l0:w0:i2", "3000", 290, 90),
        _word("word:b2:l1:w0:i3", "FPB", 274, 90),
    )
    rectangles = (
        _visible_rect("zone:grid", (60, 40, 160, 150)),
        _visible_rect("zone:fpb", (255, 45, 375, 170)),
        _visible_rect("whole-plan", (0, 0, 500, 300)),
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
    near = _visible_rect("zone:almost-grid", (58, 38, 162, 152))
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
    # Original p141 native rect is a white *fill* with NO stroked border.
    # Previous 13 matches were invisible graphics, never ceiling zones.
    assert len(out["source_zone_rectangle_candidates"]) == 0
    assert len(out["unresolved_callouts"]) == 18
    assert {x["reason_code"] for x in out["unresolved_callouts"]} == {
        "no_source_zone_rectangle_around_rcp_callout"
    }
    white_mask = next(r for r in page.rectangles if r.ref == "rect:p141:i0")
    assert white_mask.stroke_present is False
    assert white_mask.stroke_color is None
    assert white_mask.stroke_width == 0
    # The extractor historically generated four imaginary rect_edge
    # segments around that invisible white fill. Their paint status must
    # remain visible to downstream physical wall/ceiling tracers.
    mask_edges = [
        s for s in page.segments if s.ref.startswith("d141i0e")
    ]
    assert len(mask_edges) == 4
    assert all(s.kind == "rect_edge" and s.stroke_present is False
               and s.stroke_color is None for s in mask_edges)
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
    assert len(data["source_zone_rectangle_candidates"]) == 0
    assert len(data["source_zone_unresolved_callouts"]) == 18
    assert not data["commercial_publishable"]
    second = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    assert second.returncode == 2 and "FileExistsError" in second.stderr


def test_section_cannot_relabel_itself_as_an_rcp_zone(tmp_path):
    import subprocess
    import sys
    from tests.original_source_3laurel import require_original_3laurel

    original = str(require_original_3laurel())
    output = tmp_path / "not-rcp-zone.json"
    cmd = [sys.executable, "-m", "planreader_next", "heights",
           "--drawing-type", "section", "--pdf", original, "--page", "6",
           "--with-source-zone-rectangles", "--output", str(output)]
    root = Path(__file__).resolve().parents[1]
    response = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    assert response.returncode == 2
    assert not output.exists()
    assert "source_zone_rectangles_only_valid_for_rcp" in response.stderr



def test_white_fill_only_rectangle_cannot_claim_rcp_zone():
    """PDF white-background rectangle bbox is NOT actual ceiling boundary."""
    page = _rcp_fixture()
    print_rect = NativeRectangle(
        "white-fake", (60, 40, 160, 150), True,
        stroke_present=False, stroke_color=None, stroke_width=0,
    )
    # Competing fill-only rectangle should be ignored, not turn otherwise
    # unique visible outline into an ambiguous different region.
    page = NativePage(page.source_sha256, page.page_index, page.words,
                      page.rectangles + (print_rect,), page.segments)
    got = propose_rcp_source_zone_rectangles(page)
    assert {x["source_rectangle_ref"] for x in got["source_zone_rectangle_candidates"]} == {
        "zone:grid", "zone:fpb",
    }


def test_only_invisible_rectangles_cannot_claim_a_material_height():
    page = _rcp_fixture()
    invisible = tuple(
        NativeRectangle(
            item.ref, item.bbox, True, stroke_present=False,
            stroke_color=None, stroke_width=0,
        ) for item in page.rectangles
    )
    page = NativePage(page.source_sha256, page.page_index, page.words,
                      invisible, page.segments)
    got = propose_rcp_source_zone_rectangles(page)
    assert got["source_height_material_pairs"] == 2
    assert not got["source_zone_rectangle_candidates"]
    assert len(got["unresolved_callouts"]) == 2


def test_unproven_or_white_stroked_rectangle_cannot_claim_ceiling():
    page = _rcp_fixture()
    invisible = tuple(
        NativeRectangle(
            item.ref, item.bbox, True, stroke_present=True,
            stroke_color=(1.0, 1.0, 1.0), stroke_width=0.5,
        ) for item in page.rectangles
    )
    page = NativePage(page.source_sha256, page.page_index, page.words,
                      invisible, page.segments)
    got = propose_rcp_source_zone_rectangles(page)
    assert not got["source_zone_rectangle_candidates"]
