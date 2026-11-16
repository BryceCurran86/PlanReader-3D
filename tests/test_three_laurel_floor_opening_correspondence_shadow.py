"""Window and door witnesses annotate uncovered room edges; never commercial."""

from __future__ import annotations

import fitz

from pb_source_window_footprint_continuity import WindowFootprintBridge
from pb_source_swing_door_footprint_continuity import ExteriorSwingDoorFootprintBridge
from pb_source_sliding_door_footprint_continuity import (
    ExteriorSlidingDoorFootprintBridge,
)
from pb_source_garage_door_footprint_continuity import GarageDoorFootprintBridge
from pb_three_laurel_floor_wall_face_correspondence_shadow import (
    build_floor_to_physical_wall_candidate_receipt,
)
from pb_three_laurel_floor_opening_correspondence_shadow import (
    match_source_exterior_openings_to_floor_wall_gaps,
)


def _floor():
    pts = ((100, 100), (200, 100), (200, 180), (100, 180), (100, 100))
    return {
        "layer": "Finish_Floor",
        "type": "f",
        "fill": (1.0, 1.0, 1.0),
        "rect": fitz.Rect(100, 100, 200, 180),
        "items": tuple(
            ("l", fitz.Point(*a), fitz.Point(*b)) for a, b in zip(pts, pts[1:])
        ),
    }


def _wall(bounds, layer="Enclosure_WallExternal"):
    return {
        "layer": layer,
        "fill": (0.0, 0.0, 0.0),
        "rect": fitz.Rect(*bounds),
        "items": (),
        "type": "f",
    }


def _receipt(gap=True, page=2):
    d = [
        _floor(),
        _wall((97, 100, 100, 180)),
        _wall((200, 100, 203, 180)),
        _wall((100, 180, 200, 183)),
    ]
    if gap:
        d += [_wall((100, 97, 135, 100)), _wall((165, 97, 200, 100))]
    else:
        d += [_wall((100, 97, 200, 100))]
    words = [(140, 130, 160, 141, "MEDIA", 0, 0, 0)]
    return build_floor_to_physical_wall_candidate_receipt(
        d, words, "MEDIA", page_index=page, source_sha256="private-original-sha"
    )


def _window(page=2, axis="h", bounds=(135.0, 97.0, 165.0, 100.0)):
    return WindowFootprintBridge(
        left_host_path_id=4,
        right_host_path_id=5,
        marker_path_ids=(8, 9),
        label_text="ASW",
        bounds_pdf_pts=bounds,
        axis=axis,
        page_index=page,
    )


def _swing():
    return ExteriorSwingDoorFootprintBridge(
        first_host_path_id=4,
        second_host_path_id=5,
        swing_arc_path_id=10,
        jamb_cap_path_ids=(11, 12),
        bounds_pdf_pts=(135.0, 97.0, 165.0, 100.0),
        axis="h",
        page_index=2,
    )


def _slider():
    return ExteriorSlidingDoorFootprintBridge(
        first_host_path_id=4,
        second_host_path_id=5,
        jamb_cap_path_ids=(11, 12),
        sliding_track_path_ids=(13, 14),
        label_text="ASD",
        bounds_pdf_pts=(135.0, 97.0, 165.0, 100.0),
        axis="h",
        page_index=2,
    )


def _garage():
    return GarageDoorFootprintBridge(
        start_host_path_id=4,
        end_host_path_id=5,
        jamb_cap_path_ids=(11, 12),
        bounds_pdf_pts=(135.0, 97.0, 165.0, 100.0),
        native_label_words=("panel", "lift", "door"),
        axis="h",
        page_index=2,
    )


