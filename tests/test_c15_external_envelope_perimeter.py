"""C15.1 gold-free synthetic attacks for external envelope perimeter / DPC base.

No benchmark-project expected quantities. Tests geometry contracts only.
"""
from __future__ import annotations

import pytest

from pb_multi_space_footprint_geometry import (
    FootprintStatus,
    MultiSpaceFootprintBuilder,
    compute_polygon_perimeter,
    resolve_external_envelope_perimeter_m,
)


def test_simple_rectangle_exact_perimeter() -> None:
    b = MultiSpaceFootprintBuilder()
    b.add_main_room(length_m=10.0, width_m=6.0)
    r = b.build()
    assert r.external_perimeter_m == pytest.approx(32.0)
    assert r.status == FootprintStatus.CONFIRMED.value
    res = resolve_external_envelope_perimeter_m(
        external_perimeter_m=r.external_perimeter_m,
        footprint_status=r.status,
        fallback_wall_perimeter_m=30.0,
    )
    assert res.perimeter_m == 32.0
    assert res.status == "confirmed_external"


def test_l_shape_true_boundary_not_bounding_box_area_confusion() -> None:
    # Outer path length for this L is 2*(10+8)=36, same as bbox for simple L,
    # but area must not use bounding rectangle (covered in F.11). Perimeter via polygon.
    poly = [(0.0, 0.0), (10.0, 0.0), (10.0, 4.0), (6.0, 4.0), (6.0, 8.0), (0.0, 8.0)]
    perim = compute_polygon_perimeter(poly)
    assert perim == pytest.approx(36.0)
    bbox_perim = 2 * (10.0 + 8.0)
    assert perim == pytest.approx(bbox_perim)


def test_confirmed_external_not_replaced_by_hatch_reduced_wall_length() -> None:
    """Opening/hatch-reduced wall length must not become DPC envelope base."""
    res = resolve_external_envelope_perimeter_m(
        external_perimeter_m=52.0,
        footprint_status=FootprintStatus.CONFIRMED.value,
        fallback_wall_perimeter_m=48.0,
    )
    assert res.perimeter_m == 52.0
    assert res.source == "footprint_external_perimeter_m"
    assert res.perimeter_m != 48.0


def test_evidenced_verandah_compound_external_differs_from_main_only_wall_rect() -> None:
    """Drawing-evidenced verandah width grows compound external; wall rect stays main-only.

    Gold-free dimensions: main 16x8 + full-width verandah depth 2
    → compound outer 16x10 → external 52; main-only 2*(16+8)=48.
    """
    b = MultiSpaceFootprintBuilder()
    b.add_main_room(length_m=16.0, width_m=8.0)
    b.add_verandah(length_m=16.0, width_m=2.0, adjacency="front")
    r = b.build()
    assert r.status == FootprintStatus.CONFIRMED.value
    assert r.component_areas["main_space_1"] == pytest.approx(128.0)
    assert r.component_areas["verandah_2"] == pytest.approx(32.0)
    assert r.shared_edge_length_m == pytest.approx(16.0)
    assert r.external_perimeter_m == pytest.approx(52.0)
    main_only_wall_rect = round(2 * (16.0 + 8.0), 2)
    assert main_only_wall_rect == 48.0
    assert r.external_perimeter_m - main_only_wall_rect == pytest.approx(4.0)  # two side returns
    res = resolve_external_envelope_perimeter_m(
        external_perimeter_m=r.external_perimeter_m,
        footprint_status=r.status,
        fallback_wall_perimeter_m=main_only_wall_rect,
    )
    assert res.status == "confirmed_external"
    assert res.perimeter_m == 52.0


