"""Repeated source proofs must not copy the whole drawing or the PDF again."""

from dataclasses import replace

from pb_source_observation_authority import ObservationSelector
from test_wall_visible_observation_page_index import _source


def test_republish_keeps_the_stored_source_bytes_object():
    source, published, _ = _source(page_count=2)
    store = source._producer._store
    revision_id = published.revision.revision_id
    stored = store.source_bytes_by_revision[revision_id]
    source.augment_with_raster_visible_segments(revision_id, page_ids=("1",))
    assert store.source_bytes_by_revision[revision_id] is stored


def test_page_proof_checks_every_page_and_keeps_one_page():
    source, published, _ = _source(page_count=2)
    authority = source.authority()
    full = authority.authenticated_visible_observations(published)
    pages = {record.page_id for _observation_id, record in full}
    assert pages == {"1", "2"}
    store = source._producer._store
    assert len(store.visible_authentication_cache) == 1
    page = authority.authenticated_visible_observations(
        published, bind_page_id="1"
    )
    assert {record.page_id for _observation_id, record in page} == {"1"}
    assert page == tuple(
        row for row in full if row[1].page_id == "1"
    )
    assert store.visible_authentication_cache == {}
    page_two = next(
        observation_id
        for observation_id, record in full
        if record.page_id == "2"
    )
    key = (published.snapshot.snapshot_id, page_two)
    prior = store.observations[key]
    store.observations[key] = replace(prior, geometry=tuple(
        value + 3.0 for value in prior.geometry
    ))
    try:
        try:
            authority.authenticated_visible_observations(
                published, bind_page_id="1"
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError("a damaged observation on another page must fail")
    finally:
        store.observations[key] = prior


def test_second_page_bind_does_not_walk_the_store_again():
    source, published, _ = _source(page_count=2)
    authority = source.authority()
    first = authority.authenticated_visible_observations(
        published, bind_page_id="1"
    )
    store = source._producer._store
    original = store.observations.get
    calls = {"n": 0}

    def counting(key, default=None):
        calls["n"] += 1
        if default is None:
            return original(key)
        return original(key, default)

    store.observations.get = counting
    second = authority.authenticated_visible_observations(
        published, bind_page_id="2"
    )
    assert calls["n"] == 0
    assert {record.page_id for _observation_id, record in first} == {"1"}
    assert {record.page_id for _observation_id, record in second} == {"2"}
    full = tuple(
        (observation_id, record)
        for observation_id, record in authority.authenticated_visible_observations(
            published
        )
        if record.page_id == "2"
    )
    assert second == full


def test_second_visible_authentication_reuses_the_bound_rows():
    source, published, _ = _source(page_count=2)
    authority = source.authority()
    first = authority.authenticated_visible_observations(published)
    second = authority.authenticated_visible_observations(published)
    assert second == first
    assert second is not first
    assert second[0][1] is first[0][1]
    assert len(source._producer._store.visible_authentication_cache) == 1


def test_mutated_returned_row_is_rebuilt_from_the_store():
    source, published, _ = _source(page_count=1)
    authority = source.authority()
    first = authority.authenticated_visible_observations(published)
    original = first[0][1].raw_text
    object.__setattr__(first[0][1], "raw_text", "tampered-returned-row")
    fresh = authority.authenticated_visible_observations(published)
    assert fresh[0][1] is not first[0][1]
    assert fresh[0][1].raw_text == original
    assert fresh != first


def test_opening_snapshot_records_keep_only_the_seed_page():
    source, published, _ = _source(page_count=2)
    authority = source.authority()
    rows = authority.authenticated_visible_observations(published)
    assert {str(record.page_id) for _observation_id, record in rows} == {"1", "2"}
    physical = source.physical_opening_authority()
    page_one = next(
        observation_id
        for observation_id, record in rows
        if str(record.page_id) == "1"
    )
    selector = ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=page_one,
    )
    resolved = authority.resolve_visible(selector)
    records, failures = physical._visible_snapshot_records(resolved)
    assert not failures
    assert records
    assert {str(record.page_id) for record in records} == {"1"}


def test_replaced_competitor_on_another_page_is_not_served_from_cache():
    source, published, _ = _source(page_count=2)
    authority = source.authority()
    rows = authority.authenticated_visible_observations(published)
    competitor = next(
        observation_id
        for observation_id, record in rows
        if str(record.page_id) == "2"
    )
    key = (published.snapshot.snapshot_id, competitor)
    store = source._producer._store
    prior = store.observations[key]
    store.observations[key] = replace(
        prior, geometry=tuple(float(value) + 3 for value in prior.geometry)
    )
    try:
        try:
            authority.authenticated_visible_observations(published)
        except RuntimeError:
            return
        raise AssertionError("replaced competitor geometry was accepted")
    finally:
        store.observations[key] = prior
