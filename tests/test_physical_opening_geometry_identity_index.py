"""Physical opening geometry identity: the per-snapshot lookup selects exactly the scan's records.

``_physical_opening_geometry_identity`` used to walk every visible record of the snapshot
once per candidate observation (quadratic over a page). The lookup variant must return
exactly what the scan returns for every candidate, may never outlive the records tuple it
was built from, must be dropped with the other snapshot caches after a failed source
batch, and must step aside whenever an observation id repeats.
"""
from __future__ import annotations

import random
from types import SimpleNamespace

from test_wall_visible_observation_page_index import _source as _wall_source

import pb_physical_opening_authority as module
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    PhysicalOpeningAuthority,
    _physical_opening_geometry_identity,
)
from pb_source_observation_authority import ObservationSelector


def _record(observation_id, geometry):
    return SimpleNamespace(observation_id=observation_id, geometry=geometry)


def _candidate(*observation_ids):
    return SimpleNamespace(source_observation_ids=tuple(observation_ids))


def _index(records):
    return {str(record.observation_id): record for record in records}


def _synthetic_records(count=40):
    rng = random.Random(20261014)
    records = []
    for number in range(count):
        x = round(rng.uniform(0, 400), 3)
        y = round(rng.uniform(0, 400), 3)
        length = rng.choice((0.0, 12.5, 30.0, 61.0))
        records.append(
            _record(
                f"obs-{number}",
                (x, y, x + length, y) if number % 2 else (x, y, x, y + length),
            )
        )
    # A non-line record (3 coordinates) and a non-finite one.
    records.append(_record("obs-bad-arity", (1.0, 2.0, 3.0)))
    records.append(_record("obs-nan", (0.0, 0.0, float("nan"), 1.0)))
    return tuple(records)


def test_indexed_selection_matches_the_scan_for_every_support_shape():
    records = _synthetic_records()
    index = _index(records)
    rng = random.Random(7)
    ids = [record.observation_id for record in records]
    candidates = [
        _candidate(*rng.sample(ids, rng.choice((1, 2, 3, 6))))
        for _ in range(200)
    ]
    candidates += [
        _candidate(),                          # empty support
        _candidate("obs-1", "not-in-records"),  # one id missing
        _candidate("obs-1", "obs-1", "obs-3"),  # repeated declaration
        _candidate("obs-bad-arity", "obs-2"),
        _candidate("obs-nan", "obs-2"),
        _candidate(1, 2, 3),                    # non-string ids stringify identically
    ]
    non_empty = 0
    for candidate in candidates:
        scan = _physical_opening_geometry_identity(candidate, records)
        looked_up = _physical_opening_geometry_identity(candidate, records, index)
        assert looked_up == scan
        non_empty += bool(scan)
    assert non_empty > 20, "the sample must include real positive identities"


def test_indexed_selection_is_invariant_to_record_and_support_order():
    records = _synthetic_records()
    candidate = _candidate("obs-3", "obs-5", "obs-8", "obs-13")
    reference = _physical_opening_geometry_identity(candidate, records, _index(records))
    assert reference
    shuffled = list(records)
    random.Random(3).shuffle(shuffled)
    assert _physical_opening_geometry_identity(
        candidate, tuple(shuffled), _index(shuffled)
    ) == reference
    reordered = _candidate("obs-13", "obs-8", "obs-5", "obs-3")
    assert _physical_opening_geometry_identity(
        reordered, records, _index(records)
    ) == reference


def _authority_and_seed():
    source, published, _payload = _wall_source(page_count=1)
    authority = source.physical_opening_authority()
    snapshot = published.snapshot
    seed = SimpleNamespace(snapshot=snapshot)
    return source, published, authority, seed


