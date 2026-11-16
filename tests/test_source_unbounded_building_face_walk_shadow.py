"""Use the UNBOUNDED outside face for one building containing two homes.

These are topology-only safety/acceptance tests; no external wall customer
area or finished floor area can be minted from the preview.
"""

from dataclasses import dataclass

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from pb_source_shared_dwelling_envelope_shadow import CandidateSharedBuildingDivider
from pb_source_unbounded_building_face_walk_shadow import (
    walk_source_unbounded_building_face,
)


@dataclass(frozen=True)
class SourceBar:
    polygon: Polygon
    original_path_id: int

    def native_path_indices(self):
        return (self.original_path_id,)


def _building_bars():
    return tuple(
        SourceBar(box(*r), i)
        for i, r in enumerate(
            (
                (0, 0, 240, 3),
                (0, 117, 240, 120),
                (0, 0, 3, 120),
                (237, 0, 240, 120),
                (118, 0, 122, 120),  # full-length PARTY partition, physically real
            )
        )
    )


def _source_words(*, second_x=178, alfresco=False):
    result = (
        (47, 55, 67, 63, "LIVING", 0, 0, 0),
        (second_x - 10, 55, second_x + 10, 63, "MEDIA", 1, 0, 0),
    )
    if alfresco:
        return (*result, (12, 25, 43, 33, "ALFRESCO", 2, 0, 0))
    return result


def _party():
    return CandidateSharedBuildingDivider(
        source_page_index=2,
        annotation_word_ids=(733, 734),
        annotation_text="PARTY WALL",
        wall_native_path_ids=(4,),
        wall_layer="Enclosure_WallExternal",
        wall_bounds_pdf_pts=(118.0, 0.0, 122.0, 120.0),
        orientation="vertical",
        side_one_label="LIVING",
        side_two_label="MEDIA",
    )


def test_complete_two_dwelling_envelope_walk_skips_internal_party_edge():
    bars = _building_bars()
    result = walk_source_unbounded_building_face(
        bars,
        _source_words(),
        shared_dividers=(_party(),),
        source_wall_union=unary_union([x.polygon for x in bars]),
    )
    assert result.status == "CANDIDATE"
    assert result.enclosed_region_count == 2
    assert result.enclosed_dwelling_zone_count == 2
    assert result.outer_wall_native_path_ids == (0, 1, 2, 3)
    assert result.internal_party_wall_native_path_ids == (4,)
    assert len(result.clockwise_pdf_pts) >= 5
    assert result.clockwise_pdf_pts[0] == result.clockwise_pdf_pts[-1]
    pts = result.clockwise_pdf_pts
    assert sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:])) > 0
    assert result.to_dict()["measurement_authorized"] is False
    assert result.to_dict()["building_footprint_authenticated"] is False


def test_second_dwelling_wall_gap_is_not_repaired_by_left_turn_or_hull():
    bars = list(_building_bars())
    bars[1] = SourceBar(box(0, 117, 122, 120), 1)  # right home opens outdoors
    result = walk_source_unbounded_building_face(
        bars,
        _source_words(),
        shared_dividers=(_party(),),
    )
    assert result.status == "ABSTAINED"
    assert result.reason == "source_dwelling_region_still_open_to_outside"
    assert result.enclosed_region_count == 1
    assert result.enclosed_dwelling_zone_count == 1
    assert result.unclosed_dwelling_sides == ("right",)
    assert result.clockwise_pdf_pts == ()


def test_two_printed_rooms_on_same_side_cannot_prove_second_dwelling():
    result = walk_source_unbounded_building_face(
        _building_bars(), _source_words(second_x=59), shared_dividers=(_party(),)
    )
    assert result.status == "ABSTAINED"
    assert result.unclosed_dwelling_sides == ("right",)


def test_single_dwelling_unchanged_when_no_party_source_exists():
    result = walk_source_unbounded_building_face(
        _building_bars()[:4], _source_words(), shared_dividers=()
    )
    assert result.status == "CANDIDATE"
    assert result.enclosed_region_count == 1
    assert result.internal_party_wall_native_path_ids == ()


def test_missing_physical_party_between_occupied_units_fails():
    result = walk_source_unbounded_building_face(
        _building_bars()[:4], _source_words(), shared_dividers=(_party(),)
    )
    assert result.status == "ABSTAINED"
    assert result.reason == "party_wall_two_sides_are_same_free_space"


