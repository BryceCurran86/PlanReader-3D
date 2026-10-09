"""Fresh source integrity precedes reuse of individual opening proofs."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

import pb_physical_wall_candidate_authority as module
from test_wall_visible_observation_page_index import _source


def _proof(source,published,authority,page_id='1',rows=None):
    return module._producer_proven_page_opening_records(
        source_producer=source,published=published,page_id=page_id,
        physical_opening_authority=authority,resolved_visible_observations=rows)


def test_complete_page_is_proven_once_without_a_count_or_scope_claim(monkeypatch):
    source,published,_ = _source(page_count=2)
    authority = source.physical_opening_authority()
    rows = source.authority().authenticated_visible_observations(published)
    page_rows = tuple(row for row in rows if row[1].page_id=='1')
    original = authority.prove_existence
    calls=[]
    def counted(selector):
        calls.append(selector.observation_id)
        return original(selector)
    monkeypatch.setattr(authority,'prove_existence',counted)
    first = _proof(source,published,authority,rows=page_rows)
    assert first and len({r.record_id for r in first}) == len(first)
    assert sorted(calls)==sorted(row[0] for row in page_rows)
    calls.clear()
    assert _proof(source,published,authority,rows=tuple(reversed(page_rows))) is first
    assert calls==[]
    second = _proof(source,published,authority,page_id='2')
    assert second and {r.record_id for r in first}.isdisjoint(r.record_id for r in second)
    assert sorted(calls)==sorted(row[0] for row in rows if row[1].page_id=='2')


@pytest.mark.parametrize('warm',[False,True])
def test_caller_subset_never_becomes_a_complete_proof_inventory(warm):
    source,published,_ = _source(page_count=1)
    authority=source.physical_opening_authority()
    rows=source.authority().authenticated_visible_observations(published)
    if warm: assert _proof(source,published,authority)
    with pytest.raises(RuntimeError,match='source_integrity_failure'):
        _proof(source,published,authority,rows=rows[:-1])
    assert _proof(source,published,authority)


@pytest.mark.parametrize('warm',[False,True])
def test_damage_outside_cached_openings_page_is_checked_before_cache_hit(warm):
    source,published,_ = _source(page_count=2)
    authority=source.physical_opening_authority()
    if warm: assert _proof(source,published,authority)
    rows=source.authority().authenticated_visible_observations(published)
    observation_id = next(key for key,row in rows if row.page_id=='2')
    key=(published.snapshot.snapshot_id,observation_id)
    original=source._producer._store.observations[key]
    source._producer._store.observations[key]=replace(original,
        geometry=tuple(value+1 for value in original.geometry))
    with pytest.raises(RuntimeError):
        _proof(source,published,authority)
    source._producer._store.observations[key]=original
    assert _proof(source,published,authority)


def test_another_producers_cache_cannot_be_used_even_for_identical_source_bytes():
    source,published,_ = _source(page_count=1)
    other,other_published,_ = _source(page_count=1)
    other_authority=other.physical_opening_authority()
    assert _proof(other,other_published,other_authority)
    with pytest.raises(RuntimeError,match='source_integrity_failure'):
        _proof(source,published,other_authority)
    with pytest.raises(TypeError,match='producer-owned'):
        _proof(source,published,SimpleNamespace(prove_existence=lambda _: None))


def test_small_page_is_still_fully_proven_and_never_defaults_to_one(monkeypatch):
    import fitz
    from pb_source_visibility_authority import SourceVisibilityProducer
    doc=fitz.open()
    page=doc.new_page(width=200,height=200)
    page.draw_line((10,20),(30,20),width=1)
    payload=doc.tobytes(garbage=4,deflate=True)
    doc.close()
    source=SourceVisibilityProducer(producer_method='small-page-proof-test',producer_version='1')
    published=source.ingest_native_pdf_bytes(document_id='small-page-proof-test',source_bytes=payload,
        source_locator='memory://small-page.pdf',page_ids=('1',))
    authority=source.physical_opening_authority()
    rows=source.authority().authenticated_visible_observations(published)
    assert 0<len(rows)<6
    calls=[]
    original=authority.prove_existence
    def counted(selector):
        calls.append(selector.observation_id)
        return original(selector)
    monkeypatch.setattr(authority,'prove_existence',counted)
    assert _proof(source,published,authority)==()
    assert sorted(calls)==sorted(key for key,_ in rows)
    calls.clear()
    assert _proof(source,published,authority)==()
    assert calls==[]
