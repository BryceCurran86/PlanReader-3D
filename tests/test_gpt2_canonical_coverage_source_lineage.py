"""Fail-closed live canonical quantity provenance across original revisions."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest

from pb_live_canonical_coverage_registry import collect_live_canonical_coverage
from pb_live_ceiling_area_quantity_publication import publish_live_ceiling_area_quantities
from pb_live_floor_area_quantity_publication import publish_live_floor_area_quantities
from tests.test_live_ceiling_area_quantity_publication import _ceiling, _result
from tests.test_live_floor_area_quantity_publication_integrity import _claim_with, _source_area
from tests.test_live_floor_finish_area_source_closed_export import _floor, _quantity


def _summaries(objects, quantities):
    return collect_live_canonical_coverage(
        objects=objects, quantities=quantities, output_rows=(),
        registry_run_scope="gpt2-source-lineage-integrity",
    )


def test_verified_original_ceiling_and_floor_quantity_survive_exact_lineage():
    ceiling = _ceiling()
    ceiling_quantity = publish_live_ceiling_area_quantities(_result())[0]
    floor_claim = _claim_with(_source_area())
    floor_quantity = publish_live_floor_area_quantities(floor_claim)[0]
    ceiling_summaries, ceiling_gaps = _summaries((ceiling,), (ceiling_quantity,))
    floor_summaries, floor_gaps = _summaries(floor_claim.canonical_floors, (floor_quantity,))
    assert ceiling_gaps == floor_gaps == {}
    assert ceiling_summaries[0].object_records[0].quantity_ids == (ceiling_quantity.quantity_id,)
    assert floor_summaries[0].object_records[0].quantity_ids == (floor_quantity.quantity_id,)


@pytest.mark.parametrize("field,wrong", [
    ("document_id", "wrong-document"),
    ("revision_id", "replayed-revision"),
    ("source_sha256", "b" * 64),
    ("source_sha256", ""),
    ("snapshot_id", "foreign-physical-snapshot"),
])
def test_explicit_foreign_ceiling_lineage_is_not_credited_as_quantified(field, wrong):
    ceiling = _ceiling()
    q = publish_live_ceiling_area_quantities(_result())[0]
    changed = replace(q, metadata={**q.metadata, field: wrong})
    prior = deepcopy(changed.to_dict())
    summaries, gaps = _summaries((ceiling,), (changed,))
    assert gaps == {"ceiling": ["quantity_source_lineage_conflict"]}
    assert len(summaries) == 1
    assert summaries[0].object_records[0].quantity_ids == ()
    assert changed.to_dict() == prior


@pytest.mark.parametrize("field,wrong", [
    ("document_id", "wrong-document"),
    ("revision_id", "stale-floor-revision"),
    ("source_sha256", "b" * 64),
    ("snapshot_id", "foreign-physical-snapshot"),
])
def test_explicit_foreign_floor_lineage_is_not_credited_as_quantified(field, wrong):
    claim = _claim_with(_source_area())
    q = publish_live_floor_area_quantities(claim)[0]
    altered = replace(q, metadata={**q.metadata, field: wrong})
    summaries, gaps = _summaries(claim.canonical_floors, (altered,))
    assert gaps == {"floor": ["quantity_source_lineage_conflict"]}
    assert summaries[0].object_records[0].quantity_ids == ()


def test_foreign_quantity_cannot_poison_independent_valid_surface():
    first = _ceiling()
    second = replace(
        first,
        canonical_ceiling_id="canonical-ceiling-2",
    )
    original_q = publish_live_ceiling_area_quantities(_result())[0]
    second_q = publish_live_ceiling_area_quantities(_result(ceiling=second))[0]
    stale_q = replace(original_q, metadata={
        **original_q.metadata,
        "source_sha256": "b" * 64,
    })
    summaries, gaps = _summaries((first, second), (stale_q, second_q))
    assert gaps == {"ceiling": ["quantity_source_lineage_conflict"]}
    ids_by_object = {
        rec.object_id: rec.quantity_ids
        for summary in summaries
        for rec in summary.object_records
    }
    assert ids_by_object[first.canonical_ceiling_id] == ()
    assert ids_by_object[second.canonical_ceiling_id] == (second_q.quantity_id,)


def test_uppercase_same_source_hash_is_same_original_source():
    ceil = _ceiling()
    q = publish_live_ceiling_area_quantities(_result())[0]
    uppercase = replace(q, metadata={
        **q.metadata,
        "source_sha256": q.metadata["source_sha256"].upper(),
    })
    summaries, gaps = _summaries((ceil,), (uppercase,))
    assert gaps == {}
    assert summaries[0].object_records[0].quantity_ids == (q.quantity_id,)


def test_unrelated_cross_view_semantic_snapshot_is_not_a_foreign_canonical_surface():
    # The semantic source's independent snapshot is not the canonical physical
    # floor snapshot. Only explicit canonical *reissues* bind that exact scope.
    floor = _floor()
    q = _quantity()
    q = replace(q, metadata={
        **q.metadata,
        "snapshot_id": "separately-proven-finish-sheet-snapshot",
    })
    summaries, gaps = _summaries((floor,), (q,))
    assert gaps == {}
    assert summaries[0].object_records[0].quantity_ids == (q.quantity_id,)


def test_optional_absent_source_metadata_does_not_invent_an_automatic_source_conflict():
    floor = _floor()
    q = _quantity()
    stripped = replace(q, metadata={
        key: value for key, value in q.metadata.items()
        if key not in {"document_id", "source_sha256", "revision_id"}
    })
    summaries, gaps = _summaries((floor,), (stripped,))
    assert gaps == {}
    assert summaries[0].object_records[0].quantity_ids == (q.quantity_id,)
