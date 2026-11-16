"""On-demand review is original-page scoped, host-owned and never customer data."""
from __future__ import annotations

import fitz

from pb_source_room_opening_review import (
    printed_room_names,
    review_source_room_opening_gaps,
)
from pb_source_window_footprint_continuity import WindowFootprintBridge


def _wall(bounds):
    return {
        "layer": "Enclosure_WallExternal",
        "fill": (0.0, 0.0, 0.0),
        "rect": fitz.Rect(*bounds),
        "items": (),
        "type": "f",
    }


def _page():
    pts = ((100, 100), (200, 100), (200, 180), (100, 180), (100, 100))
    floor = {
        "layer": "Finish_Floor",
        "fill": (1., 1., 1.),
        "rect": fitz.Rect(100, 100, 200, 180),
        "items": tuple(
            ("l", fitz.Point(*a), fitz.Point(*b))
            for a, b in zip(pts, pts[1:])
        ),
        "type": "f",
    }
    drawings = [
        floor,
        _wall((97, 100, 100, 180)),
        _wall((200, 100, 203, 180)),
        _wall((100, 180, 200, 183)),
        _wall((100, 97, 135, 100)),
        _wall((165, 97, 200, 100)),
    ]
    words = [(140, 130, 160, 141, "MEDIA", 0, 0, 0)]
    source_window = WindowFootprintBridge(
        left_host_path_id=4, right_host_path_id=5,
        marker_path_ids=(8, 9), label_text="ASW",
        bounds_pdf_pts=(135., 97., 165., 100.),
        axis="h", page_index=2,
    )
    return drawings, words, source_window


def test_printed_room_names_only_read_native_tokens_not_geometry():
    native_words = [
        (0, 0, 10, 10, "BED", 0, 0, 0),
        (12, 0, 20, 10, "2", 0, 0, 1),
        (0, 20, 30, 30, "LIVING", 0, 1, 0),
        (100, 0, 120, 10, "BED", 3, 0, 0),
        (200, 0, 220, 10, "4", 4, 0, 0),
    ]
    assert printed_room_names(native_words) == ("BED 2", "LIVING", "BED")


def test_read_only_review_reuses_hosted_window_on_original_page():
    drawings, words, window = _page()
    review = review_source_room_opening_gaps(
        drawings, words, (window,),
        page_index=2, source_sha256="a"*64,
    )
    assert review.status == "CANDIDATE"
    assert review.labels_checked == 1
    assert review.floor_candidates == 1
    assert len(review.witnesses) == 1
    witness = review.witnesses[0]
    assert witness.opening_host_path_ids == (4, 5)
    assert witness.room_label == "MEDIA"
    assert witness.passage_role == "closed_room_edge_not_opaque_wall"
    assert review.physical_wall_authenticated is False
    assert review.measurement_authorized is False
    assert review.to_dict()["measurement_authorized"] is False


def test_wrong_page_foreign_hosts_and_invalid_digest_cannot_admit_opening():
    drawings, words, window = _page()
    from dataclasses import replace
    for candidate in (
        replace(window, page_index=1),
        replace(window, left_host_path_id=90, right_host_path_id=91),
    ):
        report = review_source_room_opening_gaps(
            drawings, words, (candidate,),
            page_index=2, source_sha256="b"*64,
        )
        assert report.witnesses == ()
        assert report.measurement_authorized is False
    invalid = review_source_room_opening_gaps(
        drawings, words, (window,),
        page_index=2, source_sha256="wrong-digest",
    )
    assert invalid.reason == "original_source_scope_invalid"
    assert invalid.witnesses == ()


def test_label_budget_abstains_without_partial_room_output():
    drawings, words, window = _page()
    result = review_source_room_opening_gaps(
        drawings, words, (window,),
        page_index=2, source_sha256="a"*64,
        max_labels=0,
    )
    assert result.witnesses == ()
    assert result.reason == "native_room_label_budget_exceeded"



