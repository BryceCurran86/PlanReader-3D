"""One original-source page transaction may revisit the SAME support fragments.

Source-proofing still authenticates entry and exit; this cache cannot create
physical opening/wall authority or change any FIRM/customer/evaluator output.
"""
from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch

import pytest

import pb_native_dimension_cap_evidence as native
from pb_source_visibility_authority import SourceVisibilityAuthority
from test_native_dimension_cap_evidence import _source as original_source


def test_repeated_same_source_supports_do_not_rescan_original_components():
    source, published, selector, support = original_source()
    unoptimized = source.native_dimension_cap_evidence(
        selector, opening_support_ids=support
    )
    spy = native.native_dimension_cap_evidence_from_components
    # Both batch ENTRY and batch EXIT still prove source independently.
    with patch.object(native, "native_dimension_cap_evidence_from_components", wraps=spy) as compiled:
        with source._native_dimension_source_proof_batch(published, page_id="1"):
            first = source.native_dimension_cap_evidence(
                selector, opening_support_ids=support
            )
            count = compiled.call_count
            assert count >= 1
            for selection in (support, tuple(reversed(support)), support):
                same = source.native_dimension_cap_evidence(
                    selector, opening_support_ids=selection
                )
                assert same == first == unoptimized
                assert compiled.call_count == count
        # The independent EXIT re-proof is never satisfied from an internal
        # source-candidate cache.
        assert compiled.call_count >= count + 1


def test_original_source_atom_metadata_cannot_be_poisoned_from_cache():
    source, published, selector, support = original_source()
    with source._native_dimension_source_proof_batch(published, page_id="1"):
        candidate = source.native_dimension_cap_evidence(
            selector, opening_support_ids=support
        )
        assert candidate
        original = candidate[0].metadata["opening_support_observation_ids"]
        candidate[0].metadata["opening_support_observation_ids"] = ("malicious",)
        recovered = source.native_dimension_cap_evidence(
            selector, opening_support_ids=support
        )
        assert recovered[0].metadata["opening_support_observation_ids"] == original
        assert recovered[0].evidence_id == candidate[0].evidence_id
        assert recovered[0].metadata is not candidate[0].metadata


def test_each_complete_source_proof_batch_owns_distinct_selection_cache():
    source, published, selector, support = original_source()
    with source._native_dimension_source_proof_batch(published, page_id="1"):
        first = source.native_dimension_cap_evidence(
            selector, opening_support_ids=support
        )
        assert source._native_dimension_proof_batch["selected_evidence_cache"]
    assert source._native_dimension_proof_batch is None
    with source._native_dimension_source_proof_batch(published, page_id="1"):
        second = source.native_dimension_cap_evidence(
            selector, opening_support_ids=support
        )
        assert second == first
        assert source._native_dimension_proof_batch["selected_evidence_cache"]
    assert source._native_dimension_proof_batch is None


def test_foreign_original_support_does_not_borrow_cached_atoms():
    source, published, selector, support = original_source()
    with source._native_dimension_source_proof_batch(published, page_id="1"):
        source.native_dimension_cap_evidence(selector, opening_support_ids=support)
        with pytest.raises(RuntimeError):
            source.native_dimension_cap_evidence(
                selector, opening_support_ids=tuple(support) + ("foreign-original-segment",)
            )


def test_source_tamper_between_batch_phases_aborts_and_discards_cache():
    source, published, selector, support = original_source()
    store = source._producer._store
    key = (selector.snapshot_id, support[0])
    if key not in store.observations:
        key = (selector.snapshot_id, source._visibility_receipts[key])
    original = store.observations[key]
    try:
        with pytest.raises(RuntimeError):
            with source._native_dimension_source_proof_batch(published, page_id="1"):
                source.native_dimension_cap_evidence(selector, opening_support_ids=support)
                store.observations[key] = replace(
                    original, geometry=(0., 0., 20., 0.),
                )
    finally:
        store.observations[key] = original
    assert source._native_dimension_proof_batch is None
    with source._native_dimension_source_proof_batch(published, page_id="1"):
        assert source.native_dimension_cap_evidence(
            selector, opening_support_ids=support
        )


def test_public_issuer_still_independently_authenticates_every_query():
    source, published, selector, support = original_source()
    original = SourceVisibilityAuthority.authenticated_visible_observations
    calls = []
    def spy(self, published, **kwargs):
        calls.append(1)
        return original(self, published, **kwargs)
    with patch.object(SourceVisibilityAuthority, "authenticated_visible_observations", spy):
        first = source.native_dimension_cap_evidence(selector, opening_support_ids=support)
        second = source.native_dimension_cap_evidence(selector, opening_support_ids=support)
    assert first == second and first
    assert len(calls) == 2
