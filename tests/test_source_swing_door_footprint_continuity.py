"""Original-native hosted swing door: topology yes, solid material no."""

import fitz
from pb_source_swing_door_footprint_continuity import (
    detect_exterior_swing_door_footprint_bridges as detect,
)

LAYER = "Enclosure_WallExternal"


def wall(bounds, layer=LAYER, fill=0):
    return {
        "layer": layer,
        "rect": fitz.Rect(*bounds),
        "fill": (fill, fill, fill),
        "items": (),
    }


def arc(points, layer=LAYER):
    return {
        "layer": layer,
        "rect": fitz.Rect(
            min(p[0] for p in points),
            min(p[1] for p in points),
            max(p[0] for p in points),
            max(p[1] for p in points),
        ),
        "fill": None,
        "items": (("c", *(fitz.Point(*p) for p in points)),),
    }


def horizontal():
    return [
        wall((0, 20, 5, 22.5)),
        wall((30, 20, 35, 22.5)),
        arc(((5.85, -3.6), (18.7, -3.6), (29.15, 6.85), (29.15, 19.7))),
        wall((5, 19.7, 5.85, 22.2), fill=1),
        wall((29.15, 19.7, 30, 22.2), fill=1),
    ]


def vertical():
    return [
        wall((60, 0, 62.5, 5)),
        wall((60, 30, 62.5, 35)),
        arc(((60.3, 5.85), (60.3, 18.7), (70.75, 29.15), (83.6, 29.15))),
        wall((60.3, 5, 62.8, 5.85), fill=1),
        wall((60.3, 29.15, 62.8, 30), fill=1),
    ]


def test_short_wall_jamb_swing_has_source_owned_nonmaterial_footprint_bridge():
    d = horizontal()
    rows = detect(d)
    assert len(rows) == 1, rows
    x = rows[0]
    assert x.axis == "h"
    assert (x.first_host_path_id, x.second_host_path_id, x.swing_arc_path_id) == (
        0,
        1,
        2,
    )
    assert x.jamb_cap_path_ids == (3, 4)
    assert x.bounds_pdf_pts == (5.0, 20.0, 30.0, 22.5)
    assert x.measurement_authorized is False
    assert x.physical_wall_authenticated is False
    assert x.to_dict()["kind"] == "source_hosted_swing_door_footprint_continuity_only"


def test_vertical_hosted_swing_door_geometry():
    # Rotated source-native swing-door geometry, not a fixed-window chevron.
    d = vertical()
    rows = detect(d)
    assert len(rows) == 1, rows
    x = rows[0]
    assert x.axis == "v"
    assert x.bounds_pdf_pts == (60.0, 5.0, 62.5, 30.0)
    assert x.jamb_cap_path_ids == (3, 4)


def test_missing_arc_or_either_cap_or_either_host_abstains():
    d = horizontal()
    for deleted in range(len(d)):
        assert detect(d[:deleted] + d[deleted + 1 :]) == ()


def test_cross_viewport_or_duplicate_arc_cannot_own_one_door():
    d = horizontal()
    d[0]["viewport_id"] = "floor-plan"
    d[1]["viewport_id"] = "elevation"
    assert detect(d) == ()
    d = horizontal()
    d.append(arc(((5.85, -3.6), (18.7, -3.6), (29.15, 6.85), (29.15, 19.7))))
    assert detect(d) == ()


def test_internal_wall_swing_is_not_external_footprint():
    d = horizontal()
    for x in d:
        x["layer"] = "Enclosure_WallInternal"
    assert detect(d) == ()


def test_window_identity_over_same_gap_vetoes_door_identity():
    d = horizontal()
    words = [(10, 25, 17, 30, "asw")]
    assert detect(d, words) == ()


def test_through_wall_intervening_gap_cannot_be_invented_as_door():
    d = horizontal() + [wall((12, 20, 20, 22.5))]
    assert detect(d) == ()


def test_preflight_keeps_authentic_short_wall_hosts_as_topology_only():
    # Older wall-strip collectors discard small real jamb-side external wall
    # rectangles. They cannot veto a separate original arc + two jambs.
    from pb_new_exterior_wall_preflight import attempt_source_native_outer_wall_first

    drawings = horizontal()
    attempt = attempt_source_native_outer_wall_first(
        drawings,
        source_ink_already_scoped=True,
        window_source_drawings=drawings,
    )
    assert len(attempt.swing_door_footprint_bridges) == 1
    assert attempt.swing_door_footprint_bridges[0].swing_arc_path_id == 2
    assert attempt.status == "ABSTAINED"
    assert attempt.measurement_authorized is False
    assert attempt.physical_wall_authenticated is False


def test_swing_arc_geometry_does_not_authorize_customer_area():
    d = horizontal()
    bridge = detect(d)[0]
    emitted = bridge.to_dict()
    assert emitted["measurement_authorized"] is False
    assert emitted["physical_wall_authenticated"] is False
    assert emitted["bounds_pdf_pts"] == [5.0, 20.0, 30.0, 22.5]
