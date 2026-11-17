"""Fail-closed internal door recovery: source arc+leaf+two real jamb+host ends."""
import fitz

from pb_source_internal_swing_room_barrier import (
    detect_source_internal_swing_room_barriers as detect_internal,
    _source_native_internal_cap_host_pair,
)
from pb_source_internal_door_completeness_shadow import (
    inspect_source_internal_door_completeness as audit,
)
from pb_layered_wall_doorway_room_ring_shadow import _swing_arcs


def _filled(bounds, shade, *, viewport=""):
    return {"layer": "Enclosure_WallInternal", "rect": fitz.Rect(*bounds),
            "type": "f", "fill": (shade,) * 3, "viewport_id": viewport, "items": ()}


def _source_native_door():
    # Synthetic example, not private drawing geometry.
    return [
        _filled((97.8, 7, 99.8, 18.8), 0),
        _filled((97.8, 46.2, 99.8, 59), 0),
        _filled((97.5, 18.8, 100, 20), 1),
        _filled((97.5, 45, 100, 46.2), 1),
        {"layer": "Enclosure_WallInternal", "rect": fitz.Rect(100, 20, 125, 45),
         "type": "s", "fill": None, "color": (0, 0, 0),
         "items": (("c", fitz.Point(125, 20), fitz.Point(125, 33.807),
                    fitz.Point(113.807, 45), fitz.Point(100, 45)),)},
        {"layer": "Enclosure_WallInternal", "rect": fitz.Rect(100, 20, 125, 20),
         "type": "s", "fill": None, "color": (0, 0, 0),
         "items": (("l", fitz.Point(100, 20), fitz.Point(125, 20)),)},
    ]


def test_direct_native_short_stubs_recover_missing_internal_swing():
    rows = _source_native_door()
    matches = detect_internal(rows, page_index=2)
    assert len(matches) == 1
    rec = matches[0]
    assert rec.swing_arc_path_id == 4
    assert (rec.first_host_path_id, rec.second_host_path_id) == (0, 1)
    assert rec.jamb_cap_path_ids == (2, 3)
    assert rec.bounds_pdf_pts == (97.8, 18.8, 99.8, 46.2)
    assert rec.axis == "v"
    assert not rec.physical_wall_authenticated and not rec.measurement_authorized


def test_no_black_wall_end_or_white_jamb_means_no_invented_door():
    # Existing legacy source detector tolerates absent radial leaf; this
    # specifically guards the NEW arc+leaf cap-host fallback.
    for missing in (0, 1, 2, 3, 4):
        rows = _source_native_door()
        rows.pop(missing)
        assert detect_internal(rows) == ()


def test_competing_white_jamb_or_duplicate_swing_arc_fail_closed():
    rows = _source_native_door()
    rows.insert(4, rows[2].copy())
    arcs, _ = _swing_arcs(rows, unlabelled_source_ink=True)
    assert len(arcs) == 1
    assert _source_native_internal_cap_host_pair(rows, arcs[0], page_index=2) is None
    rows = _source_native_door()
    rows.append(rows[4].copy())
    assert detect_internal(rows) == ()


def test_mixed_original_viewports_and_joinery_are_not_native_wall_hosts():
    rows = _source_native_door()
    rows[0]["viewport_id"] = "floor"
    rows[1]["viewport_id"] = "elevation"
    assert detect_internal(rows) == ()
    rows = _source_native_door()
    rows[2]["layer"] = "Interior_Joinery"
    assert detect_internal(rows) == ()


def test_source_cs_labels_are_recorded_without_fabricating_jamb_geometry():
    words = [
        (50, 50, 65, 58, "720", 0, 0, 0),
        (66, 50, 73, 58, "CS", 0, 0, 1),
        (150, 50, 175, 58, "ASW", 0, 0, 2),
        (210, 50, 217, 58, "CS", 0, 0, 3),
    ]
    result = audit([], words, page_index=2)
    assert result.swing_symbol_count == 0
    assert result.cavity_slider_callout_count == 2
    assert [m.label_width_mm for m in result.marks] == [720, None]
    assert all(m.status == "NEEDS_JAMB_WITNESS" for m in result.marks)
    assert not result.measurement_authorized
    assert not result.physical_openings_authenticated


def test_app_door_census_exposes_both_classes_but_never_commercializes_labels():
    words = [(50, 50, 65, 58, "870", 0, 0, 0),
             (66, 50, 73, 58, "CS", 0, 0, 1)]
    review = audit(_source_native_door(), words, page_index=2)
    assert (
        review.swing_symbol_count, review.hosted_swing_count,
        review.unhosted_swing_symbol_count, review.cavity_slider_callout_count,
    ) == (1, 1, 0, 1)
    assert len(review.marks) == 2
    assert review.to_dict()["physical_door_count_is_not_established"] is True
    assert review.to_dict()["measurement_authorized"] is False
