"""Source-component union contracts: never certify overlapping/foreign voids.

No original plans, golden benchmark quantities or client geometry in these tests.
"""
import math

from pb_multi_space_footprint_geometry import (
    MultiSpaceFootprintBuilder, MultiSpaceFootprintEngine,
    SpaceComponent, SpaceType, FootprintStatus,
)


def test_valid_touching_compound_union_is_still_confirmed():
    builder = MultiSpaceFootprintBuilder()
    builder.add_main_room(10.0, 6.0)
    builder.add_verandah(10.0, 2.0, adjacency="front")
    result = builder.build()
    assert result.status == FootprintStatus.CONFIRMED.value
    assert result.metadata["source_geometry_conflicts"] == []
    assert result.gross_floor_area_m2 == 80.0


def test_positive_overlap_is_quarantined_and_order_independent():
    first = SpaceComponent(
        "a", SpaceType.MAIN_BUILDING.value, "Main",
        polygon=[(0, 0), (10, 0), (10, 6), (0, 6)],
    )
    second = SpaceComponent(
        "b", SpaceType.VERANDAH.value, "Porch",
        polygon=[(0, 5), (10, 5), (10, 8), (0, 8)],
    )
    for pair in ([first, second], [second, first]):
        result = MultiSpaceFootprintEngine.evaluate(pair)
        assert result.status == FootprintStatus.PARTIAL_MISSING_COMPONENTS.value
        assert "overlapping_source_solid_areas" in result.metadata["source_geometry_conflicts"]


def test_source_void_outside_building_cannot_subtract_from_occupied_floor():
    builder = MultiSpaceFootprintBuilder()
    builder.add_main_room(10.0, 6.0)
    builder.add_courtyard_void(2.0, 2.0, origin=(15, 15))
    result = builder.build()
    assert result.status == FootprintStatus.PARTIAL_MISSING_COMPONENTS.value
    assert "source_void_outside_solid_footprint" in result.metadata["source_geometry_conflicts"]


def test_two_voids_cannot_deduct_the_same_floor_twice():
    builder = MultiSpaceFootprintBuilder()
    builder.add_main_room(12.0, 12.0)
    builder.add_courtyard_void(3.0, 3.0, origin=(2, 2))
    builder.add_courtyard_void(3.0, 3.0, origin=(3, 3))
    result = builder.build()
    assert result.status == FootprintStatus.PARTIAL_MISSING_COMPONENTS.value
    assert "overlapping_source_voids" in result.metadata["source_geometry_conflicts"]


def test_self_intersecting_floor_ring_must_not_get_confirmed():
    ring = [(0, 0), (8, 6), (0, 6), (8, 0)]
    result = MultiSpaceFootprintEngine.evaluate([
        SpaceComponent("self", SpaceType.MAIN_BUILDING.value, "Crossing", polygon=ring)
    ])
    assert result.status == FootprintStatus.PARTIAL_MISSING_COMPONENTS.value
    assert "invalid_component_metric_area" in result.metadata["source_geometry_conflicts"]


def test_repeated_physical_space_id_is_not_two_separate_components():
    builder = MultiSpaceFootprintBuilder()
    builder.add_main_room(10.0, 6.0)
    builder.add_verandah(10.0, 2.0, adjacency="front")
    builder.components[1].space_id = builder.components[0].space_id
    result = builder.build()
    assert result.status == FootprintStatus.PARTIAL_MISSING_COMPONENTS.value
    assert "duplicate_physical_space_identity" in result.metadata["source_geometry_conflicts"]


def test_forged_figured_dimensions_disagree_with_original_shape():
    component = SpaceComponent(
        "main", SpaceType.MAIN_BUILDING.value, "Main",
        polygon=[(0, 0), (8, 0), (8, 6), (0, 6)], length_m=8, width_m=6,
    )
    component.length_m = 9
    result = MultiSpaceFootprintEngine.evaluate([component])
    assert result.status == FootprintStatus.PARTIAL_MISSING_COMPONENTS.value
    assert "figured_dimensions_disagree_with_source_polygon" in result.metadata["source_geometry_conflicts"]


def test_compound_missing_coordinate_placement_abstains_from_whole_area():
    parts = [
        SpaceComponent("main", SpaceType.MAIN_BUILDING.value, "Main", length_m=8, width_m=6),
        SpaceComponent("porch", SpaceType.VERANDAH.value, "Porch", length_m=8, width_m=2),
    ]
    result = MultiSpaceFootprintEngine.evaluate(parts)
    assert result.status == FootprintStatus.PARTIAL_MISSING_COMPONENTS.value
    assert "unplaced_compound_source_component" in result.metadata["source_geometry_conflicts"]


def test_rotated_valid_single_polygon_keeps_confirmed_source_area():
    theta = math.radians(28.0)
    u = (math.cos(theta), math.sin(theta))
    v = (-math.sin(theta), math.cos(theta))
    ring = [
        (0.0, 0.0),
        (8*u[0], 8*u[1]),
        (8*u[0] + 6*v[0], 8*u[1] + 6*v[1]),
        (6*v[0], 6*v[1]),
    ]
    result = MultiSpaceFootprintEngine.evaluate([
        SpaceComponent(
            "main", SpaceType.MAIN_BUILDING.value, "Rotated",
            polygon=ring, length_m=8, width_m=6,
        )
    ])
    assert result.status == FootprintStatus.CONFIRMED.value
    assert result.gross_floor_area_m2 == 48.0
