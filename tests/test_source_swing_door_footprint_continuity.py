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


def test_orthogonal_corner_host_swing_door_continuity():
    # Corner wall meeting orthogonal wall across a swing door opening with line jamb caps
    def line(p0, p1, layer=LAYER):
        return {
            "layer": layer,
            "rect": fitz.Rect(
                min(p0[0], p1[0]),
                min(p0[1], p1[1]),
                max(p0[0], p1[0]),
                max(p0[1], p1[1]),
            ),
            "fill": None,
            "items": (("l", fitz.Point(*p0), fitz.Point(*p1)),),
        }

    d = [
        wall((0, 0, 2.5, 25)),
        wall((28.5, 22.5, 60, 25.0)),
        arc(((2.0, -1.0), (15.0, -1.0), (28.5, 10.0), (28.5, 23.5))),
        line((1.5, 22.5), (1.5, 25.0)),
        line((28.5, 22.5), (28.5, 25.0)),
    ]
    bridges = detect(d)
    assert len(bridges) == 1
    b = bridges[0]
    assert b.axis == "h"
    assert (b.first_host_path_id, b.second_host_path_id) == (0, 1)
    assert b.jamb_cap_path_ids == (3, 4)
    assert b.bounds_pdf_pts == (2.5, 22.5, 28.5, 25.0)
    assert b.measurement_authorized is False
    assert b.physical_wall_authenticated is False


def test_derbyshire_construction_sample_real_pdf_exterior_swing_doors():
    import os
    pdf_path = r"C:\Users\bryce\OneDrive\Desktop\documents\sources\other plans\02_Derbyshire_2016_construction_sample.pdf"
    if not os.path.exists(pdf_path):
        return
    from pb_new_exterior_wall_preflight import (
        _source_wall_ink_candidate_drawings,
        _collect_strips,
        _collect_dark_painted_source_wall_strips,
        _collect_monotonic_source_stroke_pairs,
        _collect_source_heavy_stroke_strips,
        _collect_cavity_multi_face_strips,
        _collect_source_wide_face_pairs,
    )
    doc = fitz.open(pdf_path)
    page = doc[3]
    drawings = page.get_drawings()
    source_words = page.get_text("words")
    wall_ink = _source_wall_ink_candidate_drawings(drawings)[0]
    bars = (
        _collect_strips(wall_ink)[0]
        + _collect_dark_painted_source_wall_strips(wall_ink)
        + _collect_monotonic_source_stroke_pairs(wall_ink)
        + _collect_source_heavy_stroke_strips(wall_ink)
        + _collect_cavity_multi_face_strips(wall_ink)
        + _collect_source_wide_face_pairs(wall_ink)
    )
    unique_bars = {}
    for bar in bars:
        if bar.polygon is None or bar.polygon.is_empty or not bar.polygon.is_valid:
            continue
        key = (int(bar.path_index), *(round(float(v), 4) for v in bar.polygon.bounds))
        unique_bars[key] = bar
    wall_bars = list(unique_bars.values())

    bridges = detect(
        drawings,
        source_words=source_words,
        wall_bars=wall_bars,
        page_index=3,
    )
    # Front entry swing door (arc 1284), North swing door (arc 855), and Laundry/Garage (arc 435)
    arc_ids = {b.swing_arc_path_id for b in bridges}
    assert 1284 in arc_ids
    assert 855 in arc_ids
    assert 435 in arc_ids
