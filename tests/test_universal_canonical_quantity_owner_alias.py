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


def test_canonical_alias_retains_stale_quantity_for_audit_but_never_credits_it():
    from pb_takeoff_coverage_audit_adapter import build_runtime_coverage_publication

    floor = replace(_floor(), physical_floor_surface_id="different-physical-floor")
    original = _quantity()
    stale = replace(original, metadata={
        **original.metadata, "source_sha256": "b" * 64,
    })
    summaries, gaps = collect_live_canonical_coverage(
        objects=(floor,), quantities=(stale,), output_rows=(),
        registry_run_scope="unfamiliar-revision-2027",
    )
    assert gaps == {"floor": ["quantity_source_lineage_conflict"]}
    assert summaries[0].object_records[0].quantity_ids == (stale.quantity_id,)
    report = build_runtime_coverage_publication(summaries, family_gaps=gaps)
    assert report["family_reports"]["floor_slab"]["stage_counts"]["QUANTIFIED"] == 0


def test_canonical_alias_with_same_original_sha_retains_valid_dependency():
    floor = replace(_floor(), physical_floor_surface_id="different-physical-floor")
    original = _quantity()
    summaries, gaps = _collect((floor,), (original,))
    assert gaps == {}
    assert summaries[0].object_records[0].quantity_ids == (original.quantity_id,)
