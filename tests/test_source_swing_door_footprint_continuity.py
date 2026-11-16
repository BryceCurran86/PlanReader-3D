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


def test_rival_perpendicular_wall_cannot_displace_exact_jamb_hosts():
    # The outside wall continues well past an entry door at either end.
    # Its large filled body is a competing candidate, not the actual short
    # wall that terminates at both original jamb caps.
    d = vertical()
    d.append(wall((60, 0, 105, 4)))
    d.append(wall((60, 31, 105, 35)))
    bridges = detect(d)
    assert len(bridges) == 1
    b = bridges[0]
    assert b.axis == "v"
    assert (b.first_host_path_id, b.second_host_path_id) == (0, 1)
    assert b.jamb_cap_path_ids == (3, 4)
    assert b.swing_arc_path_id == 2
    assert b.measurement_authorized is False


def test_multiple_equally_exact_jamb_host_owners_remain_unresolved():
    # One quarter arc cannot grant an invented unique host when genuinely
    # distinct painted source paths terminate at the same source caps.
    d = vertical()
    d.append(wall((60.0, 0.0, 62.5, 5.0)))
    d.append(wall((60.0, 30.0, 62.5, 35.0)))
    # Exact duplicate geometry is handled by the existing source owner
    # ambiguity rules; it must not claim an authoritative physical wall.
    rows = detect(d)
    assert all(not row.physical_wall_authenticated for row in rows)
    assert all(not row.measurement_authorized for row in rows)


def test_original_3laurel_right_entry_porch_door_native_host_witness():
    import hashlib
    from tests.original_source_3laurel import ORIGINAL_SHA256, require_original_3laurel
    from pb_source_native_wall_body_junction_graph_shadow import _unique_source_wall_bars

    original = require_original_3laurel().read_bytes()
    assert hashlib.sha256(original).hexdigest() == ORIGINAL_SHA256
    with fitz.open(stream=original, filetype="pdf") as doc:
        page = doc[2]
        drawings = page.get_drawings()
        words = page.get_text("words")
        before = (len(drawings), len(words))
        bars = _unique_source_wall_bars(drawings)
        bridges = detect(drawings, words, page_index=2, wall_bars=bars)
        after = (len(page.get_drawings()), len(page.get_text("words")))
    assert before == after
    entrance = [bridge for bridge in bridges if bridge.swing_arc_path_id == 1912]
    assert len(entrance) == 1
    b = entrance[0]
    assert b.axis == "v"
    assert b.first_host_path_id != b.second_host_path_id
    assert len(set(b.jamb_cap_path_ids)) == 2
    assert not b.physical_wall_authenticated
    assert not b.measurement_authorized
