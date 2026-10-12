"""Full original source page proof batch: source mutations invalidate reuse."""
from dataclasses import replace
from unittest.mock import patch

import pytest

from pb_source_visibility_authority import SourceVisibilityAuthority
from test_native_dimension_cap_evidence import _source as _native_source
from test_wall_visible_observation_page_index import _source as _wall_source
from test_wall_opening_page_proof_cache import _proof


def test_batch_original_native_components_match_scalar_with_final_reproof():
    source, published, selector, support = _native_source()
    original = source.native_dimension_cap_evidence(selector, opening_support_ids=support)
    assert len(original) == 2
    original_resolve = SourceVisibilityAuthority.authenticated_visible_observations
    with patch.object(
        SourceVisibilityAuthority, "authenticated_visible_observations", autospec=True
    ) as wrapped:
        wrapped.side_effect = lambda instance, pub: original_resolve(instance, pub)
        with source._native_dimension_source_proof_batch(published, page_id="1"):
            first = source.native_dimension_cap_evidence(selector, opening_support_ids=support)
            second = source.native_dimension_cap_evidence(
                selector, opening_support_ids=tuple(reversed(support))
            )
            assert first == second == original
            assert first is not second
            assert wrapped.call_count == 2
        assert wrapped.call_count == 4
    assert source._native_dimension_proof_batch is None
    assert source.native_dimension_cap_evidence(selector, opening_support_ids=support) == original


@pytest.mark.parametrize("damage", [
    "visible_geometry", "visibility_parent", "text_receipt",
    "text_page", "source_bytes", "stale_revision",
])
def test_source_changed_inside_batch_aborts_before_publication(damage):
    source, published, selector, support = _native_source()
    store = source._producer._store
    original = source.native_dimension_cap_evidence(selector, opening_support_ids=support)
    assert len(original) == 2
    with pytest.raises(RuntimeError):
        with source._native_dimension_source_proof_batch(published, page_id="1"):
            assert source.native_dimension_cap_evidence(selector, opening_support_ids=support) == original
            if damage == "visible_geometry":
                key=(selector.snapshot_id,support[0]); record=store.observations[key]
                store.observations[key]=replace(record,geometry=(0.,0.,20.,0.))
            elif damage == "visibility_parent":
                source._visibility_receipts.pop((selector.snapshot_id,support[0]))
            elif damage == "text_receipt":
                source._text_integrity_receipts.clear()
            elif damage == "text_page":
                key=(selector.snapshot_id,published.text_observation_ids[0])
                record=store.observations[key]
                store.observations[key]=replace(record,page_id="2")
            elif damage == "source_bytes":
                store.source_bytes_by_revision[selector.revision_id]=b"bad-original"
            elif damage == "stale_revision":
                store.current_revision_by_document[selector.document_id]="new-competing-revision"
    assert source._native_dimension_proof_batch is None


def test_no_foreign_source_or_fragment_can_borrow_an_original_batch():
    source, published, selector, support = _native_source()
    with source._native_dimension_source_proof_batch(published, page_id="1"):
        assert source.native_dimension_cap_evidence(selector, opening_support_ids=support)
        with pytest.raises(RuntimeError):
            source.native_dimension_cap_evidence(
                replace(selector,source_sha256="foreign-source"), opening_support_ids=support
            )
        with pytest.raises(RuntimeError):
            source.native_dimension_cap_evidence(
                selector, opening_support_ids=(support[0], "not-original")
            )
        with pytest.raises(RuntimeError):
            with source._native_dimension_source_proof_batch(published,page_id="1"):
                pass


def test_full_page_competitor_mutated_midbatch_rejects_all_opening_proofs(monkeypatch):
    source,published,_ = _wall_source(page_count=2)
    authority=source.physical_opening_authority()
    original=authority.prove_existence
    rows=source.authority().authenticated_visible_observations(published)
    competitor=next(observation_id for observation_id, rec in rows if rec.page_id=="2")
    key=(published.snapshot.snapshot_id, competitor)
    record=source._producer._store.observations[key]
    modified=False

    def mutate_once(selector):
        nonlocal modified
        output=original(selector)
        if not modified:
            modified=True
            source._producer._store.observations[key]=replace(record,geometry=(0.,0.,2.,0.))
        return output

    monkeypatch.setattr(authority,"prove_existence",mutate_once)
    with pytest.raises(RuntimeError):
        _proof(source,published,authority,page_id="1")
    assert source._native_dimension_proof_batch is None
    source._producer._store.observations[key]=record
    monkeypatch.setattr(authority,"prove_existence",original)
    assert _proof(source,published,authority,page_id="1")


def test_native_source_text_integrity_unavailable_aborts_full_page_batch():
    source, published, selector, support = _native_source()
    physical = source.physical_opening_authority()
    source._text_integrity_receipts.clear()
    with pytest.raises(RuntimeError):
        _proof(source, published, physical, page_id="1")
    assert source._native_dimension_proof_batch is None
