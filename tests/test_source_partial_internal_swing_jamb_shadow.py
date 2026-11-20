"""Partial source-cubic swing door with a real diagonal radial leaf.

The default swing parser matches full 90-degree arcs. This separate form
requires a genuine partial cubic, a real radial leaf, source printed width,
two distinct white jamb caps and two black painted wall-end hosts.
"""
from copy import deepcopy

import fitz

from pb_source_internal_swing_room_barrier import detect_source_internal_swing_room_barriers


def _scene():
    wall = lambda box, color: {
        "layer": "Enclosure_WallInternal", "type": "f",
        "fill": (color,) * 3, "rect": fitz.Rect(*box),
        "items": (),
    }
    rows = [
        wall((0, 0, 15, 2.5), 0),
        wall((42, 0, 65, 2.5), 0),
        wall((15, -.3, 16.1, 2.8), 1),
        wall((40.9, -.3, 42, 2.8), 1),
        {"layer": "Enclosure_WallInternal", "type": "s",
         "color": (0, 0, 0), "fill": None,
         "rect": fitz.Rect(33.8, 2.8, 40.9, 20.25),
         "items": [("c", fitz.Point(40.9, 2.8),
                    fitz.Point(40.9, 9.33), fitz.Point(38.3, 15.6),
                    fitz.Point(33.8, 20.25))]},
        {"layer": "Enclosure_WallInternal", "type": "s",
         "color": (0, 0, 0), "fill": None,
         "rect": fitz.Rect(16.1, 2.8, 33.8, 20.25),
         "items": [("l", fitz.Point(16.1, 2.8), fitz.Point(33.8, 20.25))]},
    ]
    words = [(20, 0, 32, 8, "870", 0, 0, 0)]
    return rows, words


def test_partial_native_swing_is_a_unique_hosted_room_threshold_not_a_wall():
    rows, words = _scene()
    found = detect_source_internal_swing_room_barriers(rows, words, page_index=2)
    assert len(found) == 1
    r = found[0]
    assert r.swing_arc_path_id == 4
    assert (r.first_host_path_id, r.second_host_path_id) == (0, 1)
    assert r.jamb_cap_path_ids == (2, 3)
    assert r.axis == "h"
    assert not r.physical_wall_authenticated
    assert not r.measurement_authorized


def test_partial_arc_requires_original_width_and_real_radial_leaf():
    rows, words = _scene()
    assert detect_source_internal_swing_room_barriers(rows, (), page_index=2) == ()
    bad = deepcopy(rows)
    bad[5]["layer"] = "Annotation_FloorPlan"
    assert detect_source_internal_swing_room_barriers(bad, words, page_index=2) == ()
    bad = deepcopy(rows)
    bad[5]["items"] = [("l", fitz.Point(5, 20), fitz.Point(33.8, 20.25))]
    assert detect_source_internal_swing_room_barriers(bad, words, page_index=2) == ()


def test_partial_arc_needs_both_native_end_hosts_and_two_white_caps():
    rows, words = _scene()
    for idx in (0, 1, 2, 3):
        bad = deepcopy(rows)
        bad[idx]["layer"] = "Annotation_FloorPlan"
        assert detect_source_internal_swing_room_barriers(bad, words, page_index=2) == ()


def test_ambiguous_second_partial_door_on_identical_jambs_abstains():
    rows, words = _scene()
    rows.append(deepcopy(rows[4]))
    rows.append(deepcopy(rows[5]))
    assert detect_source_internal_swing_room_barriers(rows, words, page_index=2) == ()
