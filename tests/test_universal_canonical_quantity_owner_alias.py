"""Source-owned canonical/physical quantity identity must be unambiguous."""
from dataclasses import replace

import pytest

from pb_live_canonical_coverage_registry import collect_live_canonical_coverage
from test_live_floor_finish_area_source_closed_export import _floor, _quantity


def _collect(floors, quantities):
    return collect_live_canonical_coverage(
        objects=tuple(floors), quantities=tuple(quantities),
        registry_run_scope="unseen-building-original-source",
    )


def test_canonical_floor_quantity_survives_distinct_physical_id():
    floor = replace(_floor(), physical_floor_surface_id="physical-room-slab-9")
    quantity = _quantity()
    summaries, gaps = _collect((floor,), (quantity,))
    assert gaps == {}
    assert summaries[0].object_records[0].quantity_ids == (quantity.quantity_id,)


def test_original_physical_floor_quantity_still_links():
    floor = replace(_floor(), physical_floor_surface_id="physical-room-slab-9")
    quantity = replace(_quantity(), input_entity_ids=(floor.physical_floor_surface_id,))
    summaries, gaps = _collect((floor,), (quantity,))
    assert gaps == {}
    assert summaries[0].object_records[0].quantity_ids == (quantity.quantity_id,)


def test_cross_owner_canonical_physical_collision_cannot_mint_credit():
    first = replace(_floor(), canonical_floor_id="source-A", physical_floor_surface_id="source-B")
    second = replace(_floor(), canonical_floor_id="source-B", physical_floor_surface_id="source-C")
    quantity = replace(_quantity(), input_entity_ids=("source-B",))
    summaries, gaps = _collect((first, second), (quantity,))
    assert "ambiguous_canonical_physical_quantity_owner" in gaps["floor"]
    assert all(quantity.quantity_id not in r.quantity_ids
               for s in summaries for r in s.object_records)


def test_two_physical_surfaces_cannot_reuse_same_canonical_id():
    first = replace(_floor(), canonical_floor_id="same-canonical", physical_floor_surface_id="original-A")
    second = replace(_floor(), canonical_floor_id="same-canonical", physical_floor_surface_id="original-B")
    with pytest.raises(ValueError, match="duplicate producer canonical identity"):
        _collect((first, second), ())