def test_fixed_window_closes_room_edge_topology_without_opaque_wall():
    matches = match_source_exterior_openings_to_floor_wall_gaps(
        _receipt(), (_window(),)
    )
    assert len(matches) == 1
    m = matches[0]
    assert m.room_label == "MEDIA"
    assert m.room_side == "north"
    assert m.opening_kind == "fixed_window"
    assert m.passage_role == "closed_room_edge_not_opaque_wall"
    assert m.opening_host_path_ids == (4, 5)
    assert m.opening_source_path_ids == (8, 9)
    assert m.supported_gap_interval_pdf_pts == (135.0, 165.0)
    assert m.supported_gap_length_pdf_pt == 30.0
    assert m.boundary_distance_pdf_pt == 0.0
    assert m.to_dict()["measurement_authorized"] is False
    assert m.physical_wall_authenticated is False


def test_swing_and_slider_are_thresholds_not_solid_walls_or_floor_finish():
    for opening, name in (
        (_swing(), "hinged_swing_door"),
        (_slider(), "asd_sgd_sliding_door"),
        (_garage(), "garage_panel_lift_door"),
    ):
        matches = match_source_exterior_openings_to_floor_wall_gaps(
            _receipt(), (opening,)
        )
        assert len(matches) == 1, opening
        m = matches[0]
        assert m.opening_kind == name
        assert m.passage_role == "doorway_threshold_not_solid_wall"
        assert m.supported_gap_length_pdf_pt == 30.0
        assert m.measurement_authorized is False
        assert m.opening_source_path_ids


def test_wrong_page_wrong_axis_and_nonadjacent_window_do_not_bridge_room():
    assert (
        match_source_exterior_openings_to_floor_wall_gaps(
            _receipt(), (_window(page=3),)
        )
        == ()
    )
    assert (
        match_source_exterior_openings_to_floor_wall_gaps(
            _receipt(), (_window(axis="v"),)
        )
        == ()
    )
    assert (
        match_source_exterior_openings_to_floor_wall_gaps(
            _receipt(), (_window(bounds=(135.0, 91.0, 165.0, 94.0)),)
        )
        == ()
    )
    assert (
        match_source_exterior_openings_to_floor_wall_gaps(
            _receipt(page=-1), (_window(),)
        )
        == ()
    )


def test_present_real_wall_cannot_generate_extra_window_material():
    assert (
        match_source_exterior_openings_to_floor_wall_gaps(
            _receipt(gap=False), (_window(),)
        )
        == ()
    )


def test_far_away_gap_label_wrong_source_does_not_auto_join():
    assert match_source_exterior_openings_to_floor_wall_gaps(
        _receipt(), (_window(bounds=(152.0, 97.0, 182.0, 100.0)),)
    )[0].supported_gap_interval_pdf_pts == (152.0, 165.0)
    assert (
        match_source_exterior_openings_to_floor_wall_gaps(
            _receipt(), (_window(bounds=(175.0, 97.0, 205.0, 100.0)),)
        )
        == ()
    )


def test_competing_window_door_claims_to_one_gap_fail_closed():
    receipt = _receipt()
    assert (
        match_source_exterior_openings_to_floor_wall_gaps(
            receipt, (_window(), _swing())
        )
        == ()
    )
    # Duplicate occurrence of the exact same independent source witness
    # does not manufacture extra supported area.
    assert (
        len(
            match_source_exterior_openings_to_floor_wall_gaps(
                receipt, (_window(), _window())
            )
        )
        == 1
    )


def test_unauthorized_or_untyped_receipts_fail_closed():
    fake = WindowFootprintBridge(
        left_host_path_id=4,
        right_host_path_id=5,
        marker_path_ids=(8, 9),
        label_text="ASW",
        bounds_pdf_pts=(135.0, 97.0, 165.0, 100.0),
        axis="h",
        page_index=2,
        measurement_authorized=True,
    )
    assert match_source_exterior_openings_to_floor_wall_gaps(_receipt(), (fake,)) == ()
    assert (
        match_source_exterior_openings_to_floor_wall_gaps(_receipt(), (object(),)) == ()
    )
