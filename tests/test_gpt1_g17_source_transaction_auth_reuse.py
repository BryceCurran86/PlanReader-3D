"""Source-authenticated G17 prepass reuse: no loss of lineage or competitor proof."""
from dataclasses import replace

import pytest

import pb_physical_wall_candidate_authority as wall
from pb_source_visibility_authority import SourceVisibilityAuthority
from test_wall_visible_observation_page_index import _source


def _proof(source, published, physical, *, page="1", rows=None):
    return wall._producer_proven_page_opening_records(
        source_producer=source,
        published=published,
        page_id=page,
        physical_opening_authority=physical,
        resolved_visible_observations=rows,
        proof_scope_fingerprint="gpt1-source-transaction-integrity",
    )


def test_original_g17_proof_reuses_transaction_entry_auth_and_retains_order(
    monkeypatch,
):
    source, published, _ = _source(page_count=2)
    physical = source.physical_opening_authority()
    visibility = source.authority()
    page_rows = tuple(
        (key, value)
        for key, value in visibility.authenticated_visible_observations(published)
        if str(value.page_id) == "1"
    )
    original = SourceVisibilityAuthority.authenticated_visible_observations
    checks = []

    def checked(self, exact_published, **kwargs):
        checks.append(exact_published)
        return original(self, exact_published, **kwargs)

    monkeypatch.setattr(
        SourceVisibilityAuthority, "authenticated_visible_observations", checked
    )
    first = _proof(source, published, physical, rows=page_rows)
    # Entry and exit BOTH fully reauthenticate the same original published
    # document, including every competitor on the other source page. Native
    # text/opposition and physical candidate substages may also reauthenticate.
    assert len(checks) >= 2
    assert all(item is published for item in checks)
    assert len({x.record_id for x in first}) == len(first)
    checks.clear()
    second = _proof(source, published, physical, rows=tuple(reversed(page_rows)))
    assert second is first
    # Cached proof still authenticates the entire source on every reuse.
    assert checks == [published]


@pytest.mark.parametrize("warm", [False, True])
def test_original_g17_full_page_competitor_damage_abstains_before_cached_reuse(
    warm,
):
    source, published, _ = _source(page_count=2)
    physical = source.physical_opening_authority()
    if warm:
        assert _proof(source, published, physical)
    rows = source.authority().authenticated_visible_observations(published)
    competitor = next(key for key, record in rows if str(record.page_id) == "2")
    key = (published.snapshot.snapshot_id, competitor)
    prior = source._producer._store.observations[key]
    source._producer._store.observations[key] = replace(
        prior, geometry=tuple(float(value) + 3 for value in prior.geometry)
    )
    try:
        with pytest.raises(RuntimeError):
            _proof(source, published, physical)
    finally:
        source._producer._store.observations[key] = prior
    assert _proof(source, published, physical)


def test_original_g17_transaction_rechecks_competitor_mutated_during_proof(
    monkeypatch,
):
    source, published, _ = _source(page_count=2)
    physical = source.physical_opening_authority()
    rows = source.authority().authenticated_visible_observations(published)
    competitor = next(key for key, record in rows if str(record.page_id) == "2")
    key = (published.snapshot.snapshot_id, competitor)
    stored = source._producer._store.observations
    original_record = stored[key]
    original_prove = physical.prove_existence
    mutation_count = []

    def mutate_after_transaction_entry(selector):
        if not mutation_count:
            mutation_count.append(selector.observation_id)
            stored[key] = replace(
                original_record,
                geometry=tuple(float(value) + 2 for value in original_record.geometry),
            )
        return original_prove(selector)

    monkeypatch.setattr(physical, "prove_existence", mutate_after_transaction_entry)
    try:
        with pytest.raises(RuntimeError):
            _proof(source, published, physical)
        assert len(mutation_count) == 1
        # The failed transaction must not cache any signed page proof.
        assert not any(
            value[3] == published.snapshot.snapshot_id
            for value in physical._wall_source_opening_page_proof_cache
        )
    finally:
        stored[key] = original_record
    assert _proof(source, published, physical)


def test_failed_source_batch_evicts_only_affected_snapshot_negative_memos():
    source, published, _ = _source(page_count=1)
    physical = source.physical_opening_authority()
    affected = published.snapshot.snapshot_id
    unaffected = "independent-other-snapshot"
    damaged_key = ("doc", "rev", "sha", affected, "observation")
    intact_key = ("doc", "rev", "sha", unaffected, "observation")
    physical._visible_source_result_cache[damaged_key] = object()
    preserved = object()
    physical._visible_source_result_cache[intact_key] = preserved
    physical._visible_candidate_cache[damaged_key] = ()
    physical._visible_snapshot_cache[("doc", "rev", "sha", affected)] = ((), ())
    physical._visible_snapshot_cache[("doc", "rev", "sha", unaffected)] = ((), ())
    physical._visible_existence_cache[damaged_key] = object()
    physical._wall_source_opening_page_proof_cache[
        ("doc", "rev", "sha", affected, "page", "scope")
    ] = ()

    physical._invalidate_snapshot_caches_after_failed_source_batch(affected)

    assert damaged_key not in physical._visible_source_result_cache
    assert damaged_key not in physical._visible_candidate_cache
    assert damaged_key not in physical._visible_existence_cache
    assert ("doc", "rev", "sha", affected) not in physical._visible_snapshot_cache
    assert not physical._wall_source_opening_page_proof_cache
    assert physical._visible_source_result_cache[intact_key] is preserved
    assert ("doc", "rev", "sha", unaffected) in physical._visible_snapshot_cache
