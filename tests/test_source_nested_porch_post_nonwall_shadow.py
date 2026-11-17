"""Source-positive negative-role evidence for exterior wall walkers.

The original 3Laurel p3 porch has two concentric post symbols drawn on an
external-wall CAD layer. These are physically real porch posts, not continuous
wall segments; they must not veto an otherwise source-closed outside face.
No project names, coordinates or native path IDs in the production detector.
"""
from shapely.geometry import box

from pb_source_unbounded_building_face_walk_shadow import (
    _source_nested_concentric_porch_post_nonwall as recognize,
)


def _concentric_source(count=4, *, layer="Enclosure_WallExternal",
                       fill=None, stroke_width=0.34):
    drawings = []
    for size in (7.1, 10.5, 12.2, 13.3)[:count]:
        low, high = 100 - size / 2, 100 + size / 2
        for p, q in (
            ((low, low), (high, low)),
            ((high, low), (high, high)),
            ((high, high), (low, high)),
            ((low, high), (low, low)),
        ):
            drawings.append({
                "type": "s", "layer": layer, "fill": fill,
                "width": stroke_width, "items": [("l", p, q)],
            })
    return drawings


def _source_words():
    return ((96, 70, 104, 76, "PORCH", 0, 0, 0),
            (96, 80, 104, 86, "TILES", 0, 0, 0))


def _outside_band():
    return box(95, 92.8, 105, 94)


def test_three_or_more_original_nested_closed_square_rings_are_post_not_wall():
    assert recognize(_outside_band(), (12,), _concentric_source(), _source_words())


def test_two_source_square_rings_cannot_exclude_possible_physical_wall():
    assert not recognize(_outside_band(), (4,), _concentric_source(2), _source_words())


def test_original_porch_and_tiles_labels_both_required():
    assert not recognize(_outside_band(), (12,), _concentric_source(),
                         ((96, 80, 104, 86, "TILES", 0, 0, 0),))


def test_filled_structural_wall_or_internal_layer_never_disappears():
    assert not recognize(_outside_band(), (12,),
                         _concentric_source(fill=(0, 0, 0)), _source_words())
    assert not recognize(_outside_band(), (12,),
                         _concentric_source(layer="Enclosure_WallInternal"), _source_words())


def test_unrelated_original_wall_stroke_not_reclassified_by_nearby_porch():
    drawings = _concentric_source()
    drawings.append({
        "type": "s", "layer": "Enclosure_WallExternal",
        "fill": None, "width": 0.34,
        "items": [("l", (150, 120), (165, 120))],
    })
    assert not recognize(box(149, 119, 166, 121), (16,), drawings, _source_words())


def test_missing_original_square_returns_abstain_not_post():
    drawings = _concentric_source()
    drawings[-1]["items"] = [("l", (80, 80), (90, 90))]
    drawings[-5]["items"] = [("l", (81, 81), (91, 91))]
    assert not recognize(_outside_band(), (12,), drawings, _source_words())


def test_non_ring_source_path_mixed_with_true_post_owners_must_not_disappear():
    drawings = _concentric_source()
    drawings.append({
        "type": "s", "layer": "Enclosure_WallExternal",
        "fill": None, "width": 0.34,
        "items": [("l", (94, 93), (106, 93))],
    })
    assert not recognize(_outside_band(), (12, 16), drawings, _source_words())


def test_ring_owner_id_without_native_local_line_overlap_is_not_enough():
    # Even a real nested porch symbol at the right coordinates is NOT proof
    # that an unrelated residual wall band belongs to the original symbol.
    assert not recognize(box(95, 95, 105, 96), (12,),
                         _concentric_source(), _source_words())
