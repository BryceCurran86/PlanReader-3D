"""The visible-segment generation keeps the snapshot identity that publish_derived_observations always gave it.

Every id issued from a snapshot (opening host bindings, quantities, run fingerprints) hashes its snapshot id, and the
signed Lot16 and Maryborough receipts pin those fingerprints. Visible lines are read views of native records, so the
generation stores no new records, but its snapshot id must still hash the visible observation ids exactly as the old
batch publication did. `fork_derived_snapshot` once hashed an empty list and every signed id changed.
"""
from __future__ import annotations

import pytest

from pb_migration_contracts import stable_contract_id
from pb_source_observation_authority import ProducerIntegrityError
from pb_source_visibility_authority import SourceVisibilityProducer
from tests.test_raster_source_visibility_v1 import _hybrid_pdf


def _published():
    source = SourceVisibilityProducer(
        producer_method="visible-snapshot-identity-test", producer_version="1"
    )
    published = source.ingest_native_pdf_bytes(
        document_id="visible-identity-doc",
        source_bytes=_hybrid_pdf(),
        source_locator="memory://visible-identity.pdf",
        page_ids=("1",),
    )
    return source, published


def test_visible_generation_snapshot_id_hashes_the_visible_observation_ids():
    _source, published = _published()
    snapshot = published.snapshot
    assert published.visible_observation_ids, "the fixture must contain native visible lines"
    assert snapshot.parent_snapshot_id
    expected = stable_contract_id(
        "source_snapshot",
        {
            "revision_id": snapshot.revision_id,
            "base_snapshot_id": snapshot.parent_snapshot_id,
            "derived_observation_ids": tuple(sorted(published.visible_observation_ids)),
            "generation": snapshot.producer_generation,
        },
        digest_chars=32,
    )
    assert snapshot.snapshot_id == expected


def test_visible_generation_snapshot_id_changes_when_the_visible_ids_change():
    source, published = _published()
    producer = source._producer
    base = published.snapshot.parent_snapshot_id
    first = producer.fork_derived_snapshot(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        base_snapshot_id=base,
        derived_observation_ids=["source_observation_a", "source_observation_b"],
    )
    # same ids in another order: same hash input except for the (monotonic) generation counter
    reordered = producer.fork_derived_snapshot(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        base_snapshot_id=base,
        derived_observation_ids=["source_observation_b", "source_observation_a"],
    )
    other = producer.fork_derived_snapshot(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        base_snapshot_id=base,
        derived_observation_ids=["source_observation_a", "source_observation_c"],
    )
    ids = {first.snapshot_id, reordered.snapshot_id, other.snapshot_id}
    assert len(ids) == 3  # generation differs, so even equal id sets never collide
    expected_first = stable_contract_id(
        "source_snapshot",
        {
            "revision_id": first.revision_id,
            "base_snapshot_id": base,
            "derived_observation_ids": ("source_observation_a", "source_observation_b"),
            "generation": first.producer_generation,
        },
        digest_chars=32,
    )
    expected_reordered = stable_contract_id(
        "source_snapshot",
        {
            "revision_id": reordered.revision_id,
            "base_snapshot_id": base,
            "derived_observation_ids": ("source_observation_a", "source_observation_b"),
            "generation": reordered.producer_generation,
        },
        digest_chars=32,
    )
    assert first.snapshot_id == expected_first
    assert reordered.snapshot_id == expected_reordered  # input order never matters, only the sorted id set


def test_fork_requires_a_non_empty_set_of_distinct_derived_ids():
    source, published = _published()
    kwargs = dict(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        base_snapshot_id=published.snapshot.parent_snapshot_id,
    )
    with pytest.raises(ValueError, match="non-empty"):
        source._producer.fork_derived_snapshot(derived_observation_ids=[], **kwargs)
    with pytest.raises(ProducerIntegrityError, match="duplicate"):
        source._producer.fork_derived_snapshot(
            derived_observation_ids=["source_observation_a", "source_observation_a"], **kwargs
        )