def test_one_window_claimed_by_two_printed_labels_is_unassigned():
    drawings, words, window = _page()
    # Two section labels within the same source floor shape do not create
    # two rooms or duplicate one source window as two physical openings.
    words = [*words, (110, 140, 135, 150, "LIVING", 0, 1, 0)]
    review = review_source_room_opening_gaps(
        drawings, words, (window,),
        page_index=2, source_sha256="a"*64,
    )
    assert review.labels_checked == 2
    assert review.floor_candidates == 2
    assert review.witnesses == ()
    assert review.ambiguous_opening_count == 1
    assert review.measurement_authorized is False
    assert review.to_dict()["ambiguous_opening_count"] == 1


def test_duplicate_same_source_window_receipt_is_not_double_counted():
    drawings, words, window = _page()
    review = review_source_room_opening_gaps(
        drawings, words, (window, window),
        page_index=2, source_sha256="a"*64,
    )
    assert len(review.witnesses) == 1
    assert review.ambiguous_opening_count == 0



def test_existing_hosted_internal_swing_is_threshold_not_floor_material():
    from pb_source_internal_swing_room_barrier import SourceInternalSwingRoomBarrier
    drawings, words, _ = _page()
    internal = SourceInternalSwingRoomBarrier(
        first_host_path_id=4, second_host_path_id=5,
        swing_arc_path_id=10, jamb_cap_path_ids=(11, 12),
        bounds_pdf_pts=(135.0, 97.0, 165.0, 100.0),
        axis="h", page_index=2,
    )
    review = review_source_room_opening_gaps(
        drawings, words, (internal,), page_index=2, source_sha256="a"*64,
    )
    assert len(review.witnesses) == 1
    assert review.witnesses[0].opening_kind == "internal_hinged_swing_door"
    assert review.witnesses[0].passage_role == "doorway_threshold_not_solid_wall"
    assert review.measurement_authorized is False



def test_shared_native_floor_outline_is_not_split_into_fake_room_counts():
    drawings, words, window = _page()
    words = [*words, (110, 140, 135, 150, "LIVING", 0, 1, 0)]
    report = review_source_room_opening_gaps(
        drawings,words,(window,),page_index=2,source_sha256="a"*64,
    )
    assert report.shared_source_floor_outline_labels == (
        (0, ("MEDIA", "LIVING")),
    )
    assert report.room_gap_audits == ()
    assert report.ambiguous_opening_count == 1
    assert not report.measurement_authorized


def test_unique_room_outline_reports_gap_free_candidate_without_approval():
    drawings, words, window = _page()
    report = review_source_room_opening_gaps(
        drawings,words,(window,),page_index=2,source_sha256="a"*64,
    )
    assert len(report.room_gap_audits) == 1
    gaps = report.room_gap_audits[0]
    assert gaps.room_label == "MEDIA"
    assert gaps.zero_gap_candidate
    assert gaps.remaining_unproved_pdf_pt == 0.
    assert not gaps.room_enclosure_authenticated
    assert not gaps.measurement_authorized
    assert report.to_dict()["room_gap_audits"][0]["measurement_authorized"] is False



def test_read_only_room_review_exposes_native_painted_corner_candidates():
    drawings, words, window = _page()
    review = review_source_room_opening_gaps(
        drawings, words, (window,), page_index=2, source_sha256="a"*64,
    )
    assert len(review.painted_corner_reviews) == 1
    corners = review.painted_corner_reviews[0]
    assert corners.source_floor_path_id == 0
    assert corners.expected_corner_count == 4
    assert len(corners.observed_corners) == 4
    assert not corners.measurement_authorized
    assert not corners.physical_room_authenticated
    assert review.to_dict()["painted_corner_reviews"][0]["measurement_authorized"] is False


def test_shared_source_outline_does_not_emit_separate_corner_certificates():
    drawings, words, window = _page()
    words = [*words, (110, 140, 135, 150, "LIVING", 0, 1, 0)]
    review = review_source_room_opening_gaps(
        drawings, words, (window,), page_index=2, source_sha256="a"*64,
    )
    assert review.shared_source_floor_outline_labels
    assert review.painted_corner_reviews == ()
    assert review.measurement_authorized is False
