"""The native-dimension source transaction authenticates the whole source once per phase.

Entry and exit of ``_native_dimension_source_proof_batch`` each authenticate the full
visible source. The cap-evidence proofs inside those two phases used to repeat the
identical whole-source read back to back (2 + 2 reads per transaction). They now reuse
the transaction's own just-proven read. Nothing else about them is relaxed: source
bytes, every text receipt and the full-page geometry are still re-proved by each call,
and the public method still authenticates the source by itself.
"""
from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch

import pytest
from test_native_dimension_cap_evidence import _source as _native_source

from pb_source_visibility_authority import (
    SourceVisibilityAuthority,
    SourceVisibilityProducer,
)


def _counting_authentications():
    original = SourceVisibilityAuthority.authenticated_visible_observations
    seen: list = []

    def wrapped(self, published, **kwargs):
        rows = original(self, published, **kwargs)
        seen.append((published, rows))
        return rows

    return (
        patch.object(
            SourceVisibilityAuthority, "authenticated_visible_observations", wrapped
        ),
        seen,
    )


def test_each_transaction_phase_authenticates_the_whole_source_exactly_once():
    source, published, _selector, _support = _native_source()
    counting, seen = _counting_authentications()
    with counting:
        with source._native_dimension_source_proof_batch(
            published, page_id="1"
        ) as rows:
            assert len(seen) == 1
            entry_published, entry_rows = seen[0]
            assert entry_published is published
            assert rows is entry_rows
        assert len(seen) == 2
        exit_published, exit_rows = seen[1]
        assert exit_published is published
        # The exit read is a fresh authentication of the same source: equal
        # content, never the entry object itself.
        assert exit_rows == entry_rows
        assert exit_rows is not entry_rows
    assert source._native_dimension_proof_batch is None


def test_cap_evidence_proofs_inside_the_transaction_reuse_its_own_fresh_reads():
    source, published, _selector, _support = _native_source()
    captured: list = []
    original = SourceVisibilityProducer._native_dimension_cap_evidence

    def spy(self, selector, *, opening_support_ids, authenticated):
        captured.append(authenticated)
        return original(
            self,
            selector,
            opening_support_ids=opening_support_ids,
            authenticated=authenticated,
        )

    counting, seen = _counting_authentications()
    with counting, patch.object(
        SourceVisibilityProducer, "_native_dimension_cap_evidence", spy
    ), source._native_dimension_source_proof_batch(published, page_id="1"):
        pass
    assert len(captured) == 2 and len(seen) == 2
    (entry_published, entry_rows), (exit_published, exit_rows) = captured
    assert entry_published is published and exit_published is published
    # Each proof reuses the read its own phase just performed, not a stale one.
    assert entry_rows is seen[0][1]
    assert exit_rows is seen[1][1]


def test_standalone_cap_evidence_still_authenticates_the_source_itself():
    source, published, selector, support = _native_source()
    counting, seen = _counting_authentications()
    with counting:
        atoms = source.native_dimension_cap_evidence(
            selector, opening_support_ids=support
        )
    assert len(atoms) == 2
    assert len(seen) == 1 and seen[0][0] == published


def test_reused_rows_give_exactly_the_standalone_result():
    source, published, selector, support = _native_source()
    standalone = source.native_dimension_cap_evidence(
        selector, opening_support_ids=support
    )
    rows = source.authority().authenticated_visible_observations(published)
    reused = source._native_dimension_cap_evidence(
        selector, opening_support_ids=support, authenticated=(published, rows)
    )
    assert reused == standalone


def test_rows_authenticated_for_another_snapshot_are_refused():
    source, published, selector, support = _native_source()
    rows = source.authority().authenticated_visible_observations(published)
    other = replace(
        published, visible_observation_ids=published.visible_observation_ids[:-1]
    )
    assert other != published
    with pytest.raises(RuntimeError):
        source._native_dimension_cap_evidence(
            selector, opening_support_ids=support, authenticated=(other, rows)
        )


@pytest.mark.parametrize("phase", ["entry", "exit"])
def test_damage_in_either_phase_still_aborts_the_transaction(phase):
    """Entry and exit proofs still fail closed on a source changed in that phase."""
    source, published, selector, support = _native_source()
    store = source._producer._store
    key = (selector.snapshot_id, support[0])
    if key not in store.observations:
        key = (selector.snapshot_id, source._visibility_receipts[key])
    record = store.observations[key]
    damaged = replace(record, geometry=(0.0, 0.0, 20.0, 0.0))
    if phase == "entry":
        store.observations[key] = damaged
        try:
            with pytest.raises(RuntimeError):
                with source._native_dimension_source_proof_batch(
                    published, page_id="1"
                ):
                    pytest.fail("a damaged source must not enter the transaction")
        finally:
            store.observations[key] = record
    else:
        try:
            with pytest.raises(RuntimeError):
                with source._native_dimension_source_proof_batch(
                    published, page_id="1"
                ):
                    store.observations[key] = damaged
        finally:
            store.observations[key] = record
    assert source._native_dimension_proof_batch is None
    # Restored source proves again.
    with source._native_dimension_source_proof_batch(published, page_id="1"):
        pass
