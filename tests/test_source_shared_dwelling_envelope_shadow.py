"""A common-party-wall separates TWO dwelling regions, not BUILDING outside."""

from __future__ import annotations

import fitz
from shapely.geometry import Polygon

from pb_source_shared_dwelling_envelope_shadow import (
    CandidateSharedBuildingDivider,
    closed_loop_uses_interior_dwelling_divider,
    detect_native_shared_dwelling_dividers,
)


def words(*, party=True, opposite=True, grouped=True):
    result = [
        (45.0, 55.0, 65.0, 63.0, "LIVING", 12, 0, 0),
    ]
    if opposite:
        result.append((142.0, 55.0, 164.0, 63.0, "MEDIA", 13, 0, 0))
    if party:
        result.extend(
            [
                (70.0, 43.0, 91.0, 51.0, "PARTY", 5, 0, 0),
                (70.0, 53.0, 92.0, 61.0, "WALL", 5 if grouped else 9, 1, 0),
            ]
        )
    return result


def _wall(rect, layer="Enclosure_WallExternal", fill=(0.0, 0.0, 0.0)):
    return {
        "rect": fitz.Rect(*rect),
        "type": "f",
        "fill": fill,
        "layer": layer,
        "items": (),
    }


def walls():
    return (
        _wall((20, 10, 22, 110)),
        _wall((98.5, 10, 101.5, 110)),
        _wall((220, 10, 222, 110)),
        _wall((20, 10, 222, 12)),
        _wall((20, 108, 222, 110)),
    )


def test_native_annotated_party_wall_between_living_spaces_is_not_exterior():
    result = detect_native_shared_dwelling_dividers(
        walls(),
        words(),
        source_page_index=2,
    )
    assert len(result) == 1
    part = result[0]
    assert part.annotation_word_ids == (2, 3)
    assert part.wall_native_path_ids == (1,)
    assert part.orientation == "vertical"
    assert part.wall_layer == "Enclosure_WallExternal"
    assert part.source_role == "candidate_inter_dwelling_party_wall"
    assert part.minimum_dwelling_zones_candidate == 2
    assert not part.wall_role_authenticated
    assert not part.building_footprint_authenticated
    assert not part.measurement_authorized
    assert (
        part.to_dict()["building_envelope_policy"]
        == "shared_outer_envelope_not_unit_room_loop"
    )


def test_closed_loop_around_one_dwelling_is_rejected_but_whole_envelope_survives():
    party = detect_native_shared_dwelling_dividers(walls(), words())
    left_unit = Polygon(((20, 10), (98.5, 10), (98.5, 110), (20, 110)))
    right_unit = Polygon(((101.5, 10), (220, 10), (220, 110), (101.5, 110)))
    entire_building = Polygon(((20, 10), (222, 10), (222, 110), (20, 110)))
    assert closed_loop_uses_interior_dwelling_divider(left_unit, party)
    assert closed_loop_uses_interior_dwelling_divider(right_unit, party)
    assert not closed_loop_uses_interior_dwelling_divider(entire_building, party)
    assert not closed_loop_uses_interior_dwelling_divider(entire_building, ())


def test_party_word_alone_or_unrelated_annotation_cannot_relabel_wall():
    assert detect_native_shared_dwelling_dividers(walls(), words(party=False)) == ()
    assert detect_native_shared_dwelling_dividers(walls(), words(opposite=False)) == ()
    assert detect_native_shared_dwelling_dividers(walls(), words(grouped=False)) == ()


def test_missing_native_physical_wall_ink_refuses_party_role():
    d = list(walls())
    d[1] = _wall((98.5, 10, 101.5, 110), layer="Finish_Floor")
    assert detect_native_shared_dwelling_dividers(d, words()) == ()
    d[1] = _wall((98.5, 10, 101.5, 110), fill=(1.0, 1.0, 1.0))
    assert detect_native_shared_dwelling_dividers(d, words()) == ()
    d[1] = _wall((98.5, 10, 101.5, 110), layer="Annotation_Dimensions")
    assert detect_native_shared_dwelling_dividers(d, words()) == ()


def test_attached_alfresco_and_porch_not_conditioned_opposite_dwelling():
    w = [
        (45.0, 55.0, 65.0, 63.0, "ALFRESCO", 12, 0, 0),
        (142.0, 55.0, 164.0, 63.0, "PORCH", 13, 0, 0),
        (70.0, 43.0, 91.0, 51.0, "PARTY", 5, 0, 0),
        (70.0, 53.0, 92.0, 61.0, "WALL", 5, 1, 0),
    ]
    assert detect_native_shared_dwelling_dividers(walls(), w) == ()


def test_wrong_side_of_label_or_missing_full_length_wall_does_not_mint_party():
    w = words()
    both_left = [
        v if v[4] != "MEDIA" else (55.0, 75.0, 77.0, 83.0, "MEDIA", 13, 0, 0) for v in w
    ]
    assert detect_native_shared_dwelling_dividers(walls(), both_left) == ()
    d = list(walls())
    d[1] = _wall((98.5, 10, 101.5, 23))
    assert detect_native_shared_dwelling_dividers(d, w) == ()


def test_untrusted_nonfinite_geometry_or_unclosed_ring_cannot_issue():
    d = list(walls())
    d[1] = {
        "layer": "Enclosure_WallExternal",
        "rect": (float("nan"), 10, 101.5, 110),
        "fill": (0, 0, 0),
        "type": "f",
    }
    assert detect_native_shared_dwelling_dividers(d, words()) == ()
    party = detect_native_shared_dwelling_dividers(walls(), words())
    assert not closed_loop_uses_interior_dwelling_divider(((0, 0), (1, 1)), party)
