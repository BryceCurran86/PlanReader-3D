"""Derived snapshot generations share unchanged immutable records; reads re-bind them.

Every derived generation used to clone all N base records into a new snapshot, which made
memory and time O(generations x N). Records are frozen and their payload hash covers content only
(never snapshot_id or producer_generation), so the same object is valid in every snapshot that
contains it. These tests pin that the store shares them, and that every public read still
returns exactly what a per-generation clone would have returned.
"""
from __future__ import annotations

from dataclasses import replace
from itertools import pairwise

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import (
    PRODUCER_INTEGRITY_FAILURE,
    ObservationSelector,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from tests.test_raster_source_visibility_v1 import _hybrid_pdf


@pytest.fixture()
def chain():
    source = SourceVisibilityProducer(
        producer_method="shared-record-test", producer_version="1"
    )
    published = source.ingest_native_pdf_bytes(
        document_id="shared-doc",
        source_bytes=_hybrid_pdf(),
        source_locator="memory://shared.pdf",
        page_ids=("1",),
    )
    source.augment_with_raster_visible_segments(
        published.revision.revision_id, page_ids=("1",)
    )
    store = source._producer._store
    snapshots = sorted(store.snapshots.values(), key=lambda s: s.producer_generation)
    assert len(snapshots) >= 3, "fixture must produce several derived generations"
    return source, published, store, snapshots


def _selector(published, snapshot, observation_id):
    return ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=snapshot.snapshot_id,
        observation_id=observation_id,
    )


def _resolve(source, published, snapshot, observation_id):
    return source._producer.authority().resolve(
        _selector(published, snapshot, observation_id)
    )


def _origin(store, snapshots, observation_id):
    """The record stored by the first generation that contains the observation."""
    for snapshot in snapshots:
        if observation_id in snapshot.observation_ids:
            return store.observations[(snapshot.snapshot_id, observation_id)]
    raise AssertionError(observation_id)


def _membership_history(chain):
    source, published, store, snapshots = chain
    parent = published.snapshot.observation_ids[0]
    latest = snapshots[-1]
    for index in range(8):
        latest = source._producer.publish_derived_observation(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            base_snapshot_id=latest.snapshot_id,
            page_id="1", source_partition_id="page:1",
            observation_kind="synthetic_membership_annotation",
            source_primitive_ref=f"membership-test:{index}",
            parent_observation_ids=(parent,), geometry=(0., 0., 1., 1.),
            origin_kind="synthetic_membership_annotation",
        )
        snapshots.append(latest)
    return source, published, store, snapshots, parent


def test_membership_hints_remain_bounded_after_derived_commits(chain):
    source, published, store, snapshots, parent = _membership_history(chain)
    assert len(store.snapshots) == len(snapshots)
    assert len(store.snapshot_observation_id_sets) <= 3
    inventories = {snapshot.snapshot_id: snapshot.observation_ids for snapshot in snapshots}
    for snapshot in snapshots:
        result = _resolve(source, published, snapshot, parent)
        assert result.status is EvidenceResolutionStatus.CORROBORATED
        assert result.observation.snapshot_id == snapshot.snapshot_id
        assert result.observation.producer_generation == snapshot.producer_generation
        assert store.snapshots[snapshot.snapshot_id].observation_ids == inventories[snapshot.snapshot_id]
        assert len(store.snapshot_observation_id_sets) <= 3
    # Membership hints, unlike immutable source history, can be discarded.
    store.snapshot_observation_id_sets.clear()
    assert _resolve(source, published, snapshots[0], parent).status is EvidenceResolutionStatus.CORROBORATED
    assert len(store.snapshots) == len(snapshots)


def test_evicted_membership_rechecks_a_replaced_snapshot_inventory(chain):
    source, published, store, snapshots, parent = _membership_history(chain)
    earliest = snapshots[0]
    assert earliest.snapshot_id not in store.snapshot_observation_id_sets
    changed = replace(earliest, observation_ids=tuple(x for x in earliest.observation_ids if x != parent))
    store.snapshots[earliest.snapshot_id] = changed
    try:
        result = _resolve(source, published, changed, parent)
        assert result.status is not EvidenceResolutionStatus.CORROBORATED
        assert result.observation is None
    finally:
        store.snapshots[earliest.snapshot_id] = earliest
    assert _resolve(source, published, earliest, parent).status is EvidenceResolutionStatus.CORROBORATED


def test_unchanged_records_are_shared_objects_across_generations(chain) -> None:
    _source, _published, store, snapshots = chain
    for earlier, later in pairwise(snapshots):
        for observation_id in earlier.observation_ids:
            assert (
                store.observations[(earlier.snapshot_id, observation_id)]
                is store.observations[(later.snapshot_id, observation_id)]
            )
    # One stored object per observation id: no per-generation clones exist.
    distinct_objects = {id(record) for record in store.observations.values()}
    distinct_ids = {observation_id for _, observation_id in store.observations}
    assert len(distinct_objects) == len(distinct_ids)
    # Per-snapshot entries and fingerprints are still keyed per snapshot.
    for snapshot in snapshots:
        for observation_id in snapshot.observation_ids:
            key = (snapshot.snapshot_id, observation_id)
            assert key in store.observations and key in store.record_fingerprints
    # Storage is one object per observation, not one copy per generation.
    assert store.observations.stored_entry_count() == len(distinct_ids)
    assert store.record_fingerprints.stored_entry_count() == len(distinct_ids)
    assert len(store.observations) == sum(len(snapshot.observation_ids) for snapshot in snapshots)