def test_alfresco_bounded_in_building_would_make_wrong_outside_trace():
    result = walk_source_unbounded_building_face(
        _building_bars(), _source_words(alfresco=True), shared_dividers=(_party(),)
    )
    assert result.status == "ABSTAINED"
    assert result.reason == "outdoor_space_inside_proposed_building"


def test_far_unowned_structural_wall_or_separate_building_cannot_be_dropped():
    bars = (*_building_bars(), SourceBar(box(280, 20, 283, 90), 12))
    result = walk_source_unbounded_building_face(
        bars, _source_words(), shared_dividers=(_party(),)
    )
    assert result.status == "ABSTAINED"
    assert result.reason == "source_other_structural_walls_outside_candidate"
    assert result.other_source_wall_band_count == 1


def test_original_wall_source_ids_required_and_nonfinite_or_empty_abstains():
    bad = SourceBar(Polygon(((0, 0), (1, 1), (2, 2))), 100)
    result = walk_source_unbounded_building_face(
        (bad,), _source_words(), shared_dividers=(_party(),)
    )
    assert result.status == "ABSTAINED"
    assert result.to_dict()["measurement_authorized"] is False


def test_clockwise_outside_face_walk_handles_a_source_reentrant_L_not_a_hull():
    bars = tuple(
        SourceBar(box(*rect), i)
        for i, rect in enumerate(
            (
                (0, 0, 52, 2),
                (50, 0, 52, 52),
                (50, 50, 100, 52),
                (98, 50, 100, 100),
                (0, 98, 100, 100),
                (0, 0, 2, 100),
            )
        )
    )
    result = walk_source_unbounded_building_face(bars, (), shared_dividers=())
    assert result.status == "CANDIDATE"
    assert set(result.outer_wall_native_path_ids) == set(range(6))
    ring = Polygon(result.clockwise_pdf_pts)
    assert ring.is_valid
    assert not ring.covers(box(75, 20, 77, 23))
    assert ring.covers(box(10, 80, 12, 82))
    assert ring.area < 10000  # no page bounding hull
    assert not result.measurement_authorized


def test_source_T_junction_inside_outside_wall_is_not_taken_as_outer_face():
    bars = (
        *_building_bars()[:4],
        SourceBar(box(0, 56, 70, 59), 9),  # genuine internal T wall
    )
    result = walk_source_unbounded_building_face(bars, (), shared_dividers=())
    assert result.status == "CANDIDATE"
    assert 9 not in result.outer_wall_native_path_ids
    assert set(result.outer_wall_native_path_ids) == {0, 1, 2, 3}
    assert result.clockwise_pdf_pts[0] == result.clockwise_pdf_pts[-1]
    assert not result.measurement_authorized


def test_unwitnessed_four_tenths_point_source_gap_is_not_snapped_closed():
    bars = list(_building_bars())
    bars[0] = SourceBar(box(0, 0, 50, 3), 0)
    bars.append(SourceBar(box(50.425, 0, 240, 3), 5))
    result = walk_source_unbounded_building_face(
        bars,
        _source_words(),
        shared_dividers=(_party(),),
    )
    assert result.status == "ABSTAINED"
    assert result.clockwise_pdf_pts == ()
    assert not result.building_footprint_authenticated


def test_source_outside_walk_is_invariant_to_translation_and_input_order():
    from dataclasses import replace

    bars = _building_bars()
    original = walk_source_unbounded_building_face(
        bars,
        _source_words(),
        shared_dividers=(_party(),),
    )
    shifted_bars = tuple(
        SourceBar(
            box(
                bar.polygon.bounds[0] + 27,
                bar.polygon.bounds[1] + 13,
                bar.polygon.bounds[2] + 27,
                bar.polygon.bounds[3] + 13,
            ),
            bar.original_path_id,
        )
        for bar in reversed(bars)
    )
    shifted_words = tuple(
        (w[0] + 27, w[1] + 13, w[2] + 27, w[3] + 13, *w[4:]) for w in _source_words()
    )
    party = replace(_party(), wall_bounds_pdf_pts=(145.0, 13.0, 149.0, 133.0))
    shifted = walk_source_unbounded_building_face(
        shifted_bars,
        shifted_words,
        shared_dividers=(party,),
    )
    assert original.status == shifted.status == "CANDIDATE"
    assert original.outer_wall_native_path_ids == shifted.outer_wall_native_path_ids
    assert (
        original.internal_party_wall_native_path_ids
        == shifted.internal_party_wall_native_path_ids
    )
    assert (
        original.enclosed_dwelling_zone_count
        == shifted.enclosed_dwelling_zone_count
        == 2
    )
    assert original.measurement_authorized is shifted.measurement_authorized is False