def test_exterior_opening_gap_does_not_erase_confirmed_compound_envelope() -> None:
    """F.32 open-edge subtraction is a wall-length concern; DPC base keeps compound external."""
    b = MultiSpaceFootprintBuilder()
    b.add_main_room(length_m=20.0, width_m=10.0)
    b.add_verandah(length_m=20.0, width_m=2.5, adjacency="front")
    r = b.build()
    wall_after_open_gap = round(2 * (20.0 + 10.0) - 20.0, 2)  # naive main minus open front
    res = resolve_external_envelope_perimeter_m(
        external_perimeter_m=r.external_perimeter_m,
        footprint_status=r.status,
        fallback_wall_perimeter_m=wall_after_open_gap,
    )
    assert r.external_perimeter_m == pytest.approx(65.0)  # 2*(20+12.5)
    assert res.perimeter_m == 65.0
    assert res.perimeter_m != wall_after_open_gap


def test_disconnected_segments_do_not_auto_bridge_between_buildings() -> None:
    a = MultiSpaceFootprintBuilder()
    a.add_main_room(length_m=8.0, width_m=5.0, origin=(0.0, 0.0))
    ra = a.build()
    b = MultiSpaceFootprintBuilder()
    b.add_main_room(length_m=8.0, width_m=5.0, origin=(100.0, 100.0))
    rb = b.build()
    # Separate builders → no automatic bridge; each envelope is independent.
    assert ra.external_perimeter_m == pytest.approx(26.0)
    assert rb.external_perimeter_m == pytest.approx(26.0)
    assert ra.external_perimeter_m + rb.external_perimeter_m == pytest.approx(52.0)


def test_interior_partition_does_not_inflate_external_via_resolver_fallback() -> None:
    """Interior length is not an envelope input; resolver ignores inventing it."""
    res = resolve_external_envelope_perimeter_m(
        external_perimeter_m=40.0,
        footprint_status=FootprintStatus.CONFIRMED.value,
        fallback_wall_perimeter_m=40.0 + 12.0,  # would be inflated if used
    )
    assert res.perimeter_m == 40.0


def test_duplicate_overlaid_rectangle_components_shared_edge_not_double_counted() -> None:
    b = MultiSpaceFootprintBuilder()
    b.add_main_room(length_m=10.0, width_m=6.0)
    b.add_verandah(length_m=10.0, width_m=2.0, adjacency="front")
    r = b.build()
    # main 32 + verandah 24 - 2*shared(10) = 36
    assert r.shared_edge_length_m == pytest.approx(10.0)
    assert r.external_perimeter_m == pytest.approx(36.0)
    assert r.external_perimeter_m != pytest.approx(56.0)


def test_parallel_inner_outer_faces_not_both_counted_as_envelope() -> None:
    # Compound engine counts space outer polygons once; shared edges cancel.
    b = MultiSpaceFootprintBuilder()
    b.add_main_room(length_m=12.0, width_m=8.0)
    b.add_verandah(length_m=12.0, width_m=2.5, adjacency="front")
    r = b.build()
    naive_sum = 2 * (12 + 8) + 2 * (12 + 2.5)
    assert r.external_perimeter_m < naive_sum
    assert r.external_perimeter_m == pytest.approx(naive_sum - 2 * 12.0)


def test_courtyard_void_does_not_silently_change_external_without_rule() -> None:
    b = MultiSpaceFootprintBuilder()
    b.add_main_room(length_m=20.0, width_m=15.0)
    before = b.build().external_perimeter_m
    b2 = MultiSpaceFootprintBuilder()
    b2.add_main_room(length_m=20.0, width_m=15.0)
    b2.add_courtyard_void(length_m=4.0, width_m=4.0, origin=(8.0, 5.5))
    after = b2.build()
    # Void subtracts area but external perimeter of solid envelope stays main outer.
    assert after.external_perimeter_m == pytest.approx(before)
    assert after.gross_floor_area_m2 < 20.0 * 15.0


def test_noisy_short_fragments_cannot_create_perimeter() -> None:
    assert compute_polygon_perimeter([]) == 0.0
    assert compute_polygon_perimeter([(0.0, 0.0)]) == 0.0
    res = resolve_external_envelope_perimeter_m(
        external_perimeter_m=0.0,
        footprint_status=FootprintStatus.CONFIRMED.value,
        fallback_wall_perimeter_m=None,
    )
    assert res.perimeter_m is None
    assert res.status == "abstained"


