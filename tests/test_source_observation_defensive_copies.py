"""Defensive copies of authority values are field-for-field clones that equal dataclasses.replace.

The source authority hands out a fresh copy of a frozen value on every read. The clones that replace
``dataclasses.replace`` on that hot path must build the identical object, share field values the same way,
reject unknown fields the same way, stay frozen, and refuse to be created for a class whose ``replace``
could do more than copy fields.
"""
from __future__ import annotations

import dataclasses
from dataclasses import InitVar, dataclass, field

import pytest

import pb_source_observation_authority as authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import (
    ObservationSelector,
    ProducerSnapshotRecord,
    SourceObservationAuthorityResult,
    SourceObservationRecord,
    SourceRevisionRecord,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from tests.test_raster_source_visibility_v1 import _hybrid_pdf


@pytest.fixture()
def instances():
    source = SourceVisibilityProducer(producer_method="defensive-copy-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="defensive-copy-doc",
        source_bytes=_hybrid_pdf(),
        source_locator="memory://defensive-copy.pdf",
        page_ids=("1",),
    )
    source.augment_with_raster_visible_segments(published.revision.revision_id, page_ids=("1",))
    store = source._producer._store
    snapshot = max(store.snapshots.values(), key=lambda s: s.producer_generation)
    observation_id = snapshot.observation_ids[0]
    key = (snapshot.snapshot_id, observation_id)
    if key not in store.verified_resolution_cache:
        source._producer.authority().resolve(
            ObservationSelector(
                document_id=snapshot.document_id,
                revision_id=snapshot.revision_id,
                source_sha256=snapshot.source_sha256,
                snapshot_id=snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
    return {
        "source": source,
        "published": published,
        "revision": store.revisions[snapshot.revision_id],
        "snapshot": snapshot,
        "record": store.observations[key],
        "result": store.verified_resolution_cache[key][4],
    }


CASES = [
    ("revision", SourceRevisionRecord, authority._clone_revision, {"producer_generation": 9, "source_locator": "x"}),
    ("snapshot", ProducerSnapshotRecord, authority._clone_snapshot, {"snapshot_id": "other", "producer_generation": 9}),
    ("record", SourceObservationRecord, authority._clone_observation, {"snapshot_id": "other", "producer_generation": 9}),
    ("result", SourceObservationAuthorityResult, authority._clone_result, {"snapshot": None, "semantic_enumeration_complete": True}),
]


@pytest.mark.parametrize("name, cls, clone, changes", CASES)
def test_clone_equals_replace_and_shares_field_values(instances, name, cls, clone, changes):
    original = instances[name]
    assert type(original) is cls
    for applied in ({}, changes):
        copy = clone(original, **applied)
        expected = dataclasses.replace(original, **applied)
        assert copy == expected
        assert type(copy) is cls and copy is not original
        for f in dataclasses.fields(cls):
            if f.name in applied:
                assert getattr(copy, f.name) is applied[f.name] or getattr(copy, f.name) == applied[f.name]
            else:
                assert getattr(copy, f.name) is getattr(original, f.name)
                assert getattr(copy, f.name) is getattr(expected, f.name)


@pytest.mark.parametrize("name, cls, clone, changes", CASES)
def test_unknown_field_is_a_type_error_like_replace(instances, name, cls, clone, changes):
    original = instances[name]
    with pytest.raises(TypeError):
        dataclasses.replace(original, not_a_field=1)
    with pytest.raises(TypeError):
        clone(original, not_a_field=1)


@pytest.mark.parametrize("name, cls, clone, changes", CASES)
def test_clone_is_frozen_and_isolated_from_the_original(instances, name, cls, clone, changes):
    original = instances[name]
    first = dataclasses.fields(cls)[0].name
    copy = clone(original)
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(copy, first, "tampered")
    before = getattr(original, first)
    object.__setattr__(copy, first, "poisoned")
    assert getattr(original, first) == before
    assert getattr(clone(original), first) == before


@pytest.mark.parametrize("name, clone", [("revision", authority._clone_revision), ("snapshot", authority._clone_snapshot)])
def test_stray_attributes_on_the_original_are_not_copied(instances, name, clone):
    original = instances[name]
    object.__setattr__(original, "stray", "not a declared field")
    try:
        copy = clone(original)
        assert not hasattr(copy, "stray")
        assert copy == dataclasses.replace(original)
    finally:
        object.__delattr__(original, "stray")


def test_cloning_is_refused_for_a_class_replace_could_treat_differently():
    @dataclass(frozen=True)
    class Plain:
        a: int
        b: int

    @dataclass(frozen=True)
    class WithPostInit:
        a: int
        b: int

        def __post_init__(self):
            pass

    @dataclass(frozen=True)
    class WithNonInitField:
        a: int
        b: int = field(init=False, default=0)

    @dataclass(frozen=True)
    class WithInitVar:
        a: int
        b: int
        c: InitVar[int] = 0

    @dataclass
    class NotFrozen:
        a: int
        b: int

    @dataclass(frozen=True)
    class OneField:
        a: int

    assert authority._shallow_cloner(Plain)(Plain(1, 2), b=5) == Plain(1, 5)
    for unsafe in (WithPostInit, WithNonInitField, WithInitVar, NotFrozen, OneField):
        with pytest.raises(TypeError):
            authority._shallow_cloner(unsafe)
    with pytest.raises(TypeError):
        authority._shallow_cloner(int)


def test_bind_helper_matches_replace_for_both_branches(instances):
    record, snapshot = instances["record"], instances["snapshot"]
    same = dataclasses.replace(record, snapshot_id=snapshot.snapshot_id, producer_generation=snapshot.producer_generation)
    other = dataclasses.replace(snapshot, snapshot_id="elsewhere", producer_generation=snapshot.producer_generation + 1)
    assert authority._bind_record_to_snapshot(same, snapshot) == dataclasses.replace(same)
    assert authority._bind_record_to_snapshot(same, snapshot) is not same
    rebound = authority._bind_record_to_snapshot(same, other)
    assert rebound == dataclasses.replace(same, snapshot_id="elsewhere", producer_generation=snapshot.producer_generation + 1)
    assert rebound is not same


def test_resolve_returns_what_the_replace_based_read_returned(instances):
    source = instances["source"]
    store = source._producer._store
    reader = source._producer.authority()
    checked = 0
    for snapshot in sorted(store.snapshots.values(), key=lambda s: s.producer_generation):
        revision = store.revisions[snapshot.revision_id]
        for observation_id in snapshot.observation_ids[:25]:
            selector = ObservationSelector(
                document_id=snapshot.document_id,
                revision_id=snapshot.revision_id,
                source_sha256=snapshot.source_sha256,
                snapshot_id=snapshot.snapshot_id,
                observation_id=observation_id,
            )
            stored = store.observations[(snapshot.snapshot_id, observation_id)]
            first = reader.resolve(selector)
            template = store.verified_resolution_cache[(snapshot.snapshot_id, observation_id)][4]
            expected = dataclasses.replace(
                template,
                source_revision=dataclasses.replace(revision),
                snapshot=dataclasses.replace(snapshot),
                observation=dataclasses.replace(
                    stored, snapshot_id=snapshot.snapshot_id, producer_generation=snapshot.producer_generation
                ),
            )
            second = reader.resolve(selector)
            assert first.status is EvidenceResolutionStatus.CORROBORATED
            assert first == expected and second == expected
            assert first is not second and first.observation is not second.observation
            assert first.snapshot is not second.snapshot and first.source_revision is not second.source_revision
            assert first.observation is not stored
            checked += 1
    # Every stored record of every generation is checked (up to 25 each). The
    # native visible generation stores no records of its own (its lines are
    # read views of the native records), so it holds the base id set.
    assert len(store.snapshots) >= 4
    assert checked == sum(min(25, len(s.observation_ids)) for s in store.snapshots.values())
    assert checked > 40
