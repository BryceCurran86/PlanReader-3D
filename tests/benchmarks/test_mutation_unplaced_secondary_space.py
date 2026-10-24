"""Unknown verandah adjacency is not a source-owned footprint placement."""
import math

from pb_multi_space_footprint_geometry import (
    FootprintStatus, MultiSpaceFootprintBuilder,
)


def test_valid_front_rear_and_side_full_edge_placements():
    for edge, run in (("front", 10.0), ("rear", 10.0), ("left", 6.0), ("right", 6.0)):
        builder = MultiSpaceFootprintBuilder()
        builder.add_main_room(10.0, 6.0)
        builder.add_verandah(run, 2.0, adjacency=edge)
        result = builder.build()
        assert result.status == FootprintStatus.CONFIRMED.value
        assert result.metadata["source_geometry_conflicts"] == []
        assert result.components[1].polygon


def test_invalid_host_reference_cannot_invent_origin_rectangle():
    builder = MultiSpaceFootprintBuilder()
    builder.add_main_room(10.0, 6.0)
    builder.add_verandah(10.0, 2.0, reference_space_idx=45)
    result = builder.build()
    assert result.status == FootprintStatus.PARTIAL_MISSING_COMPONENTS.value
    assert result.components[1].polygon == []
    assert "physical_placement" in result.components[1].missing_dimensions


def test_unrecognized_edge_role_cannot_become_first_matching_front_edge():
    builder = MultiSpaceFootprintBuilder()
    builder.add_main_room(10.0, 6.0)
    builder.add_verandah(10.0, 2.0, adjacency="maybe_front")
    result = builder.build()
    assert result.status == FootprintStatus.PARTIAL_MISSING_COMPONENTS.value
    assert not result.components[1].polygon


def test_short_strip_requires_explicit_start_offset_instead_of_assuming_corner():
    builder = MultiSpaceFootprintBuilder()
    builder.add_main_room(10.0, 6.0)
    builder.add_verandah(8.0, 2.0, adjacency="front")
    result = builder.build()
    assert result.status == FootprintStatus.PARTIAL_MISSING_COMPONENTS.value
    assert result.components[1].polygon == []


def test_rotated_reference_does_not_place_axis_aligned_guess():
    builder = MultiSpaceFootprintBuilder()
    theta = math.radians(35)
    u = (math.cos(theta), math.sin(theta))
    v = (-math.sin(theta), math.cos(theta))
    builder.add_main_room(10.0, 6.0)
    builder.components[0].polygon = [
        (0.0, 0.0),
        (10*u[0], 10*u[1]),
        (10*u[0]+6*v[0], 10*u[1]+6*v[1]),
        (6*v[0], 6*v[1]),
    ]
    builder.add_verandah(10.0, 2.0, adjacency="front")
    result = builder.build()
    assert result.status == FootprintStatus.PARTIAL_MISSING_COMPONENTS.value
    assert not result.components[1].polygon
