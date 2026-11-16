"""Hosted panel-lift garage aperture keeps the footprint, not wall material."""

from shapely.geometry import box
from shapely.ops import unary_union

from pb_source_garage_door_footprint_continuity import (
    detect_exterior_garage_door_footprint_bridges,
)

_LAYER = "Enclosure_WallExternal"


def _fill(bounds, *, layer=_LAYER, tone=0.0):
    return {"layer": layer, "rect": bounds, "fill": (tone, tone, tone), "items": ()}


def _setup():
    drawings = [
        _fill((10.0, 0.0, 12.0, 20.0)),
        _fill((10.0, 80.0, 12.0, 100.0)),
        _fill((10.0, 20.0, 14.0, 20.8), tone=0.415686),
        _fill((10.0, 79.2, 14.0, 80.0), tone=0.415686),
    ]
    words = [
        (12.0, 32.0, 14.0, 36.0, "Panel"),
        (12.0, 44.0, 14.0, 48.0, "Lift"),
        (12.0, 56.0, 14.0, 60.0, "Door"),
    ]
    return drawings, words


def test_two_anchored_native_caps_and_panel_lift_label_close_only_footprint():
    drawings, words = _setup()
    matches = detect_exterior_garage_door_footprint_bridges(
        drawings, words, page_index=2
    )
    assert len(matches) == 1
    door = matches[0]
    assert (door.start_host_path_id, door.end_host_path_id) == (0, 1)
    assert door.jamb_cap_path_ids == (2, 3)
    assert door.axis == "v"
    assert door.bounds_pdf_pts == (10.0, 20.0, 12.0, 80.0)
    assert door.physical_wall_authenticated is False
    assert door.measurement_authorized is False
    assert (
        door.to_dict()["kind"] == "source_garage_panel_lift_footprint_continuity_only"
    )
    continuous = unary_union(
        [
            box(*drawings[0]["rect"]),
            box(*door.bounds_pdf_pts),
            box(*drawings[1]["rect"]),
        ]
    )
    assert continuous.is_valid
    assert continuous.geom_type == "Polygon"


def test_missing_legend_or_missing_grey_end_caps_keeps_garage_open():
    drawings, words = _setup()
    assert detect_exterior_garage_door_footprint_bridges(drawings, []) == ()
    assert detect_exterior_garage_door_footprint_bridges(drawings, words[:-1]) == ()
    assert detect_exterior_garage_door_footprint_bridges(drawings[:3], words) == ()
    assert detect_exterior_garage_door_footprint_bridges(drawings[:2], words) == ()


def test_full_thickness_wall_inside_door_span_does_not_authorize_virtual_join():
    drawings, words = _setup()
    drawings.append(_fill((10.0, 40.0, 12.0, 60.0)))
    assert detect_exterior_garage_door_footprint_bridges(drawings, words) == ()


def test_internal_joinery_and_cross_viewport_decoy_are_not_garage_exteriors():
    drawings, words = _setup()
    for drawing in drawings:
        drawing["layer"] = "Interior_Joinery"
    assert detect_exterior_garage_door_footprint_bridges(drawings, words) == ()


def test_competing_wall_owners_fail_closed():
    drawings, words = _setup()
    drawings.append(_fill((10.0, 0.0, 12.0, 20.0)))
    assert detect_exterior_garage_door_footprint_bridges(drawings, words) == ()


def test_garage_label_outside_hosted_span_is_not_an_aperture():
    drawings, words = _setup()
    words = [(a, b + 200, c, d + 200, word) for a, b, c, d, word in words]
    assert detect_exterior_garage_door_footprint_bridges(drawings, words) == ()
