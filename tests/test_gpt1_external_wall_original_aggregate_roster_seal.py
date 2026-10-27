"""Real per-wall source issuer must retain the complete original aggregate seal.

These are source-shaped negative tests through the actual per-wall issuer and
sealed consumer, not new physical-wall or material measurement authority.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_live_external_wall_surface_area_quantity_publication import (
    publish_live_per_wall_surface_area_quantities,
    seal_live_per_wall_surface_area_run,
)
from tests.test_gpt1_source_closed_external_per_wall_surface_m2 import _produced


def _assert_unsealable(produced):
    assert publish_live_per_wall_surface_area_quantities(produced) == ()
    with pytest.raises(ValueError, match="no source-complete original external wall"):
        seal_live_per_wall_surface_area_run(
            produced, workspace_id=7, project_id="source-wall-roster-test",
        )


@pytest.mark.parametrize("roster", (
    "gross_geometry_record_ids",
    "whole_wall_role_record_ids",
    "physical_void_record_ids",
    "opening_universe_record_ids",
))
def test_replaced_original_roster_cannot_launder_per_wall_area(roster):
    produced = _produced()
    original = getattr(produced, roster)
    foreign = ("foreign-original-receipt", *original[1:]) if original else (
        "foreign-original-receipt",
    )
    _assert_unsealable(replace(produced, **{roster: foreign}))
    assert publish_live_per_wall_surface_area_quantities(produced)


@pytest.mark.parametrize("roster", (
    "gross_geometry_record_ids",
    "whole_wall_role_record_ids",
    "physical_void_record_ids",
    "opening_universe_record_ids",
))
def test_replaced_aggregate_metadata_roster_cannot_launder_area(roster):
    produced = _produced()
    aggregate = produced.quantity_evidence
    assert aggregate is not None
    old = aggregate.metadata[roster]
    foreign = ("foreign-original-receipt", *old[1:]) if old else (
        "foreign-original-receipt",
    )
    changed = replace(
        aggregate, metadata={**aggregate.metadata, roster: foreign},
    )
    _assert_unsealable(replace(produced, quantity_evidence=changed))


def test_joint_publication_and_metadata_replay_cannot_inherit_old_source_id():
    produced = _produced()
    aggregate = produced.quantity_evidence
    assert aggregate is not None
    foreign = ("foreign-original-gross",)
    changed = replace(
        produced,
        gross_geometry_record_ids=foreign,
        quantity_evidence=replace(
            aggregate,
            metadata={**aggregate.metadata, "gross_geometry_record_ids": foreign},
        ),
    )
    _assert_unsealable(changed)


def test_original_aggregate_evidence_census_cannot_drop_universe_receipt():
    produced = _produced()
    aggregate = produced.quantity_evidence
    assert aggregate is not None
    assert aggregate.evidence_ids
    changed = replace(
        aggregate, evidence_ids=aggregate.evidence_ids[:-1],
    )
    _assert_unsealable(replace(produced, quantity_evidence=changed))


def test_original_aggregate_evidence_census_cannot_reorder_receipts():
    produced = _produced()
    aggregate = produced.quantity_evidence
    assert aggregate is not None
    assert len(aggregate.evidence_ids) > 1
    changed = replace(
        aggregate, evidence_ids=tuple(reversed(aggregate.evidence_ids)),
    )
    _assert_unsealable(replace(produced, quantity_evidence=changed))


def test_original_opening_universe_cannot_be_missing_even_without_voids():
    produced = _produced()
    aggregate = produced.quantity_evidence
    assert aggregate is not None
    assert produced.opening_universe_record_ids
    _assert_unsealable(replace(
        produced,
        opening_universe_record_ids=(),
        quantity_evidence=replace(
            aggregate,
            metadata={**aggregate.metadata, "opening_universe_record_ids": ()},
        ),
    ))


def test_aggregate_id_must_equal_original_producer_contract():
    produced = _produced()
    aggregate = produced.quantity_evidence
    assert aggregate is not None
    _assert_unsealable(replace(
        produced,
        quantity_evidence=replace(aggregate, quantity_id="forged-aggregate-id"),
    ))


def test_original_producer_to_per_wall_to_sealed_is_unchanged_and_deterministic():
    produced = _produced()
    original_quantity = produced.quantity_evidence
    original_walls = produced.canonical_walls
    before = publish_live_per_wall_surface_area_quantities(produced)
    assert len(before) == len(produced.external_wall_ids) > 0
    run = seal_live_per_wall_surface_area_run(
        produced, workspace_id=7, project_id="source-wall-roster-test",
    )
    assert len(run.quantities) == len(before)
    assert all(q.lineage_ok and not q.abstained for q in run.quantities)
    assert run.to_json() == seal_live_per_wall_surface_area_run(
        produced, workspace_id=7, project_id="source-wall-roster-test",
    ).to_json()
    assert before == publish_live_per_wall_surface_area_quantities(produced)
    assert produced.quantity_evidence == original_quantity
    assert produced.canonical_walls == original_walls
