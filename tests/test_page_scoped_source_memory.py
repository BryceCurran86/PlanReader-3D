"""Repeated source proofs must not copy the whole drawing or the PDF again."""

from dataclasses import replace
import pytest

from pb_source_observation_authority import ObservationSelector
import pb_source_visibility_authority as visibility_module
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
    parent_id = authority._visibility_receipts[
        (published.snapshot.snapshot_id, page_two)
    ]
    key = (published.snapshot.snapshot_id, parent_id)
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
    if key not in store.observations:
        key = (published.snapshot.snapshot_id, authority._visibility_receipts[key])
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


def test_repeated_page_proof_reuses_aliases_but_not_the_return_tuple(monkeypatch):
    source, published, _ = _source(page_count=2)
    authority = source.authority()
    first = authority.authenticated_visible_observations(published, bind_page_id="1")
    original = visibility_module._native_visible_alias
    calls = []
    def counting(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(visibility_module, "_native_visible_alias", counting)
    second = authority.authenticated_visible_observations(published, bind_page_id="1")
    assert second == first
    assert second is not first
    assert second[0][1] is first[0][1]
    assert calls == [], "unchanged source aliases were materialized again"


def test_mutated_page_bound_clone_is_rebuilt_from_its_source():
    source, published, _ = _source(page_count=2)
    authority = source.authority()
    first = authority.authenticated_visible_observations(published, bind_page_id="1")
    geometry = first[0][1].geometry
    object.__setattr__(first[0][1], "geometry", (900.0, 900.0, 1000.0, 900.0))
    fresh = authority.authenticated_visible_observations(published, bind_page_id="1")
    assert fresh[0][1].geometry == geometry
    assert fresh[0][1] is not first[0][1]


def test_page_alias_cache_replaces_the_previous_page():
    source, published, _ = _source(page_count=2)
    authority = source.authority()
    store = source._producer._store
    for page in ("1", "2", "1"):
        rows = authority.authenticated_visible_observations(published, bind_page_id=page)
        cached = store.visible_page_bound_rows
        assert cached[0] == published.snapshot.snapshot_id
        assert cached[1] == page
        assert cached[4] == rows
        assert {record.page_id for _, record in cached[4]} == {page}


@pytest.mark.parametrize("bind_page", (None, "1"))
@pytest.mark.parametrize("changed_page", ("1", "2"))
def test_cached_proof_rejects_changed_native_origin_receipt(bind_page, changed_page):
    source, published, _ = _source(page_count=2)
    authority = source.authority()
    all_rows = authority.authenticated_visible_observations(published)
    changed = next(oid for oid, row in all_rows if row.page_id == changed_page)
    authority.authenticated_visible_observations(published, bind_page_id=bind_page)
    key = (published.snapshot.snapshot_id, changed)
    old = authority._visible_origin_kinds[key]
    replacement = visibility_module.RECTANGULAR_CLIP_VISIBLE_SEGMENT_ORIGIN_KIND
    if replacement == old:
        replacement = visibility_module.VISIBLE_SEGMENT_ORIGIN_KIND
    authority._visible_origin_kinds[key] = replacement
    try:
        with pytest.raises(RuntimeError):
            authority.authenticated_visible_observations(published, bind_page_id=bind_page)
    finally:
        authority._visible_origin_kinds[key] = old


def test_cached_page_rejects_changed_other_page_fingerprint():
    source, published, _ = _source(page_count=2)
    authority = source.authority()
    all_rows = authority.authenticated_visible_observations(published)
    other = next(oid for oid, row in all_rows if row.page_id == "2")
    authority.authenticated_visible_observations(published, bind_page_id="1")
    native = authority._visibility_receipts[(published.snapshot.snapshot_id, other)]
    store = source._producer._store
    key = (published.snapshot.snapshot_id, native)
    prior = store.record_fingerprints[key]
    store.record_fingerprints[key] = "0" * 64
    try:
        with pytest.raises(RuntimeError):
            authority.authenticated_visible_observations(published, bind_page_id="1")
    finally:
        store.record_fingerprints[key] = prior


def test_page_bound_alias_cache_is_owned_by_each_producer():
    one, first, _ = _source(page_count=1)
    two, second, _ = _source(page_count=1)
    one.authority().authenticated_visible_observations(first, bind_page_id="1")
    assert two._producer._store.visible_page_bound_rows is None
    two.authority().authenticated_visible_observations(second, bind_page_id="1")
    assert one._producer._store.visible_page_bound_rows is not two._producer._store.visible_page_bound_rows


def test_page_indices_do_not_pin_every_derived_flat_snapshot(monkeypatch):
    import fitz
    from test_source_visibility_batch_wall_index import _image_pdf
    from pb_raster_visible_segment_detector import RasterDetectedSegment
    doc = fitz.open()
    original = fitz.open(stream=_image_pdf(), filetype="pdf")
    try:
        for _ in range(3):
            doc.insert_pdf(original)
        payload = doc.tobytes(garbage=4, deflate=True)
    finally:
        original.close()
        doc.close()
    segment = RasterDetectedSegment(pixel_geometry=(40.0, 120.0, 360.0, 120.0),
        geometry_pt=(20.0, 60.0, 180.0, 60.0), orientation="horizontal")
    monkeypatch.setattr(visibility_module, "detect_axis_aligned_raster_segments",
                        lambda *a, **k: (segment,))
    source = visibility_module.SourceVisibilityProducer(producer_method="snapshot-index-bound", producer_version="1")
    pub = source.ingest_native_pdf_bytes(document_id="snapshot-index-bound", source_bytes=payload,
        source_locator="memory://synthetic-snapshot-index-bound.pdf")
    states = []
    store = source._producer._store
    for page in ("1", "2", "3"):
        pub = source.augment_with_raster_visible_segments(pub.revision.revision_id, page_ids=(page,))
        if states:
            # A new snapshot's page proof must release the previous whole-
            # source clone hint, not just a full-cache key for this new ID.
            source.authority().authenticated_visible_observations(pub, bind_page_id=page)
            assert store.visible_authentication_cache == {}
        rows = source.authority().authenticated_visible_observations(pub)
        assert rows
        states.append((pub, rows))
        assert len(store.visible_page_index) == 1
        assert set(store.visible_page_index) == {pub.snapshot.snapshot_id}
    # Evicting derived read indices must never evict source truth. An older
    # immutable selector still re-proves the same complete native/raster rows.
    for historical, expected in states:
        fresh = source.authority().authenticated_visible_observations(historical)
        assert fresh == expected
        assert len(store.visible_page_index) == 1