def test_index_is_bound_to_the_exact_records_tuple():
    _source, _published, authority, seed = _authority_and_seed()
    first = _synthetic_records(10)
    built = authority._visible_records_by_observation_id(seed, first)
    assert built == _index(first)
    assert authority._visible_records_by_observation_id(seed, first) is built
    # A different tuple for the same snapshot key rebuilds, never reuses.
    second = first[:5] + (_record("obs-extra", (0.0, 0.0, 9.0, 0.0)),)
    rebuilt = authority._visible_records_by_observation_id(seed, second)
    assert rebuilt == _index(second)
    assert "obs-extra" in rebuilt and "obs-9" not in rebuilt
    # An equal-content but distinct tuple object also rebuilds: the binding is
    # by identity of the cached records tuple, never by equality.
    equal_copy = tuple(list(second))
    assert equal_copy == second and equal_copy is not second
    rebuilt_again = authority._visible_records_by_observation_id(seed, equal_copy)
    assert rebuilt_again == rebuilt and rebuilt_again is not rebuilt


def test_repeated_observation_id_disables_the_index():
    _source, _published, authority, seed = _authority_and_seed()
    records = (
        _record("dup", (0.0, 0.0, 10.0, 0.0)),
        _record("other", (0.0, 5.0, 10.0, 5.0)),
        _record("dup", (0.0, 9.0, 10.0, 9.0)),
    )
    assert authority._visible_records_by_observation_id(seed, records) is None
    # The scan fallback keeps both duplicate geometries.
    candidate = _candidate("dup", "other")
    assert len(_physical_opening_geometry_identity(candidate, records)) == 3


def test_snapshotless_seed_has_no_index():
    _source, _published, authority, _seed = _authority_and_seed()
    assert authority._visible_records_by_observation_id(
        SimpleNamespace(snapshot=None), _synthetic_records(3)
    ) is None


def test_failed_source_batch_evicts_only_the_affected_snapshot_index():
    _source, _published, authority, _seed = _authority_and_seed()
    affected = ("doc", "rev", "sha", "snapshot-affected")
    unaffected = ("doc", "rev", "sha", "snapshot-other")
    authority._visible_snapshot_record_index_cache[affected] = ((), {})
    authority._visible_snapshot_record_index_cache[unaffected] = ((), {})
    authority._invalidate_snapshot_caches_after_failed_source_batch(affected[3])
    assert affected not in authority._visible_snapshot_record_index_cache
    assert unaffected in authority._visible_snapshot_record_index_cache


def _prove_all(authority, published, page_id="1"):
    results = {}
    rows = authority._source_visibility_authority.authenticated_visible_observations(
        published
    )
    for observation_id, record in rows:
        if str(record.page_id) != page_id:
            continue
        results[observation_id] = authority.prove_existence(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
    return results


def _fingerprint(result):
    record = result.existence_record
    return (
        result.status,
        result.proposition,
        tuple(result.reason_codes),
        None if record is None else record.record_id,
        None if record is None else tuple(record.source_observation_ids),
    )


def test_prove_existence_is_identical_with_and_without_the_lookup(monkeypatch):
    source, published, _payload = _wall_source(page_count=1)
    with_lookup = PhysicalOpeningAuthority.from_source_visibility_producer(source)
    indexed = _prove_all(with_lookup, published)
    assert any(
        r.status is EvidenceResolutionStatus.CORROBORATED
        and r.proposition == PHYSICAL_OPENING_EXISTS
        for r in indexed.values()
    ), "fixture must contain proven openings so the identity path is exercised"
    assert with_lookup._visible_snapshot_record_index_cache

    monkeypatch.setattr(
        module.PhysicalOpeningAuthority,
        "_visible_records_by_observation_id",
        lambda self, seed, records: None,
    )
    without_lookup = PhysicalOpeningAuthority.from_source_visibility_producer(source)
    scanned = _prove_all(without_lookup, published)
    assert not without_lookup._visible_snapshot_record_index_cache
    assert set(indexed) == set(scanned)
    for observation_id in indexed:
        assert _fingerprint(indexed[observation_id]) == _fingerprint(
            scanned[observation_id]
        )
