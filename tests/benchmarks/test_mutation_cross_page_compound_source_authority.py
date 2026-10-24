"""Original source page ownership is not evidence of cross-sheet placement."""
from __future__ import annotations

from pb_multi_space_footprint_geometry import (
    FootprintStatus, MultiSpaceFootprintBuilder, MultiSpaceFootprintEngine,
    SpaceComponent, SpaceType,
)


def _builder(main_page, attached_page):
    builder = MultiSpaceFootprintBuilder()
    builder.add_main_room(10.0, 6.0, source_page=main_page)
    builder.add_verandah(10.0, 2.0, adjacency="front", source_page=attached_page)
    return builder.build()


def test_same_page_placed_compound_retains_confirmed_area():
    result = _builder(7, 7)
    assert result.status == FootprintStatus.CONFIRMED.value
    assert result.gross_floor_area_m2 == 80.0
    assert result.metadata["source_geometry_conflicts"] == []


def test_two_source_pages_cannot_claim_one_physical_floor_union():
    for source_pages in ((7, 11), (11, 7)):
        result = _builder(*source_pages)
        assert result.status == FootprintStatus.PARTIAL_MISSING_COMPONENTS.value
        assert (
            "cross_page_component_union_without_correspondence"
            in result.metadata["source_geometry_conflicts"]
        )


def test_partial_source_page_ancestry_is_not_enough_to_seal_union():
    for source_pages in ((7, None), (None, 7)):
        result = _builder(*source_pages)
        assert result.status == FootprintStatus.PARTIAL_MISSING_COMPONENTS.value
        assert "cross_page_component_union_without_correspondence" in (
            result.metadata["source_geometry_conflicts"]
        )


def test_single_source_page_alone_remains_valid():
    result = MultiSpaceFootprintEngine.evaluate([
        SpaceComponent("room", SpaceType.MAIN_BUILDING.value, "Room",
            polygon=[(0, 0), (8, 0), (8, 4), (0, 4)],
            length_m=8.0, width_m=4.0, source_page=9),
    ])
    assert result.status == FootprintStatus.CONFIRMED.value
    assert result.gross_floor_area_m2 == 32.0


def test_booleans_negative_and_string_page_ids_do_not_become_original_pages():
    for bad in (True, False, "7", -1, 0, 1.5):
        result = _builder(bad, bad)
        assert result.status == FootprintStatus.PARTIAL_MISSING_COMPONENTS.value
        assert "invalid_source_component_page" in result.metadata["source_geometry_conflicts"]