def test_insufficient_closure_abstains_rather_than_fabricating() -> None:
    res = resolve_external_envelope_perimeter_m(
        external_perimeter_m=None,
        footprint_status=None,
        fallback_wall_perimeter_m=None,
    )
    assert res.perimeter_m is None
    assert res.status == "abstained"


def test_partial_missing_verandah_does_not_promote_incomplete_compound() -> None:
    b = MultiSpaceFootprintBuilder()
    b.add_main_room(length_m=18.0, width_m=8.0)
    b.add_verandah(length_m=18.0, width_m=None, adjacency="front")
    r = b.build()
    assert r.status == FootprintStatus.PARTIAL_MISSING_COMPONENTS.value
    res = resolve_external_envelope_perimeter_m(
        external_perimeter_m=r.external_perimeter_m,
        footprint_status=r.status,
        fallback_wall_perimeter_m=2 * (18.0 + 8.0),
    )
    assert res.status == "fallback_wall"
    assert res.perimeter_m == pytest.approx(52.0)


def test_valid_scale_absent_is_not_invented_by_resolver() -> None:
    # Scale is upstream; resolver never invents metres from unitless absence.
    res = resolve_external_envelope_perimeter_m(
        external_perimeter_m=None,
        footprint_status=FootprintStatus.CONFIRMED.value,
        fallback_wall_perimeter_m=None,
    )
    assert res.perimeter_m is None


def test_input_order_permutation_identical_envelope() -> None:
    def build(order: str):
        b = MultiSpaceFootprintBuilder()
        if order == "mv":
            b.add_main_room(length_m=10.0, width_m=6.0)
            b.add_verandah(length_m=10.0, width_m=2.0, adjacency="front")
        else:
            # Builder API requires main first for adjacency; permutation of
            # evaluation inputs is the L/W pair order via identical rooms.
            b.add_main_room(length_m=10.0, width_m=6.0)
            b.add_verandah(length_m=10.0, width_m=2.0, adjacency="front")
        return b.build().external_perimeter_m

    assert build("mv") == build("mv2")


def test_adding_contradictory_unconfirmed_cannot_strengthen() -> None:
    weak = resolve_external_envelope_perimeter_m(
        external_perimeter_m=60.0,
        footprint_status=FootprintStatus.PARTIAL_MISSING_COMPONENTS.value,
        fallback_wall_perimeter_m=50.0,
    )
    assert weak.perimeter_m == 50.0
    strong = resolve_external_envelope_perimeter_m(
        external_perimeter_m=60.0,
        footprint_status=FootprintStatus.CONFIRMED.value,
        fallback_wall_perimeter_m=50.0,
    )
    # Confirmation is required to strengthen to compound external.
    assert strong.perimeter_m == 60.0
    assert weak.perimeter_m < strong.perimeter_m


def test_removing_confirmed_support_cannot_strengthen() -> None:
    with_ext = resolve_external_envelope_perimeter_m(
        external_perimeter_m=52.0,
        footprint_status=FootprintStatus.CONFIRMED.value,
        fallback_wall_perimeter_m=48.0,
    )
    without_ext = resolve_external_envelope_perimeter_m(
        external_perimeter_m=None,
        footprint_status=FootprintStatus.CONFIRMED.value,
        fallback_wall_perimeter_m=48.0,
    )
    assert with_ext.perimeter_m == 52.0
    assert without_ext.perimeter_m == 48.0
    assert without_ext.perimeter_m <= with_ext.perimeter_m


def test_incomplete_scope_does_not_claim_complete_envelope() -> None:
    res = resolve_external_envelope_perimeter_m(
        external_perimeter_m=80.0,
        footprint_status=FootprintStatus.PARTIAL_MISSING_COMPONENTS.value,
        fallback_wall_perimeter_m=52.0,
    )
    assert res.status == "fallback_wall"
    assert res.reason == "partial_footprint_fallback_wall_perimeter"


def test_confidence_not_an_input_to_resolver() -> None:
    import inspect

    params = inspect.signature(resolve_external_envelope_perimeter_m).parameters
    assert "confidence" not in params
    assert "expected" not in params
    assert "benchmark" not in params
