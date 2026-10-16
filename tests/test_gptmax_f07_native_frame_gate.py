"""Proof that a native frame census cannot mint viewport/quantity authority."""
from types import SimpleNamespace as NS
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from diag_gptmax_f07_native_frame_gate import (
    SOURCE_ONLY_STATUS, native_frame_gate_audit,
)

FIRST = (0.0, 0.0, 100.0, 100.0)
SECOND = (0.0, 120.0, 100.0, 220.0)


class Page:
    def __init__(self, paths=()):
        self.paths = tuple(paths)

    def get_drawings(self):
        return self.paths


class OriginalF07:
    def __init__(self, frames, *, rejected=(), titles=("ELEVATION 4",)):
        self.frames = list(frames)
        self.rejected = list(rejected)
        self.titles = tuple(titles)

    def calibrate_viewport_layout(self, _page):
        return NS()

    def extract_view_title_anchors(self, _page):
        return [NS(text=t, view_type="elevation", bbox=FIRST) for t in self.titles]

    def extract_vector_frames(self, _page, _cal):
        return list(self.frames)

    def _text_fragments(self, _page):
        return []

    def _frame_candidates_for_title(self, _page, anchor, frames, _cal,
                                    *, anchors):
        assert anchor in anchors
        return list(frames)

    def _rejected_ownership_frame(self, _page, frame, _cal, fragments,
                                  *, view_type):
        assert view_type == "elevation"
        assert fragments == []
        return frame in self.rejected

    def _collapse_nested_band_frames(self, frames):
        return list(frames)

    def _collapse_equivalent_nested_frames(self, frames, _cal):
        return list(frames)


def _assert_unbound(result):
    assert result["status"] == SOURCE_ONLY_STATUS
    for key in ("source_physical_view_correspondence_proven",
                "opening_height_granted", "opening_width_granted",
                "opening_host_granted", "opening_area_granted",
                "opening_count_granted"):
        assert result[key] is False
    assert all(x["native_vector_frame_authentication_granted"] is False
               for x in result["original_titles"])


def test_empty_original_vector_frame_abstains():
    result = native_frame_gate_audit(Page(), segmentation=OriginalF07([]))
    assert result["original_titles"][0]["first_failure_if_not_resolved"] == (
        "no_eligible_native_vector_frame"
    )
    _assert_unbound(result)


def test_native_candidate_presence_is_not_positive_source_authority():
    result = native_frame_gate_audit(
        Page([{"items": [("re", FIRST)], "rect": FIRST,
               "closePath": True}]),
        segmentation=OriginalF07([FIRST]),
    )
    assert result["original_titles"][0]["candidate_stage_counts"] == [1, 1, 1, 1, 1]
    assert result["original_drawing_opcode_counts"] == {"re": 1}
    _assert_unbound(result)


def test_competing_source_frame_candidates_preserved():
    result = native_frame_gate_audit(
        Page(), segmentation=OriginalF07([FIRST, SECOND]),
    )
    assert [x["original_native_frame_bbox"] for x in result[
        "original_titles"][0]["associated_frame_candidates"]] == [
            list(FIRST), list(SECOND),
        ]
    _assert_unbound(result)


def test_native_f07_rejection_preserved():
    result = native_frame_gate_audit(
        Page(), segmentation=OriginalF07([FIRST, SECOND], rejected=[FIRST, SECOND]),
    )
    assert result["original_titles"][0]["first_failure_if_not_resolved"] == (
        "all_original_title_candidate_frames_rejected"
    )
    assert all(x["rejected_by_existing_f07"] for x in result[
        "original_titles"][0]["associated_frame_candidates"])
    _assert_unbound(result)


def test_native_path_opcodes_and_identity_retained():
    result = native_frame_gate_audit(
        Page([
            {"items": [("l", 1, 2), ("l", 3, 4)], "rect": FIRST},
            {"items": [("qu", FIRST)], "rect": SECOND, "closePath": True},
        ]), segmentation=OriginalF07([]),
    )
    assert result["original_drawing_opcode_counts"] == {"l": 2, "qu": 1}
    assert [x["original_get_drawings_path_index"] for x in result[
        "original_native_candidate_path_summaries"]] == [0, 1]
    assert result["original_native_candidate_path_summaries"][1]["closed_flag"]
    _assert_unbound(result)


def test_original_frame_order_not_preferred_as_an_owner():
    a = native_frame_gate_audit(Page(), segmentation=OriginalF07([FIRST, SECOND]))
    b = native_frame_gate_audit(Page(), segmentation=OriginalF07([SECOND, FIRST]))
    assert a["original_titles"][0]["associated_source_frame_count"] == 2
    assert b["original_titles"][0]["associated_source_frame_count"] == 2
    assert a["original_titles"][0]["first_failure_if_not_resolved"] == b[
        "original_titles"][0]["first_failure_if_not_resolved"]
    _assert_unbound(a)
    _assert_unbound(b)


def test_repeat_titles_do_not_publish_viewports():
    result = native_frame_gate_audit(
        Page(), segmentation=OriginalF07([FIRST], titles=("ELEVATION 3", "ELEVATION 4")),
    )
    assert len(result["original_titles"]) == 2
    assert result["original_titles"][0]["source_title_text"] == "ELEVATION 3"
    assert result["original_titles"][1]["source_title_text"] == "ELEVATION 4"
    _assert_unbound(result)