def test_every_read_matches_what_a_per_generation_clone_returned(chain) -> None:
    source, published, store, snapshots = chain
    for snapshot in snapshots:
        for observation_id in snapshot.observation_ids:
            result = _resolve(source, published, snapshot, observation_id)
            assert result.status is EvidenceResolutionStatus.CORROBORATED
            observation = result.observation
            assert observation.snapshot_id == snapshot.snapshot_id
            assert observation.producer_generation == snapshot.producer_generation
            expected = replace(
                _origin(store, snapshots, observation_id),
                snapshot_id=snapshot.snapshot_id,
                producer_generation=snapshot.producer_generation,
            )
            assert observation == expected
            # Second read (identity-bound cache hit) is identical and still a fresh copy.
            again = _resolve(source, published, snapshot, observation_id).observation
            assert again == expected and again is not observation


def test_bulk_visible_reader_binds_records_to_the_queried_snapshot(chain) -> None:
    source, _published, store, snapshots = chain
    current = source.published_snapshot_for_revision(snapshots[-1].revision_id)
    assert current is not None
    rows = source.authority().authenticated_visible_observations(current)
    assert rows
    inherited = 0
    for observation_id, record in rows:
        parent_id = source._visibility_receipts.get(
            (current.snapshot.snapshot_id, observation_id)
        )
        stored_id = parent_id if parent_id is not None else observation_id
        stored = store.observations[(current.snapshot.snapshot_id, stored_id)]
        inherited += stored.snapshot_id != current.snapshot.snapshot_id
        assert record.snapshot_id == current.snapshot.snapshot_id
        assert record.producer_generation == current.snapshot.producer_generation
        assert record is not stored
        assert record.geometry == stored.geometry
        if parent_id is None:
            assert replace(
                stored,
                snapshot_id=current.snapshot.snapshot_id,
                producer_generation=current.snapshot.producer_generation,
            ) == record
    assert inherited > 0, "fixture must exercise records inherited from older generations"


def test_public_reads_are_defensive_copies_of_shared_records(chain) -> None:
    source, published, store, snapshots = chain
    observation_id = snapshots[0].observation_ids[0]
    stored = store.observations[(snapshots[0].snapshot_id, observation_id)]
    original_text = stored.raw_text
    # A read at a later generation re-binds the shared record; a read at the
    # generation that stored it needs no re-binding. Both hand out copies.
    for read_at in (snapshots[-1], snapshots[0]):
        handed_out = _resolve(source, published, read_at, observation_id).observation
        assert handed_out is not stored
        object.__setattr__(handed_out, "raw_text", "poisoned")
        for snapshot in snapshots:
            reread = _resolve(source, published, snapshot, observation_id)
            assert reread.observation.raw_text == original_text
        assert stored.raw_text == original_text


def test_tampering_one_generation_leaves_the_others_resolvable(chain) -> None:
    source, published, store, snapshots = chain
    observation_id = snapshots[0].observation_ids[0]
    first, last = snapshots[0], snapshots[-1]
    for target in (last, first):
        key = (target.snapshot_id, observation_id)
        prior = store.observations[key]
        store.observations[key] = replace(prior, raw_text="tampered")
        try:
            for snapshot in snapshots:
                result = _resolve(source, published, snapshot, observation_id)
                if snapshot is target:
                    assert result.status is EvidenceResolutionStatus.CONFLICT
                    assert PRODUCER_INTEGRITY_FAILURE in result.reason_codes
                else:
                    assert result.status is EvidenceResolutionStatus.CORROBORATED
        finally:
            store.observations[key] = prior
        assert (
            _resolve(source, published, target, observation_id).status
            is EvidenceResolutionStatus.CORROBORATED
        )


def test_popping_a_parent_from_one_generation_only_breaks_that_generation(chain) -> None:
    source, published, store, snapshots = chain
    last = snapshots[-1]
    derived = [
        observation_id
        for observation_id in last.observation_ids
        if store.observations[(last.snapshot_id, observation_id)].derivation_parent_ids
    ]
    assert derived
    child_id = derived[0]
    parent_id = store.observations[(last.snapshot_id, child_id)].derivation_parent_ids[0]
    key = (last.snapshot_id, parent_id)
    parent = store.observations.pop(key)
    try:
        broken = _resolve(source, published, last, child_id)
        assert broken.status is not EvidenceResolutionStatus.CORROBORATED
        # Older generations still hold their own entry for the parent.
        holders = [s for s in snapshots[:-1] if (s.snapshot_id, parent_id) in store.observations]
        assert holders
    finally:
        store.observations[key] = parent
    assert _resolve(source, published, last, child_id).status is EvidenceResolutionStatus.CORROBORATED
