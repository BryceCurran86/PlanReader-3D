"""Native internal door jamb/quarter-arc witnesses for room topology only."""
import fitz

from pb_source_internal_swing_room_barrier import (
    detect_source_internal_swing_room_barriers as detect_internal,
)
from pb_source_swing_door_footprint_continuity import (
    detect_exterior_swing_door_footprint_bridges as detect_external,
)
def wall(bounds, fill=0.0, layer="Enclosure_WallExternal"):
    return {
        "layer": layer, "rect": fitz.Rect(*bounds),
        "fill": (fill, fill, fill), "items": (),
    }


def arc(points, layer="Enclosure_WallExternal"):
    return {
        "layer": layer,
        "rect": fitz.Rect(
            min(p[0] for p in points), min(p[1] for p in points),
            max(p[0] for p in points), max(p[1] for p in points),
        ),
        "fill": None,
        "items": (("c", *(fitz.Point(*p) for p in points)),),
    }


def horizontal():
    return [
        wall((0, 20, 5, 22.5)), wall((30, 20, 35, 22.5)),
        arc(((5.85, -3.6), (18.7, -3.6), (29.15, 6.85), (29.15, 19.7))),
        wall((5, 19.7, 5.85, 22.2), fill=1),
        wall((29.15, 19.7, 30, 22.2), fill=1),
    ]


def internal_door():
    rows = horizontal()
    for row in rows:
        row["layer"] = "Enclosure_WallInternal"
    # Original internal cap across the black wall face can be ~0.6pt wider.
    # The continuous host+quarter-arc+two caps still has unique ownership.
    rows[3]["rect"] = fitz.Rect(5.0, 19.7, 5.85, 22.8)
    rows[4]["rect"] = fitz.Rect(29.15, 19.7, 30.0, 22.8)
    return rows


def test_two_original_dark_wall_hosts_arc_white_caps_close_only_room_topology():
    rows = internal_door()
    assert detect_external(rows) == ()
    matches = detect_internal(rows, page_index=2)
    assert len(matches) == 1
    rec = matches[0]
    assert rec.page_index == 2
    assert (rec.first_host_path_id, rec.second_host_path_id, rec.swing_arc_path_id) == (
        0, 1, 2
    )
    assert rec.jamb_cap_path_ids == (3, 4)
    assert rec.bounds_pdf_pts == (5.0, 20.0, 30.0, 22.5)
    assert rec.measurement_authorized is False
    assert rec.physical_wall_authenticated is False
    d = rec.to_dict()
    assert d["kind"] == "source_owned_internal_swing_room_closure_only"
    assert d["measurement_authorized"] is False


def test_missing_original_arc_cap_or_wall_host_remains_open():
    rows = internal_door()
    for missing in range(len(rows)):
        assert detect_internal(rows[:missing] + rows[missing + 1 :]) == ()


def test_competing_window_marker_prevents_internal_door_substitution():
    assert detect_internal(internal_door(), [(10, 25, 17, 30, "asw")]) == ()


def test_cross_viewport_and_duplicate_arc_remain_unverified():
    rows = internal_door()
    rows[0]["viewport_id"] = "floor-plan"
    rows[1]["viewport_id"] = "elevation"
    assert detect_internal(rows) == ()
    rows = internal_door()
    rows.append(arc(((5.85, -3.6), (18.7, -3.6), (29.15, 6.85), (29.15, 19.7)),
                    layer="Enclosure_WallInternal"))
    assert detect_internal(rows) == ()


def test_door_closure_is_not_an_external_wall_span():
    rows = internal_door()
    rec = detect_internal(rows)[0]
    assert rec.measurement_authorized is False
    assert rec.physical_wall_authenticated is False
    assert detect_external(rows) == ()
