"""Exterior windows maintain the footprint, never create a solid wall invoice."""
import fitz
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from pb_source_window_footprint_continuity import (
    detect_exterior_window_footprint_bridges,
)

LAYER = "Enclosure_WallExternal"


def _wall(bounds, *, layer=LAYER):
    return {"rect": fitz.Rect(*bounds), "layer": layer, "fill": (0., 0., 0.), "items": ()}


def _mark(a, b, *, layer=LAYER):
    return {"rect": fitz.Rect(min(a[0],b[0]), min(a[1],b[1]), max(a[0],b[0]), max(a[1],b[1])),
            "layer": layer, "fill": None,
            "items": (("l", fitz.Point(*a), fitz.Point(*b)),)}


def _window_setup(*, layer=LAYER):
    drawings = [
        _wall((0, 0, 10, 2), layer=layer),
        _wall((20, 0, 30, 2), layer=layer),
        _mark((15, 4), (17, 4.5), layer=layer),
        _mark((15, 4), (17, 3.5), layer=layer),
    ]
    words = [(13, 9, 19, 13, "asw")]
    return drawings, words


def test_external_window_keeps_footprint_connected_not_material():
    drawings, words = _window_setup()
    bridges = detect_exterior_window_footprint_bridges(drawings, words, page_index=2)
    assert len(bridges) == 1
    bridge = bridges[0]
    assert (bridge.left_host_path_id,bridge.right_host_path_id) == (0,1)
    assert bridge.marker_path_ids == (2,3)
    assert bridge.axis == "h"
    assert bridge.bounds_pdf_pts == (10.,0.,20.,2.)
    assert bridge.measurement_authorized is False
    assert bridge.physical_wall_authenticated is False
    assert bridge.to_dict()["kind"] == "exterior_window_footprint_continuity_only"


def test_window_bridge_can_close_a_real_ring_as_topology_only():
    drawings, words = _window_setup()
    drawings += [
        _wall((0, 0, 2, 30)),
        _wall((28, 0, 30, 30)),
        _wall((0, 28, 30, 30)),
    ]
    before = unary_union([box(*tuple(d["rect"])) for d in drawings if d["fill"] is not None])
    assert sum(len(p.interiors) for p in ([before] if isinstance(before, Polygon) else before.geoms) if isinstance(p, Polygon)) == 0
    bridges = detect_exterior_window_footprint_bridges(drawings, words)
    assert len(bridges) == 1
    after = unary_union(
        [box(*tuple(d["rect"])) for d in drawings if d["fill"] is not None]
        + [box(*b.bounds_pdf_pts) for b in bridges]
    )
    assert isinstance(after, Polygon)
    assert len(after.interiors) == 1


def test_no_word_or_single_marker_or_mismatched_layer_does_not_join():
    drawings, words = _window_setup()
    assert detect_exterior_window_footprint_bridges(drawings, ()) == ()
    assert detect_exterior_window_footprint_bridges(drawings[:-1], words) == ()
    internal, words = _window_setup(layer="Interior_Joinery")
    assert detect_exterior_window_footprint_bridges(internal, words) == ()


def test_intervening_wall_and_nearest_but_unmarked_gap_remain_open():
    drawings, words = _window_setup()
    # These two hosts do NOT adjoin across an empty window aperture.
    drawings.append(_wall((12, 0, 18, 2)))
    assert detect_exterior_window_footprint_bridges(drawings, words) == ()
    drawings, words = _window_setup()
    drawings[2] = _mark((15, 4), (17, 8))
    assert detect_exterior_window_footprint_bridges(drawings, words) == ()


def test_missing_opening_identity_never_promotes_collinear_wall_gap():
    drawings, _words = _window_setup()
    # A nearby unrelated W-like label is not enough without its symbol.
    words = [(13, 80, 19, 85, "asw")]
    assert detect_exterior_window_footprint_bridges(drawings, words) == ()


def test_duplicate_host_span_is_ambiguous_not_a_footprint_bridge():
    drawings, words = _window_setup()
    drawings.insert(1, _wall((0, 0, 10, 2)))
    assert detect_exterior_window_footprint_bridges(drawings, words) == ()
