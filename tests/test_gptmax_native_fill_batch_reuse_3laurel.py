"""W4 batch fill evidence may reuse authenticated rows but cannot bypass source reproof."""
from unittest.mock import patch
import pytest
from pb_source_visibility_authority import SourceVisibilityAuthority
from test_native_unstroked_fill_evidence import _source


def test_batch_fill_matches_scalar_without_repeated_receipt_resolution():
    source, published, selector, supports = _source()
    original = source.native_unstroked_fill_evidence(selector, support_observation_ids=supports)
    assert original
    with source._native_dimension_source_proof_batch(published, page_id="1"):
        with patch.object(SourceVisibilityAuthority, "resolve_visible",
                          side_effect=AssertionError("repeated scalar receipt")):
            batched = source.native_unstroked_fill_evidence(
                selector, support_observation_ids=tuple(reversed(supports)))
            assert batched == original
    assert source._native_dimension_proof_batch is None


def test_batch_detects_changed_original_bytes_on_exit():
    source, published, selector, supports = _source()
    with pytest.raises(RuntimeError):
        with source._native_dimension_source_proof_batch(published, page_id="1"):
            assert source.native_unstroked_fill_evidence(
                selector, support_observation_ids=supports)
            source._producer._store.source_bytes_by_revision[selector.revision_id] = b"tampered"
    assert source._native_dimension_proof_batch is None


def test_direct_fill_authentication_still_rejects_missing_receipt():
    source, _, selector, supports = _source()
    assert source.native_unstroked_fill_evidence(
        selector, support_observation_ids=supports)
    source._visibility_receipts.pop((selector.snapshot_id, supports[0]))
    with pytest.raises(RuntimeError):
        source.native_unstroked_fill_evidence(
            selector, support_observation_ids=supports)
